"""
smoke_test.py — Validates the Railway Docker environment before deploying the full sync worker.

Run inside the container:
  python smoke_test.py

Expected output (without env vars set):
  [PASS] Playwright: Headless Chromium launched and navigated successfully
  [SKIP] Firebase: FIREBASE_SERVICE_ACCOUNT not set
  [SKIP] Fernet: FERNET_KEY not set
  ----------------------------------------
  Results: 1 passed, 0 failed, 2 skipped

With all env vars set, all three tests should show [PASS].
"""

import os
import sys
import json


def test_playwright():
    """Verify Playwright can launch headless Chromium and navigate to a page."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com", timeout=30000)
            title = page.title()
            browser.close()

        assert "Example" in title, f"Unexpected page title: {title!r}"
        print("[PASS] Playwright: Headless Chromium launched and navigated successfully")
        return "pass"

    except Exception as e:
        print(f"[FAIL] Playwright: {e}")
        return "fail"


def test_firebase():
    """Verify Firebase Admin SDK initializes from the FIREBASE_SERVICE_ACCOUNT env var (JSON blob)."""
    env_var = "FIREBASE_SERVICE_ACCOUNT"
    service_account_json = os.environ.get(env_var)

    if not service_account_json:
        print(f"[SKIP] Firebase: {env_var} not set")
        return "skip"

    try:
        import firebase_admin
        from firebase_admin import credentials

        service_account_dict = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_dict)
        app = firebase_admin.initialize_app(cred, name="smoke_test")

        # Verify the app was registered successfully
        retrieved = firebase_admin.get_app("smoke_test")
        assert retrieved is not None

        # Clean up so the test can be run multiple times without "app already exists" error
        firebase_admin.delete_app(app)

        print("[PASS] Firebase: Admin SDK initialized from environment variable")
        return "pass"

    except json.JSONDecodeError as e:
        print(f"[FAIL] Firebase: {env_var} is not valid JSON — {e}")
        return "fail"
    except Exception as e:
        print(f"[FAIL] Firebase: {e}")
        return "fail"


def test_fernet():
    """Verify Python cryptography.fernet is compatible with the existing Fernet key."""
    env_var = "FERNET_KEY"
    fernet_key = os.environ.get(env_var)

    if not fernet_key:
        print(f"[SKIP] Fernet: {env_var} not set")
        return "skip"

    try:
        from cryptography.fernet import Fernet

        # Key must be bytes for the Fernet constructor
        if isinstance(fernet_key, str):
            fernet_key = fernet_key.encode()

        f = Fernet(fernet_key)

        # Roundtrip test: encrypt then decrypt
        plaintext = b"attendance-sync-smoke-test"
        token = f.encrypt(plaintext)
        decrypted = f.decrypt(token)

        assert decrypted == plaintext, "Decrypted value does not match original"

        print("[PASS] Fernet: Encryption/decryption roundtrip successful")
        return "pass"

    except Exception as e:
        print(f"[FAIL] Fernet: {e}")
        return "fail"


def main():
    print("=" * 40)
    print("Railway Worker Smoke Test")
    print("=" * 40)

    results = [
        test_playwright(),
        test_firebase(),
        test_fernet(),
    ]

    passed = results.count("pass")
    failed = results.count("fail")
    skipped = results.count("skip")

    print("-" * 40)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("SMOKE TEST FAILED — do not deploy worker.py until all tests pass")
        sys.exit(1)
    else:
        print("Smoke test complete — environment is ready")
        sys.exit(0)


if __name__ == "__main__":
    main()
