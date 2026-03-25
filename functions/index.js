/**
 * Firebase Cloud Functions for Attendance Taker
 *
 * authenticateTeacher: Validates Aeries credentials, encrypts the password
 * with Fernet, stores credentials in Firestore, and issues a Firebase
 * custom auth token so the teacher can sign in to the app.
 *
 * fetchRoster: Fetches the teacher's class rosters from Aeries using
 * Puppeteer (headless Chrome), then writes them to Firestore.
 *
 * syncAttendance: Scheduled function (every 20 min, Mon-Fri 8am-3:40pm).
 * Reads attendance from Firestore, logs into Aeries via Puppeteer, and
 * updates attendance checkboxes (Absent/Tardy/Present) for each period.
 *
 * Security boundaries:
 *   - The Fernet key exists ONLY in process.env.FERNET_KEY (set via
 *     firebase functions:secrets:set or --set-env-vars).  It is never
 *     written to Firestore or sent to the client.
 *   - Plaintext passwords are never persisted anywhere.
 *   - The admin SDK bypasses Firestore security rules, so the credentials
 *     sub-collection is effectively server-only even though the rules
 *     say "allow read/write: if false".
 */

"use strict";

const {onCall, HttpsError} = require("firebase-functions/v2/https");
const {onSchedule} = require("firebase-functions/v2/scheduler");
const {logger} = require("firebase-functions/v2");
const admin = require("firebase-admin");
const fernet = require("fernet");
const cheerio = require("cheerio");
const crypto = require("crypto");

admin.initializeApp();
const db = admin.firestore();

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AERIES_BASE_URL = "https://fullertonjuhsd.aeries.net/teacher";
const AERIES_LOGIN_URL = `${AERIES_BASE_URL}/Login.aspx`;

// Fake email domain used to create Firebase Auth accounts for teachers.
// Aeries usernames are not real email addresses, so we manufacture one.
const AUTH_EMAIL_DOMAIN = "aeries.attendance.local";

// Rate-limit settings for authenticateTeacher
const RATE_LIMIT_MAX_ATTEMPTS = 5; // max failed attempts per window
const RATE_LIMIT_WINDOW_MS = 15 * 60 * 1000; // 15-minute window

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create an AbortSignal that times out after `ms` milliseconds. */
function fetchTimeout(ms = 15000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return {signal: controller.signal, clear: () => clearTimeout(id)};
}

/**
 * Fetch the Aeries login page and extract all hidden ASP.NET form fields.
 * Returns an object mapping field names to values.
 */
async function fetchAeriesFormTokens() {
  const timeout = fetchTimeout(15000);
  try {
    const response = await fetch(AERIES_LOGIN_URL, {
      method: "GET",
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
      },
      redirect: "manual",
      signal: timeout.signal,
    });

    const html = await response.text();
    const $ = cheerio.load(html);

    // Extract ALL hidden form fields (handles both old and new Aeries)
    const hiddenFields = {};
    $("input[type='hidden']").each((_, el) => {
      const name = $(el).attr("name");
      const val = $(el).val() || "";
      if (name) hiddenFields[name] = val;
    });

    return hiddenFields;
  } finally {
    timeout.clear();
  }
}

/**
 * Attempt to validate Aeries credentials.
 * Returns { valid: boolean, reason: string }.
 *
 * Graceful degradation: if the Aeries server is unreachable or parsing
 * fails, returns { valid: false, reason: 'aeries_unreachable' } so the
 * caller can decide whether to proceed anyway.
 */
async function validateAeriesCredentials(username, password) {
  try {
    const hiddenFields = await fetchAeriesFormTokens();

    const body = new URLSearchParams({
      ...hiddenFields,
      "Username_Aeries": username,
      "Password_Aeries": password,
      "btnSignIn_Aeries": "Log In",
    });

    const timeout = fetchTimeout(15000);
    try {
      const response = await fetch(AERIES_LOGIN_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
        },
        body: body.toString(),
        redirect: "manual",
        signal: timeout.signal,
      });

      // ASP.NET redirects away from Login.aspx on success (status 302 or 301).
      // If we stay on the same page (200), credentials were rejected.
      const isRedirect = response.status === 302 || response.status === 301;
      const location = response.headers.get("location") || "";
      const redirectedAway =
        location.length > 0 && !location.toLowerCase().includes("login");

      if (isRedirect && redirectedAway) {
        return {valid: true, reason: "credentials_accepted"};
      }

      return {valid: false, reason: "credentials_rejected"};
    } finally {
      timeout.clear();
    }
  } catch (err) {
    logger.warn("Aeries validation failed with error — proceeding without validation", {
      error: err.message,
    });
    return {valid: false, reason: "aeries_unreachable"};
  }
}

/**
 * Decrypt a Fernet token back to plaintext.
 * The key is read from process.env.FERNET_KEY at call time.
 */
function fernetDecrypt(ciphertext) {
  const keyString = process.env.FERNET_KEY;
  if (!keyString) {
    throw new Error(
        "FERNET_KEY environment variable is not set. " +
        "Set it via: firebase functions:secrets:set FERNET_KEY",
    );
  }
  const secret = new fernet.Secret(keyString);
  const token = new fernet.Token({
    secret: secret,
    token: ciphertext,
    ttl: 0, // No expiry check for stored credentials
  });
  return token.decode();
}

/**
 * Encrypt a plaintext string using Fernet.
 * The key is read from process.env.FERNET_KEY at call time (not module load)
 * so that test environments can set it after requiring the module.
 */
function fernetEncrypt(plaintext) {
  const keyString = process.env.FERNET_KEY;
  if (!keyString) {
    throw new Error(
        "FERNET_KEY environment variable is not set. " +
        "Set it via: firebase functions:secrets:set FERNET_KEY",
    );
  }

  const secret = new fernet.Secret(keyString);
  const token = new fernet.Token({
    secret: secret,
    time: Math.floor(Date.now() / 1000),
    iv: null, // fernet will generate a random IV
  });
  return token.encode(plaintext);
}

/**
 * Check whether a username has exceeded the login attempt rate limit.
 * Uses a Firestore transaction to prevent TOCTOU races.
 * Returns { blocked: boolean, retryAfterMs: number }.
 */
async function checkRateLimit(username) {
  const docRef = db.collection("rateLimits").doc(username);

  return db.runTransaction(async (txn) => {
    const snap = await txn.get(docRef);
    if (!snap.exists) return {blocked: false, retryAfterMs: 0};

    const data = snap.data();
    const now = Date.now();
    const windowStart = now - RATE_LIMIT_WINDOW_MS;

    const recentAttempts = (data.failedAttempts || [])
        .filter((ts) => ts > windowStart);

    if (recentAttempts.length >= RATE_LIMIT_MAX_ATTEMPTS) {
      const oldestInWindow = Math.min(...recentAttempts);
      const retryAfterMs = oldestInWindow + RATE_LIMIT_WINDOW_MS - now;
      return {blocked: true, retryAfterMs};
    }
    return {blocked: false, retryAfterMs: 0};
  });
}

/**
 * Record a failed login attempt atomically using a Firestore transaction.
 * Prevents concurrent requests from bypassing the rate limit.
 */
async function recordFailedAttempt(username) {
  const docRef = db.collection("rateLimits").doc(username);

  await db.runTransaction(async (txn) => {
    const snap = await txn.get(docRef);
    const now = Date.now();
    const windowStart = now - RATE_LIMIT_WINDOW_MS;

    const existing = snap.exists ? (snap.data().failedAttempts || []) : [];
    const recent = existing.filter((ts) => ts > windowStart);
    recent.push(now);

    txn.set(docRef, {failedAttempts: recent, updatedAt: now});
  });
}

/**
 * Clear rate-limit records after a successful login.
 */
async function clearRateLimit(username) {
  const docRef = db.collection("rateLimits").doc(username);
  await docRef.delete();
}

/**
 * Look up a Firebase Auth user by the synthetic email for a given
 * Aeries username.  Returns the UserRecord or null if not found.
 */
async function findFirebaseUserByUsername(username) {
  const email = username.includes("@") ? username : `${username}@${AUTH_EMAIL_DOMAIN}`;
  try {
    const user = await admin.auth().getUserByEmail(email);
    return user;
  } catch (err) {
    if (err.code === "auth/user-not-found") {
      return null;
    }
    throw err;
  }
}

/**
 * Create a new Firebase Auth user for an Aeries teacher.
 * The Firebase password is random — actual auth is via Aeries + custom token.
 */
async function createFirebaseUser(username) {
  const email = username.includes("@") ? username : `${username}@${AUTH_EMAIL_DOMAIN}`;
  // Random password for the Firebase Auth record.  Teachers never use this;
  // they always authenticate via the Aeries flow which returns a custom token.
  const randomPassword = crypto.randomBytes(32).toString("hex");

  const user = await admin.auth().createUser({
    email: email,
    password: randomPassword,
    displayName: username,
  });
  return user;
}

// ---------------------------------------------------------------------------
// Cloud Function: authenticateTeacher
// ---------------------------------------------------------------------------

/**
 * HTTPS Callable: authenticateTeacher
 *
 * Input:  { username: string, password: string }
 * Output: { success: true, token: string, uid: string,
 *           displayName: string, validated: boolean }
 *   or    { success: false, error: string }
 *
 * The caller must exchange the returned custom token for a Firebase ID token
 * using client-side signInWithCustomToken().
 */
// ---------------------------------------------------------------------------
// Aeries session helper
// ---------------------------------------------------------------------------

/**
 * Log in to Aeries via HTTP form post and return the session cookies string.
 * Returns { cookies: string } on success or throws on failure.
 *
 * Uses the same approach as validateAeriesCredentials but captures cookies
 * so subsequent requests can make authenticated calls.
 */
async function loginToAeries(username, password) {
  const hiddenFields = await fetchAeriesFormTokens();

  const body = new URLSearchParams({
    ...hiddenFields,
    "Username_Aeries": username,
    "Password_Aeries": password,
    "btnSignIn_Aeries": "Log In",
  });

  const timeout = fetchTimeout(15000);
  try {
    const response = await fetch(AERIES_LOGIN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
      },
      body: body.toString(),
      redirect: "manual",
      signal: timeout.signal,
    });

    const isRedirect = response.status === 302 || response.status === 301;
    const location = response.headers.get("location") || "";
    const redirectedAway =
      location.length > 0 && !location.toLowerCase().includes("login");

    if (!isRedirect || !redirectedAway) {
      throw new Error("login_failed");
    }

    // Extract Set-Cookie headers (Node 20 built-in fetch uses getSetCookie)
    const rawCookies = response.headers.getSetCookie
        ? response.headers.getSetCookie()
        : [];

    const cookieString = rawCookies
        .map((c) => c.split(";")[0])
        .join("; ");

    return {cookies: cookieString, location};
  } finally {
    timeout.clear();
  }
}

/**
 * Fetch an Aeries page with the teacher's session cookies.
 * Returns the HTML text.
 */
async function aeriesGet(path, cookies) {
  const url = path.startsWith("http") ? path : `${AERIES_BASE_URL}${path}`;
  const timeout = fetchTimeout(15000);
  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Cookie": cookies,
        "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      },
      redirect: "follow",
      signal: timeout.signal,
    });
    if (!response.ok) {
      throw new Error(`Aeries returned HTTP ${response.status} for ${url}`);
    }
    return response.text();
  } finally {
    timeout.clear();
  }
}

/**
 * Parse Aeries class list page to extract period/class identifiers.
 * Returns array of { period, classId, url } objects.
 * Returns empty array if page structure is unrecognized.
 */
function parseAeriesClassList($) {
  const classes = [];

  // Aeries class list tables often have links to class roster pages.
  // Pattern: links containing "ClassRoster" or period-related hrefs.
  $("a[href]").each((_, el) => {
    const href = $(el).attr("href") || "";
    const text = $(el).text().trim();

    // Common patterns in Aeries roster links
    if (
      href.toLowerCase().includes("classroster") ||
      href.toLowerCase().includes("roster") ||
      href.toLowerCase().includes("period")
    ) {
      // Try to extract period number from link text or href
      const periodMatch = text.match(/period\s*(\d+[A-Z]?)/i) ||
        text.match(/^(\d+[A-Z]?)\s*[-–]/i) ||
        href.match(/period[=_](\d+[A-Z]?)/i) ||
        href.match(/pd[=_](\d+[A-Z]?)/i);

      if (periodMatch) {
        const fullHref = href.startsWith("http") ? href :
          href.startsWith("/") ? `https://adn.fjuhsd.org${href}` :
          `${AERIES_BASE_URL}/${href}`;
        classes.push({
          period: periodMatch[1].toUpperCase(),
          url: fullHref,
        });
      }
    }
  });

  return classes;
}

/**
 * Parse a single Aeries class roster page.
 * Returns array of { StudentID, LastName, FirstName } objects.
 * Returns empty array if page structure is unrecognized.
 */
function parseAeriesRosterPage($) {
  const students = [];

  // Aeries roster tables typically have columns for student ID and name.
  // Look for a table with student data.
  $("table tr").each((_, row) => {
    const cells = $(row).find("td");
    if (cells.length < 2) return;

    // Try to find cells that look like a student ID (numeric, 5-10 digits)
    // and a name (Last, First format).
    let studentId = null;
    let studentName = null;

    cells.each((_, cell) => {
      const text = $(cell).text().trim();
      // Student IDs in Aeries are typically 6-10 digits
      if (!studentId && /^\d{5,10}$/.test(text)) {
        studentId = text;
      }
      // Names in Aeries are typically "Last, First" or "Last, First M."
      if (!studentName && /^[A-Za-z\-']+,\s+[A-Za-z]/.test(text)) {
        studentName = text;
      }
    });

    if (studentId && studentName) {
      const comma = studentName.indexOf(",");
      const last = comma >= 0 ? studentName.slice(0, comma).trim() : studentName;
      const first = comma >= 0 ? studentName.slice(comma + 1).trim() : "";
      students.push({StudentID: studentId, LastName: last, FirstName: first});
    }
  });

  return students;
}

exports.authenticateTeacher = onCall(
    {
      region: "us-central1",
      secrets: ["FERNET_KEY"],
    },
    async (request) => {
      const {username, password} = request.data || {};

      // ------------------------------------------------------------------
      // 1. Input validation
      // ------------------------------------------------------------------
      if (!username || typeof username !== "string" || !username.trim()) {
        throw new HttpsError("invalid-argument", "username is required");
      }
      if (!password || typeof password !== "string" || !password.trim()) {
        throw new HttpsError("invalid-argument", "password is required");
      }

      const cleanUsername = username.trim().toLowerCase();

      try {
        // ------------------------------------------------------------------
        // 2. Rate-limit check (per-username)
        // ------------------------------------------------------------------
        const rateCheck = await checkRateLimit(cleanUsername);
        if (rateCheck.blocked) {
          const retryMinutes = Math.ceil(rateCheck.retryAfterMs / 60000);
          logger.warn("Rate limit exceeded", {username: cleanUsername});
          throw new HttpsError(
              "resource-exhausted",
              `Too many login attempts. Please try again in ${retryMinutes} minute(s).`,
          );
        }

        // ------------------------------------------------------------------
        // 3. Validate Aeries credentials (graceful degradation on failure)
        // ------------------------------------------------------------------
        logger.info("Validating Aeries credentials", {username: cleanUsername});
        const validation = await validateAeriesCredentials(
            cleanUsername,
            password,
        );

        const credentialsValidated = validation.valid;

        if (!credentialsValidated && validation.reason === "credentials_rejected") {
          logger.warn("Aeries credential validation failed", {
            username: cleanUsername,
            reason: validation.reason,
          });
          await recordFailedAttempt(cleanUsername);
          return {success: false, error: "Invalid Aeries credentials"};
        }

        // ------------------------------------------------------------------
        // 4. Resolve Firebase Auth user (create if first login)
        // ------------------------------------------------------------------
        let firebaseUser = await findFirebaseUserByUsername(cleanUsername);
        const isNewUser = firebaseUser === null;

        if (!credentialsValidated && validation.reason === "aeries_unreachable") {
          if (isNewUser) {
            // New user + can't validate = reject (don't store unverified creds)
            logger.warn("Aeries unreachable — rejecting new user signup", {
              username: cleanUsername,
            });
            return {
              success: false,
              error: "Aeries is currently unreachable. Please try again later.",
            };
          }
          // Existing user + can't validate = proceed with existing credentials
          logger.warn("Aeries unreachable — using existing credentials for returning user", {
            username: cleanUsername,
          });
        }

        if (isNewUser) {
          logger.info("Creating new Firebase Auth user", {
            username: cleanUsername,
          });
          firebaseUser = await createFirebaseUser(cleanUsername);
        }

        const uid = firebaseUser.uid;

        // ------------------------------------------------------------------
        // 5. Encrypt & store credentials (skip overwrite when unvalidated)
        // ------------------------------------------------------------------
        const credentialsRef = db
            .collection("teachers")
            .doc(uid)
            .collection("credentials")
            .doc("aeries");

        if (credentialsValidated) {
          // Validated credentials — safe to overwrite
          let encryptedPassword;
          try {
            encryptedPassword = fernetEncrypt(password);
          } catch (err) {
            logger.error("Fernet encryption failed", {error: err.message});
            throw new HttpsError(
                "internal",
                "Credential encryption failed. Ensure FERNET_KEY is configured.",
            );
          }

          await credentialsRef.set({
            aeriesUsername: cleanUsername,
            encryptedPassword: encryptedPassword,
            validated: true,
            updatedAt: admin.firestore.FieldValue.serverTimestamp(),
          });
        }
        // When Aeries is unreachable for an existing user, we intentionally
        // do NOT overwrite stored credentials — the previously validated
        // credentials remain intact.

        // Clear rate-limit record on successful validated login
        if (credentialsValidated) {
          await clearRateLimit(cleanUsername);
        }

        // ------------------------------------------------------------------
        // 6. Upsert teacher profile
        // ------------------------------------------------------------------
        // Ensure parent doc exists so syncAttendance can discover teachers
        await db.collection("teachers").doc(uid).set({
          aeriesUsername: cleanUsername,
          lastLogin: admin.firestore.FieldValue.serverTimestamp(),
        }, {merge: true});

        const profileRef = db
            .collection("teachers")
            .doc(uid)
            .collection("profile")
            .doc("info");

        if (isNewUser) {
          await profileRef.set({
            displayName: cleanUsername,
            aeriesUsername: cleanUsername,
            createdAt: admin.firestore.FieldValue.serverTimestamp(),
            lastLogin: admin.firestore.FieldValue.serverTimestamp(),
          });
        } else {
          await profileRef.set(
              {
                lastLogin: admin.firestore.FieldValue.serverTimestamp(),
                aeriesUsername: cleanUsername,
              },
              {merge: true},
          );
        }

        // ------------------------------------------------------------------
        // 7. Generate Firebase custom auth token
        // ------------------------------------------------------------------
        const customToken = await admin.auth().createCustomToken(uid);

        logger.info("Authentication successful", {
          uid: uid,
          username: cleanUsername,
          validated: credentialsValidated,
          isNewUser: isNewUser,
        });

        return {
          success: true,
          token: customToken,
          uid: uid,
          displayName: cleanUsername,
          validated: credentialsValidated,
        };
      } catch (err) {
        // Re-throw HttpsErrors (already structured)
        if (err instanceof HttpsError) {
          throw err;
        }

        // Log unexpected errors server-side without exposing internals
        logger.error("Unexpected error in authenticateTeacher", {
          username: cleanUsername,
          error: err.message,
          stack: err.stack,
        });

        throw new HttpsError(
            "internal",
            "Authentication failed. Please try again.",
        );
      }
    },
);

// ---------------------------------------------------------------------------
// Cloud Function: fetchRoster
// ---------------------------------------------------------------------------

/**
 * HTTPS Callable: fetchRoster
 *
 * Fetches the teacher's class rosters from Aeries via HTTP scraping.
 * Decrypts stored credentials, logs in to Aeries, navigates to roster pages,
 * and writes the results to Firestore under teachers/{uid}/rosters/{period}.
 *
 * Input:  {} (no parameters — teacher identified by Firebase Auth)
 * Output: { success: true, periods: { "1": 32, "2": 28, ... } }
 *   or    { success: false, error: "roster_requires_browser",
 *           fallback: "csv_upload" }   (if Aeries requires browser session)
 *   or    { success: false, error: string }  (other errors)
 *
 * Requires: authenticated Firebase session (request.auth must be set).
 */
exports.fetchRoster = onCall(
    {
      region: "us-central1",
      secrets: ["FERNET_KEY"],
      memory: "1GiB",
      timeoutSeconds: 300, // Puppeteer + multiple page navigations
    },
    async (request) => {
      // ----------------------------------------------------------------
      // 1. Auth check — only authenticated teachers can fetch their roster
      // ----------------------------------------------------------------
      if (!request.auth) {
        throw new HttpsError(
            "unauthenticated",
            "Must be signed in to fetch roster.",
        );
      }

      const uid = request.auth.uid;
      logger.info("fetchRoster called", {uid});

      try {
        // ----------------------------------------------------------------
        // 2. Load and decrypt Aeries credentials from Firestore
        // ----------------------------------------------------------------
        const credentialsRef = db
            .collection("teachers")
            .doc(uid)
            .collection("credentials")
            .doc("aeries");

        const credSnap = await credentialsRef.get();
        if (!credSnap.exists) {
          return {
            success: false,
            error: "no_credentials",
            message: "No Aeries credentials found. Please set up your credentials first.",
          };
        }

        const {aeriesUsername, encryptedPassword} = credSnap.data();
        if (!aeriesUsername || !encryptedPassword) {
          return {
            success: false,
            error: "incomplete_credentials",
            message: "Stored credentials are incomplete. Please re-enter your Aeries credentials.",
          };
        }

        let plaintextPassword;
        try {
          plaintextPassword = fernetDecrypt(encryptedPassword);
        } catch (err) {
          logger.error("Fernet decryption failed", {uid, error: err.message});
          return {
            success: false,
            error: "decryption_failed",
            message: "Could not decrypt stored credentials. Please re-enter your Aeries password.",
          };
        }

        // ----------------------------------------------------------------
        // 3. Scrape Aeries rosters using Puppeteer (headless Chrome)
        // ----------------------------------------------------------------
        const puppeteer = require("puppeteer");
        logger.info("Launching Puppeteer browser", {uid});
        const browser = await puppeteer.launch({
          args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
          ],
        });

        const rostersByPeriod = {};
        try {
          const page = await browser.newPage();
          await page.setViewport({width: 1600, height: 900});
          // Mask headless Chrome (Aeries blocks unsupported browsers)
          await page.setUserAgent(
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
              "AppleWebKit/537.36 (KHTML, like Gecko) " +
              "Chrome/131.0.0.0 Safari/537.36",
          );
          // Remove webdriver flag that headless Chrome sets
          await page.evaluateOnNewDocument(() => {
            Object.defineProperty(navigator, "webdriver", {
              get: () => false,
            });
          });

          // 3a. Login to Aeries via browser
          // Navigate directly to the teacher login page
          const TEACHER_LOGIN = "https://fullertonjuhsd.aeries.net/teacher/Login.aspx";
          logger.info("Navigating to Aeries teacher login", {uid});
          await page.goto(TEACHER_LOGIN, {
            waitUntil: "networkidle2",
            timeout: 30000,
          });
          logger.info("On login page", {uid, url: page.url()});

          // Wait for the username field to be ready
          await page.waitForSelector('#Username_Aeries', {
            visible: true,
            timeout: 15000,
          });

          // Click and type into each field (simulates real user input)
          await page.click('#Username_Aeries');
          await page.type('#Username_Aeries', aeriesUsername, {delay: 30});
          await page.click('#Password_Aeries');
          await page.type('#Password_Aeries', plaintextPassword, {delay: 30});

          // Debug: log what values are actually in the fields
          const debugInfo = await page.evaluate(() => ({
            ua: navigator.userAgent,
            webdriver: navigator.webdriver,
            username: document.getElementById("Username_Aeries")?.value,
            passLen: document.getElementById("Password_Aeries")?.value?.length,
          }));
          logger.info("Credentials typed", {uid, ...debugInfo});

          // Submit and wait for navigation
          await Promise.all([
            page.waitForNavigation({
              waitUntil: "networkidle2",
              timeout: 40000,
            }),
            page.click('#btnSignIn_Aeries'),
          ]);

          // Check if login succeeded (should redirect away from login)
          const postLoginUrl = page.url().toLowerCase();
          if (postLoginUrl.includes("login")) {
            // Capture error details from the page
            const pageError = await page.evaluate(() => {
              const el = document.querySelector(
                  '[class*="error"], .text-danger, [id*="Error"]',
              );
              return el ? el.textContent.trim().substring(0, 300) : "none";
            });
            const pageTitle = await page.title();
            logger.warn("Aeries login failed — still on login page", {
              uid, url: page.url(), pageError, pageTitle,
            });
            return {
              success: false,
              error: "login_failed",
              message: `Aeries login failed: ${pageError}`,
            };
          }
          logger.info("Aeries login successful via Puppeteer", {
            uid, url: page.url(),
          });

          // 3b. Navigate to Teacher Attendance page (has student grid per period)
          const currentOrigin = new URL(page.url()).origin;
          const pathPrefix = page.url().includes("/teacher/")
            ? "/teacher" : "/Aeries.net";
          const attendanceUrl =
            `${currentOrigin}${pathPrefix}/TeacherAttendance.aspx`;
          logger.info("Navigating to attendance page", {uid, attendanceUrl});

          await page.goto(attendanceUrl, {
            waitUntil: "networkidle2",
            timeout: 60000,
          });

          // Wait for the period dropdown to appear
          const periodSel = '[id*="PeriodList"]';
          await page.waitForSelector(periodSel, {
            visible: true,
            timeout: 15000,
          });

          // 3c. Get list of periods from the dropdown
          const periods = await page.evaluate((sel) => {
            const dd = document.querySelector(sel);
            if (!dd) return [];
            return Array.from(dd.options).map((o) => ({
              value: o.value,
              text: o.text.trim(),
            }));
          }, periodSel);

          if (periods.length === 0) {
            return {
              success: false,
              error: "roster_requires_browser",
              fallback: "csv_upload",
              message: "No periods found in Aeries attendance page.",
            };
          }
          logger.info("Found periods", {uid, count: periods.length});

          // 3d. Extract student roster from each period's attendance grid
          for (const period of periods) {
            try {
              // Select the period in the dropdown
              await page.select(periodSel, period.value);
              // Wait for the grid to update after period switch
              await new Promise((r) => setTimeout(r, 3000));
              await page.waitForSelector(
                  "td[data-studentid]", {timeout: 15000},
              );

              // Extract students from rows with data-studentid cells
              const students = await page.evaluate(() => {
                const result = [];
                const cells = document.querySelectorAll(
                    "td[data-studentid]",
                );
                cells.forEach((cell) => {
                  const studentId = cell.getAttribute("data-studentid");
                  const row = cell.closest("tr");
                  if (!row) return;

                  // Find name cell (Last, First format with optional parens)
                  let fullName = "";
                  row.querySelectorAll("td").forEach((td) => {
                    const t = td.textContent.trim();
                    if (/^[A-Za-z\-']+,\s+[A-Za-z]/.test(t)) {
                      fullName = t;
                    }
                  });

                  if (studentId && fullName) {
                    // Parse "Last, First M. (Preferred Preferred Last)"
                    // or "Last, First M."
                    const comma = fullName.indexOf(",");
                    const lastName = comma >= 0
                      ? fullName.slice(0, comma).trim() : fullName;
                    let rest = comma >= 0
                      ? fullName.slice(comma + 1).trim() : "";

                    // Strip parenthesized preferred-name portion
                    const parenIdx = rest.indexOf("(");
                    const firstName = parenIdx >= 0
                      ? rest.slice(0, parenIdx).trim() : rest;

                    result.push({
                      StudentID: studentId,
                      LastName: lastName,
                      FirstName: firstName,
                    });
                  }
                });
                return result;
              });

              if (students.length > 0) {
                const studentsWithPreferred = students.map((s) => ({
                  ...s,
                  preferredName: (s.FirstName || "").split(" ")[0],
                  source: "aeries",
                }));
                rostersByPeriod[period.value] = studentsWithPreferred;
                logger.info("Parsed roster for period", {
                  uid, period: period.value, count: students.length,
                });
              }
            } catch (err) {
              logger.warn("Failed to parse roster for period", {
                uid, period: period.value, error: err.message,
              });
            }
          }
        } finally {
          await browser.close();
          logger.info("Puppeteer browser closed", {uid});
        }

        if (Object.keys(rostersByPeriod).length === 0) {
          return {
            success: false,
            error: "roster_requires_browser",
            fallback: "csv_upload",
            message: "Could not extract student data from Aeries. " +
              "Please upload a roster CSV instead.",
          };
        }

        // ----------------------------------------------------------------
        // 7. Write roster data to Firestore using batch write
        //    Path: teachers/{uid}/rosters/{period}
        //    Preserves existing preferredName and manual student overrides.
        // ----------------------------------------------------------------
        const batch = db.batch();
        const rostersRef = db.collection("teachers").doc(uid).collection("rosters");

        // Load existing roster docs to preserve preferred names and manual students
        const existingSnap = await rostersRef.get();
        const existingByPeriod = {};
        existingSnap.forEach(doc => {
          existingByPeriod[doc.id] = doc.data().roster || [];
        });

        const periodCounts = {};

        for (const [period, students] of Object.entries(rostersByPeriod)) {
          // Build a map of existing student overrides (preferredName, manual additions)
          const existing = existingByPeriod[period] || [];
          const existingById = new Map(existing.map(s => [s.StudentID, s]));

          // Merge: Aeries students win for official fields, but preserve preferredName
          // if the teacher has customized it. Manual students (source: "manual") are
          // preserved only if they are NOT in the Aeries roster.
          const aeriesIds = new Set(students.map(s => s.StudentID));
          const mergedStudents = students.map(s => {
            const prev = existingById.get(s.StudentID);
            return {
              ...s,
              // Preserve any existing preferredName (teacher may have customized it);
              // fall back to first word of FirstName for new students
              preferredName: (prev && prev.preferredName)
                ? prev.preferredName
                : (s.FirstName || "").split(" ")[0],
            };
          });

          // Append manual students that are not in the Aeries roster
          existing
              .filter(s => s.source === "manual" && !aeriesIds.has(s.StudentID))
              .forEach(s => mergedStudents.push(s));

          const docRef = rostersRef.doc(period);
          batch.set(docRef, {
            roster: mergedStudents,
            updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            aeriesFetchedAt: admin.firestore.FieldValue.serverTimestamp(),
            source: "aeries",
          });

          periodCounts[period] = mergedStudents.length;
        }

        await batch.commit();
        logger.info("Roster written to Firestore", {uid, periods: Object.keys(periodCounts)});

        // ----------------------------------------------------------------
        // 8. Return success summary
        // ----------------------------------------------------------------
        return {
          success: true,
          periods: periodCounts,
          message: `Roster fetched successfully. ${Object.keys(periodCounts).length} period(s) updated.`,
        };
      } catch (err) {
        // Re-throw HttpsErrors
        if (err instanceof HttpsError) throw err;

        logger.error("Unexpected error in fetchRoster", {
          uid,
          error: err.message,
          stack: err.stack,
        });

        throw new HttpsError(
            "internal",
            "Failed to fetch roster. Please try again.",
        );
      }
    },
);

// ---------------------------------------------------------------------------
// Cloud Function: syncAttendance
// ---------------------------------------------------------------------------

/**
 * Scheduled: syncAttendance
 *
 * Runs every 10 minutes during school hours (Mon-Fri 7:40am-4:30pm).
 * Each teacher syncs roughly every 30 minutes on a staggered schedule
 * (daily random offset per teacher) to avoid overloading Aeries.
 *
 * For each teacher whose turn it is:
 *   1. Reads attendance data from Firestore
 *   2. Applies settle logic (skip periods with <5 sign-ins or <15 min elapsed)
 *   3. Logs into Aeries via Puppeteer
 *   4. Updates attendance checkboxes (Absent/Tardy/Present)
 *   5. Saves and logs results to Firestore
 */

// Settle thresholds (must match app's TARDY_AFTER_NTH)
const MIN_STUDENTS_BEFORE_SYNC = 5;
const PERIOD_SETTLE_MINUTES = 15;

// Sync window: 7:45 AM - 4:20 PM (Pacific)
const SYNC_START_MINUTE = 7 * 60 + 45; // 7:45 AM = minute 465
const SYNC_END_MINUTE = 16 * 60 + 20; // 4:20 PM = minute 980
const SYNC_INTERVAL = 30; // target interval per teacher (minutes)

/**
 * Determine if a teacher should sync on this invocation.
 * Uses a daily hash of uid+date to create a staggered offset (0–29 min)
 * so different teachers sync at different times, ~30 min apart.
 */
function shouldSyncNow(uid, now) {
  const dateStr = now.toLocaleDateString("en-CA");
  const hash = crypto.createHash("md5").update(uid + dateStr).digest();
  const offset = hash.readUInt16BE(0) % SYNC_INTERVAL;

  const minuteOfDay = now.getHours() * 60 + now.getMinutes();
  if (minuteOfDay < SYNC_START_MINUTE || minuteOfDay > SYNC_END_MINUTE) {
    return {sync: false, reason: "outside_window"};
  }

  const elapsed = minuteOfDay - SYNC_START_MINUTE;
  // Sync if we're within 10 min of this teacher's 30-min boundary
  const inWindow = ((elapsed - offset + SYNC_INTERVAL) % SYNC_INTERVAL) < 10;
  return {sync: inWindow, offset, minuteOfDay};
}

// Status normalization: app statuses → Aeries checkbox actions
function normalizeStatus(raw) {
  if (["Late", "Truant", "Cut", "Late > 20"].includes(raw)) return "Tardy";
  if (["On Time", "Present"].includes(raw)) return "Present";
  if (raw === "Absent") return "Absent";
  return raw;
}

/**
 * HTTPS Callable: triggerSync
 * Manually triggers an attendance sync for the calling teacher.
 */
exports.triggerSync = onCall(
    {
      region: "us-central1",
      secrets: ["FERNET_KEY"],
      memory: "2GiB",
      timeoutSeconds: 540,
    },
    async (request) => {
      if (!request.auth) {
        throw new HttpsError("unauthenticated", "Must be signed in.");
      }
      const uid = request.auth.uid;
      const dateStr = new Date().toLocaleDateString("en-CA");
      logger.info("triggerSync called", {uid, dateStr});

      try {
        await syncTeacher(uid, dateStr);
        return {success: true, message: "Sync complete"};
      } catch (err) {
        logger.error("triggerSync failed", {uid, error: err.message});
        return {success: false, error: err.message};
      }
    },
);

exports.syncAttendance = onSchedule(
    {
      schedule: "*/10 7-16 * * 1-5",
      timeZone: "America/Los_Angeles",
      region: "us-central1",
      secrets: ["FERNET_KEY"],
      memory: "2GiB",
      timeoutSeconds: 540,
    },
    async () => {
      const now = new Date();
      const dateStr = now.toLocaleDateString("en-CA"); // YYYY-MM-DD

      // 1. Get all teacher UIDs
      const teachersSnap = await db.collection("teachers").get();
      const teacherUids = teachersSnap.docs.map((d) => d.id);

      if (teacherUids.length === 0) {
        logger.info("No teachers found — skipping sync");
        return;
      }

      // 2. Check which teachers are due for sync this invocation
      const dueTeachers = [];
      for (const uid of teacherUids) {
        const check = shouldSyncNow(uid, now);
        if (check.sync) {
          dueTeachers.push(uid);
        }
      }

      if (dueTeachers.length === 0) {
        logger.info("No teachers due for sync this cycle", {
          dateStr, totalTeachers: teacherUids.length,
        });
        return;
      }

      logger.info("syncAttendance starting", {
        dateStr,
        dueTeachers: dueTeachers.length,
        totalTeachers: teacherUids.length,
      });

      // 3. Process each due teacher
      for (const uid of dueTeachers) {
        try {
          await syncTeacher(uid, dateStr);
        } catch (err) {
          logger.error("syncAttendance failed for teacher", {
            uid, error: err.message,
          });
        }
      }

      logger.info("syncAttendance complete", {
        dateStr, synced: dueTeachers.length,
      });
    },
);

/**
 * Sync attendance for a single teacher.
 * Reads Firestore data, launches Puppeteer, updates Aeries.
 */
async function syncTeacher(uid, dateStr) {
  logger.info("Syncing teacher", {uid, dateStr});

  // --- Load & decrypt Aeries credentials ---
  const credSnap = await db
      .collection("teachers").doc(uid)
      .collection("credentials").doc("aeries").get();

  if (!credSnap.exists) {
    logger.warn("No Aeries credentials for teacher — skipping", {uid});
    return;
  }

  const {aeriesUsername, encryptedPassword} = credSnap.data();
  if (!aeriesUsername || !encryptedPassword) {
    logger.warn("Incomplete Aeries credentials — skipping", {uid});
    return;
  }

  let plaintextPassword;
  try {
    plaintextPassword = fernetDecrypt(encryptedPassword);
  } catch (err) {
    logger.error("Fernet decryption failed — skipping teacher", {
      uid, error: err.message,
    });
    return;
  }

  // --- Read attendance data from Firestore ---
  const periods = ["0", "1", "2", "2A", "2B", "3", "4", "5", "6", "7"];
  const settledPeriods = []; // { period, students: [{StudentID, status}] }

  for (const period of periods) {
    const basePath =
      `teachers/${uid}/attendance/${dateStr}/periods/${period}`;

    const periodDoc = await db.doc(basePath).get();
    if (!periodDoc.exists) continue;

    const roster = (periodDoc.data().roster_snapshot || []);
    if (roster.length === 0) continue;

    // Get signed-in students
    const studentsSnap = await db.collection(`${basePath}/students`).get();
    const signedIn = {};
    studentsSnap.forEach((doc) => {
      signedIn[doc.id] = doc.data();
    });

    // --- Settle logic ---
    const timestamps = [];
    for (const data of Object.values(signedIn)) {
      const ts = data.Timestamp;
      if (ts && ts.toDate) {
        timestamps.push(ts.toDate());
      }
    }

    if (timestamps.length < MIN_STUDENTS_BEFORE_SYNC) {
      logger.info("Period not settled — too few sign-ins", {
        uid, period, count: timestamps.length,
      });
      continue;
    }

    timestamps.sort((a, b) => a - b);
    const nthTimestamp = timestamps[MIN_STUDENTS_BEFORE_SYNC - 1];
    const minutesElapsed = (Date.now() - nthTimestamp.getTime()) / 60000;

    if (minutesElapsed < PERIOD_SETTLE_MINUTES) {
      logger.info("Period not settled — too recent", {
        uid, period, minutesElapsed: Math.round(minutesElapsed),
      });
      continue;
    }

    // --- Build student list for this period ---
    const students = [];
    for (const student of roster) {
      const sid = student.StudentID;
      if (!sid) continue;

      if (signedIn[sid]) {
        const rawStatus = signedIn[sid].Status || "On Time";
        students.push({
          StudentID: sid,
          status: normalizeStatus(rawStatus),
          rawStatus,
        });
      } else {
        students.push({
          StudentID: sid,
          status: "Absent",
          rawStatus: "Absent",
        });
      }
    }

    settledPeriods.push({period, students});
  }

  if (settledPeriods.length === 0) {
    logger.info("No settled periods to sync", {uid});
    return;
  }

  logger.info("Settled periods ready for sync", {
    uid, periods: settledPeriods.map((p) => p.period),
  });

  // --- Launch Puppeteer and update Aeries ---
  const puppeteer = require("puppeteer");
  const browser = await puppeteer.launch({
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--no-first-run",
      "--disable-blink-features=AutomationControlled",
    ],
  });

  const syncResults = {};

  try {
    const page = await browser.newPage();
    await page.setViewport({width: 1600, height: 900});
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/131.0.0.0 Safari/537.36",
    );
    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, "webdriver", {get: () => false});
    });

    // Login to Aeries
    const TEACHER_LOGIN =
      "https://fullertonjuhsd.aeries.net/teacher/Login.aspx";
    await page.goto(TEACHER_LOGIN, {
      waitUntil: "networkidle2", timeout: 30000,
    });
    await page.waitForSelector('#Username_Aeries', {
      visible: true, timeout: 15000,
    });
    await page.click('#Username_Aeries');
    await page.type('#Username_Aeries', aeriesUsername, {delay: 30});
    await page.click('#Password_Aeries');
    await page.type('#Password_Aeries', plaintextPassword, {delay: 30});
    await Promise.all([
      page.waitForNavigation({waitUntil: "networkidle2", timeout: 40000}),
      page.click('#btnSignIn_Aeries'),
    ]);

    if (page.url().toLowerCase().includes("login")) {
      logger.error("Aeries login failed for sync", {uid});
      syncResults.error = "login_failed";
      return;
    }
    logger.info("Aeries login successful for sync", {uid});

    // Navigate to Teacher Attendance page
    const currentOrigin = new URL(page.url()).origin;
    const attendanceUrl =
      `${currentOrigin}/teacher/TeacherAttendance.aspx`;
    await page.goto(attendanceUrl, {
      waitUntil: "networkidle2", timeout: 60000,
    });
    await page.waitForSelector('[id*="PeriodList"]', {
      visible: true, timeout: 15000,
    });

    const periodSel = '[id*="PeriodList"]';

    // Process each settled period
    for (const {period, students} of settledPeriods) {
      try {
        // Select period in dropdown
        const optionExists = await page.evaluate((sel, p) => {
          const dd = document.querySelector(sel);
          return dd && Array.from(dd.options).some((o) => o.value === p);
        }, periodSel, period);

        if (!optionExists) {
          logger.warn("Period not in dropdown — skipping", {uid, period});
          syncResults[period] = {status: "skipped", reason: "not_in_dropdown"};
          continue;
        }

        await page.select(periodSel, period);
        await new Promise((r) => setTimeout(r, 3000));
        await page.waitForSelector("td[data-studentid]", {timeout: 15000});

        // Click "All Remaining Students Are Present" if visible
        try {
          const allPresentBtn = await page.evaluate(() => {
            const els = [
              ...document.querySelectorAll("a, input, button"),
            ];
            const btn = els.find((el) =>
              el.textContent.includes("All Remaining Students Are Present") &&
              el.offsetParent !== null,
            );
            if (btn) {
              btn.click();
              return true;
            }
            return false;
          });
          if (allPresentBtn) {
            logger.info("Clicked 'All Remaining Students Are Present'", {
              uid, period,
            });
            await new Promise((r) => setTimeout(r, 1000));
          }
        } catch {
          // Button not found — fine, we'll set each student individually
        }

        // Process each student
        let updates = 0;
        let skipped = 0;
        let failed = 0;

        for (const {StudentID, status} of students) {
          try {
            // Find student row by data-studentid
            const cellExists = await page.evaluate((sid) => {
              return document.querySelector(
                  `td[data-studentid="${sid}"]`,
              ) !== null;
            }, StudentID);

            if (!cellExists) {
              skipped++;
              continue;
            }

            // Check if locked
            const isLocked = await page.evaluate((sid) => {
              const cell = document.querySelector(
                  `td[data-studentid="${sid}"]`,
              );
              const row = cell?.closest("tr");
              if (!row) return false;
              const lock = row.querySelector("span[id$='lblLocked']");
              return lock && lock.offsetParent !== null;
            }, StudentID);

            if (isLocked) {
              skipped++;
              continue;
            }

            // Get current checkbox state and set as needed
            const result = await page.evaluate((sid, targetStatus) => {
              const cell = document.querySelector(
                  `td[data-studentid="${sid}"]`,
              );
              const row = cell?.closest("tr");
              if (!row) return {ok: false, reason: "no_row"};

              // Find checkboxes
              const absentBox =
                row.querySelector("span[data-cd='A'] input") ||
                row.querySelector("input[type='checkbox'][name*='Absent']");
              const tardyBox =
                row.querySelector("span[data-cd='T'] input") ||
                row.querySelector("input[type='checkbox'][name*='Tardy']");

              if (!absentBox || !tardyBox) {
                return {ok: false, reason: "no_checkboxes"};
              }

              const wasAbsent = absentBox.checked;
              const wasTardy = tardyBox.checked;
              let changed = false;

              if (targetStatus === "Absent") {
                if (!wasAbsent) {
                  absentBox.click();
                  changed = true;
                }
                if (wasTardy) {
                  tardyBox.click();
                  changed = true;
                }
              } else if (targetStatus === "Tardy") {
                if (!wasTardy) {
                  tardyBox.click();
                  changed = true;
                }
                if (wasAbsent) {
                  absentBox.click();
                  changed = true;
                }
              } else {
                // Present — uncheck both
                if (wasAbsent) {
                  absentBox.click();
                  changed = true;
                }
                if (wasTardy) {
                  tardyBox.click();
                  changed = true;
                }
              }

              return {ok: true, changed};
            }, StudentID, status);

            if (result.ok && result.changed) {
              updates++;
              // Small delay between students for UI stability
              await new Promise((r) => setTimeout(r, 200));
            }
          } catch (err) {
            failed++;
            logger.warn("Failed to process student", {
              uid, period, StudentID, error: err.message,
            });
          }
        }

        // Save if we made changes
        if (updates > 0) {
          try {
            await page.evaluate(() => {
              const btn =
                document.querySelector("input[value='Save']") ||
                document.querySelector("button[id*='Save']");
              if (btn) {
                btn.scrollIntoView();
                btn.click();
              }
            });
            await new Promise((r) => setTimeout(r, 2000));
            logger.info("Saved period", {uid, period});
          } catch (err) {
            logger.error("Failed to save period", {
              uid, period, error: err.message,
            });
          }
        }

        syncResults[period] = {
          status: "synced",
          total: students.length,
          updates,
          skipped,
          failed,
        };
        logger.info("Period sync complete", {
          uid, period, updates, skipped, failed,
        });
      } catch (err) {
        syncResults[period] = {status: "error", error: err.message};
        logger.error("Period sync failed", {
          uid, period, error: err.message,
        });
      }
    }
  } finally {
    await browser.close();
    logger.info("Puppeteer browser closed (sync)", {uid});
  }

  // --- Write sync log + status to Firestore ---
  const logRef = db
      .collection("teachers").doc(uid)
      .collection("syncLogs")
      .doc(new Date().toISOString());

  await logRef.set({
    date: dateStr,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    results: syncResults,
    settledPeriods: settledPeriods.map((p) => p.period),
  });

  // Update sync/status doc (read by the dashboard Sync tab)
  const hasError = syncResults.error ||
    Object.values(syncResults).some((r) => r.status === "error");
  const periodsProcessed = Object.values(syncResults)
      .filter((r) => r.status === "synced").length;

  const statusDoc = {
    status: hasError ? "failed" : "success",
    lastSyncTime: admin.firestore.FieldValue.serverTimestamp(),
    periodsProcessed,
    results: syncResults,
  };
  if (syncResults.error === "login_failed") {
    statusDoc.errorCategory = "credentials_invalid";
    statusDoc.error = "Aeries login failed — check your password in Settings.";
  } else if (hasError) {
    const errPeriod = Object.entries(syncResults)
        .find(([, r]) => r.status === "error");
    statusDoc.error = errPeriod ? errPeriod[1].error : "Unknown error";
  }

  await db.collection("teachers").doc(uid)
      .collection("sync").doc("status")
      .set(statusDoc);

  logger.info("Sync log written", {uid, results: syncResults});
}
