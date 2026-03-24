"""
Self-healing module for the Railway sync worker.

When all static selector strategies in selectors.json have been exhausted,
attempt_heal() asks Gemini Flash (then Pro on failure) to discover a
replacement CSS/XPath selector from the live DOM.

Usage:
    from healer import attempt_heal

    new_selector = attempt_heal(
        page=page,
        element_type="absent_checkbox",
        format_args={},
        original_selectors=["span[data-cd='A'] input", ...],
        teacher_uid=uid,
    )
    if new_selector:
        element = page.locator(new_selector)
"""

import logging
import os
import re
from typing import Optional

from firestore_client import get_healing_call_count_today, write_healing_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAILY_HEALING_CAP = 25  # Max Gemini API calls across all teachers per UTC day

# Flash is fast and cheap; Pro is a fallback for harder cases.
_GEMINI_FLASH_MODEL = "gemini-2.0-flash"
_GEMINI_PRO_MODEL = "gemini-2.0-pro"

# Maximum DOM size to send to Gemini (~30 KB)
_MAX_DOM_BYTES = 30_000

# Human-readable descriptions for each element type — used in the Gemini prompt
_ELEMENT_DESCRIPTIONS = {
    "student_cell": (
        "A table cell (td) containing or associated with student ID {student_id}"
    ),
    "absent_checkbox": (
        "The checkbox input for marking a student Absent (typically labeled 'A')"
    ),
    "tardy_checkbox": (
        "The checkbox input for marking a student Tardy (typically labeled 'T')"
    ),
    "period_dropdown": (
        "A dropdown (select element) for choosing which class period to view"
    ),
}

# Lazy sentinel so we only emit the "GEMINI_API_KEY missing" warning once
_api_key_missing_logged = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_gemini_client():
    """
    Return a configured google.generativeai module, or None if the API key
    is missing or the library is not installed.
    """
    global _api_key_missing_logged

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        if not _api_key_missing_logged:
            logger.warning(
                "GEMINI_API_KEY environment variable is not set — "
                "self-healing is disabled"
            )
            _api_key_missing_logged = True
        return None

    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        return genai
    except ImportError:
        logger.warning(
            "google-generativeai package not installed — self-healing is disabled. "
            "Run: pip install google-generativeai"
        )
        return None


def _extract_dom(page) -> str:
    """
    Extract a stripped, truncated DOM string from a Playwright Page or Locator.

    Removes <script> and <style> blocks to reduce noise before sending to Gemini.
    Truncates to _MAX_DOM_BYTES characters.
    """
    try:
        # Page.content() works on full Page objects
        html = page.content()
    except AttributeError:
        try:
            # inner_html() works on Locator objects
            html = page.inner_html()
        except Exception as exc:
            logger.debug(f"DOM extraction inner_html() failed: {exc}")
            return ""
    except Exception as exc:
        logger.debug(f"DOM extraction content() failed: {exc}")
        return ""

    # Strip <script>...</script> blocks (including multiline, case-insensitive)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    # Strip <style>...</style> blocks
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)

    if len(html) > _MAX_DOM_BYTES:
        html = html[:_MAX_DOM_BYTES] + "\n<!-- [DOM truncated] -->"

    return html


def _build_prompt(element_type: str, format_args: dict, original_selectors: list, dom: str) -> str:
    """Construct the Gemini prompt for selector discovery."""
    description_template = _ELEMENT_DESCRIPTIONS.get(
        element_type,
        f"An element of type '{element_type}'"
    )
    # Fill in format_args placeholders in the description if present
    try:
        description = description_template.format(**format_args)
    except KeyError:
        description = description_template

    original_str = "\n".join(f"  - {s}" for s in original_selectors)

    return f"""You are helping a web automation tool find a specific element on an Aeries Student Information System attendance page.

ELEMENT TO FIND:
{description}

SELECTORS THAT PREVIOUSLY WORKED (now broken — the page layout may have changed):
{original_str}

PAGE DOM (truncated, script/style removed):
{dom}

YOUR TASK:
Examine the DOM carefully and return a single CSS selector or XPath expression that uniquely identifies the target element described above.

RULES:
1. Return ONLY the selector string — no explanation, no markdown, no code block.
2. If using XPath, prefix with "xpath=" (e.g. xpath=.//td[@data-id='123']).
3. If the element cannot be found in the DOM, return exactly: NONE
4. Do not hallucinate attributes or elements that are not in the DOM.
5. Prefer specific attribute selectors over generic text matches.

SELECTOR:"""


def _validate_selector(page, candidate: str, format_args: dict) -> bool:
    """
    Try to locate `candidate` on the page after formatting with format_args.
    Returns True if at least one matching element is found.
    """
    try:
        formatted = candidate.format(**format_args)
    except KeyError:
        formatted = candidate

    try:
        count = page.locator(formatted).count()
        return count > 0
    except Exception as exc:
        logger.debug(f"Selector validation failed for '{formatted}': {exc}")
        return False


def _call_gemini(genai, model_name: str, prompt: str) -> Optional[str]:
    """
    Call the specified Gemini model and return the stripped response text.
    Returns None on any API error.
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text.strip()
        return text if text else None
    except Exception as exc:
        logger.warning(f"Gemini {model_name} call failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def attempt_heal(
    page,
    element_type: str,
    format_args: dict,
    original_selectors: list,
    teacher_uid: Optional[str] = None,
) -> Optional[str]:
    """
    Attempt to heal a broken selector using Gemini LLM.

    Strategy:
        1. Check daily cap (25 calls/day across all teachers).
        2. Extract DOM context from the Playwright page.
        3. Call Gemini Flash with a prompt describing the target element.
        4. Validate the returned selector against the live page.
        5. If Flash fails, escalate to Gemini Pro.
        6. Log all attempts to Firestore healing_events collection.

    Args:
        page:               Playwright Page or Locator (already on the attendance page).
        element_type:       One of "student_cell", "absent_checkbox", "tardy_checkbox",
                            "period_dropdown".
        format_args:        Dict of format values (e.g. {"student_id": "12345"}).
        original_selectors: The static selector list that already failed — passed to
                            Gemini as context for what used to work.
        teacher_uid:        Optional UID for healing event log context.

    Returns:
        A working selector string (already validated on the page), or None if
        healing failed (cap hit, API error, or no valid selector found).
    """
    genai = _get_gemini_client()
    if genai is None:
        # Healing is disabled (no API key or missing library) — fail silently
        return None

    # ------------------------------------------------------------------
    # Step 1: Daily cap check
    # ------------------------------------------------------------------
    current_count = get_healing_call_count_today()
    if current_count >= DAILY_HEALING_CAP:
        logger.warning(
            f"Daily healing cap reached ({current_count}/{DAILY_HEALING_CAP}) — "
            "skipping Gemini call"
        )
        return None

    # ------------------------------------------------------------------
    # Step 2: DOM context preparation
    # ------------------------------------------------------------------
    dom = _extract_dom(page)
    if not dom:
        logger.warning("Could not extract DOM for healing — aborting")
        return None

    prompt = _build_prompt(element_type, format_args, original_selectors, dom)

    # ------------------------------------------------------------------
    # Step 3 & 4: Gemini Flash attempt
    # ------------------------------------------------------------------
    flash_result = None
    flash_success = False

    logger.info(
        f"[healer] Attempting Gemini Flash heal for element_type={element_type}"
        + (f" teacher={teacher_uid}" if teacher_uid else "")
    )
    raw_flash = _call_gemini(genai, _GEMINI_FLASH_MODEL, prompt)

    if raw_flash and raw_flash.upper() != "NONE":
        if _validate_selector(page, raw_flash, format_args):
            logger.info(f"[healer] Gemini Flash found working selector: {raw_flash}")
            flash_result = raw_flash
            flash_success = True
        else:
            logger.info(
                f"[healer] Gemini Flash returned '{raw_flash}' but validation failed"
            )

    # Log Flash attempt to Firestore
    write_healing_event(
        element_type=element_type,
        model=_GEMINI_FLASH_MODEL,
        candidate=raw_flash,
        success=flash_success,
        teacher_uid=teacher_uid,
        format_args=format_args,
    )

    if flash_success:
        return flash_result

    # ------------------------------------------------------------------
    # Step 5: Gemini Pro escalation
    # ------------------------------------------------------------------
    logger.info("[healer] Flash failed — escalating to Gemini Pro")
    pro_result = None
    pro_success = False

    raw_pro = _call_gemini(genai, _GEMINI_PRO_MODEL, prompt)

    if raw_pro and raw_pro.upper() != "NONE":
        if _validate_selector(page, raw_pro, format_args):
            logger.info(f"[healer] Gemini Pro found working selector: {raw_pro}")
            pro_result = raw_pro
            pro_success = True
        else:
            logger.info(
                f"[healer] Gemini Pro returned '{raw_pro}' but validation failed"
            )

    # Log Pro attempt to Firestore
    write_healing_event(
        element_type=element_type,
        model=_GEMINI_PRO_MODEL,
        candidate=raw_pro,
        success=pro_success,
        teacher_uid=teacher_uid,
        format_args=format_args,
    )

    if pro_success:
        return pro_result

    # ------------------------------------------------------------------
    # Both models failed
    # ------------------------------------------------------------------
    logger.warning(
        f"[healer] Self-healing exhausted both Flash and Pro for "
        f"element_type={element_type} — returning None"
    )
    return None
