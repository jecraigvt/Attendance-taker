/**
 * Firebase Cloud Functions for Attendance Taker
 *
 * authenticateTeacher: Validates Aeries credentials, encrypts the password
 * with Fernet, stores credentials in Firestore, and issues a Firebase
 * custom auth token so the teacher can sign in to the app.
 *
 * fetchRoster: Fetches the teacher's class rosters from Aeries via HTTP
 * scraping (form-based ASP.NET session), then writes them to Firestore.
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

const AERIES_BASE_URL = "https://adn.fjuhsd.org/Aeries.net";
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
 * Fetch the Aeries login page and extract ASP.NET form tokens.
 * Returns { viewstate, viewstateGenerator, eventValidation } or throws.
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

    const viewstate = $("input[name='__VIEWSTATE']").val() || "";
    const viewstateGenerator =
      $("input[name='__VIEWSTATEGENERATOR']").val() || "";
    const eventValidation =
      $("input[name='__EVENTVALIDATION']").val() || "";

    return {viewstate, viewstateGenerator, eventValidation};
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
    const tokens = await fetchAeriesFormTokens();

    const body = new URLSearchParams({
      "__VIEWSTATE": tokens.viewstate,
      "__VIEWSTATEGENERATOR": tokens.viewstateGenerator,
      "__EVENTVALIDATION": tokens.eventValidation,
      "portalAccountUsername": username,
      "portalAccountPassword": password,
      "LoginButton": "Log In",
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

      // Some Aeries deployments return 200 with redirect in meta or JS.
      // Also check if the response URL (after following) differs from login.
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
  const tokens = await fetchAeriesFormTokens();

  const body = new URLSearchParams({
    "__VIEWSTATE": tokens.viewstate,
    "__VIEWSTATEGENERATOR": tokens.viewstateGenerator,
    "__EVENTVALIDATION": tokens.eventValidation,
    "portalAccountUsername": username,
    "portalAccountPassword": password,
    "LoginButton": "Log In",
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
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Cookie": cookies,
      "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
    redirect: "follow",
  });
  return response.text();
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
      timeoutSeconds: 120, // Roster scraping can be slow
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
        // 3. Log in to Aeries via HTTP
        // ----------------------------------------------------------------
        logger.info("Logging in to Aeries", {uid, username: aeriesUsername});
        let session;
        try {
          session = await loginToAeries(aeriesUsername, plaintextPassword);
        } catch (err) {
          if (err.message === "login_failed") {
            return {
              success: false,
              error: "login_failed",
              message: "Aeries login failed. Your credentials may have changed.",
            };
          }
          // Aeries unreachable
          return {
            success: false,
            error: "aeries_unreachable",
            message: "Could not connect to Aeries. Please try again later.",
          };
        }

        const {cookies} = session;
        logger.info("Aeries login successful", {uid, hasCookies: cookies.length > 0});

        // ----------------------------------------------------------------
        // 4. Navigate to the Aeries class/roster listing page
        //
        // Aeries.net (FJUHSD) typically uses:
        //   /Aeries.net/Classes.aspx  — teacher's class list
        //   /Aeries.net/Student/StudentRoster.aspx?ClassNumber=XXX — per-class roster
        //
        // We try several known paths and look for roster content.
        // ----------------------------------------------------------------
        const candidatePaths = [
          "/Classes.aspx",
          "/Schedule/TeacherClasses.aspx",
          "/TeacherClasses.aspx",
        ];

        let classListHtml = null;
        let classListPath = null;

        for (const path of candidatePaths) {
          try {
            const html = await aeriesGet(path, cookies);
            const $ = cheerio.load(html);

            // Check if we got something useful (not a login redirect)
            const pageTitle = $("title").text().toLowerCase();
            const isLoginPage = pageTitle.includes("login") ||
              html.toLowerCase().includes("portalaccountusername");

            if (!isLoginPage && html.length > 1000) {
              // Check for class/roster content indicators
              const hasClassContent =
                html.toLowerCase().includes("period") &&
                (
                  html.toLowerCase().includes("class") ||
                  html.toLowerCase().includes("roster") ||
                  html.toLowerCase().includes("student")
                );

              if (hasClassContent) {
                classListHtml = html;
                classListPath = path;
                logger.info("Found class list page", {uid, path});
                break;
              }
            }
          } catch (err) {
            logger.warn("Failed to fetch Aeries path", {uid, path, error: err.message});
          }
        }

        if (!classListHtml) {
          logger.warn("Could not find Aeries class list — returning browser fallback", {uid});
          return {
            success: false,
            error: "roster_requires_browser",
            fallback: "csv_upload",
            message: "Automatic roster fetch is not available for your school's Aeries setup. Please upload a roster CSV instead.",
          };
        }

        // ----------------------------------------------------------------
        // 5. Parse the class list to find individual roster pages
        // ----------------------------------------------------------------
        let $ = cheerio.load(classListHtml);
        const classList = parseAeriesClassList($);

        if (classList.length === 0) {
          logger.warn("No classes found in Aeries class list — returning browser fallback", {uid});
          return {
            success: false,
            error: "roster_requires_browser",
            fallback: "csv_upload",
            message: "Could not parse class list from Aeries. Please upload a roster CSV instead.",
          };
        }

        logger.info("Found classes in Aeries", {uid, count: classList.length});

        // ----------------------------------------------------------------
        // 6. Fetch each class roster and parse student data
        // ----------------------------------------------------------------
        const rostersByPeriod = {};

        for (const cls of classList) {
          try {
            const rosterHtml = await aeriesGet(cls.url, cookies);
            $ = cheerio.load(rosterHtml);
            const students = parseAeriesRosterPage($);

            if (students.length > 0) {
              // Add preferredName field defaulting to first word of FirstName
              const studentsWithPreferred = students.map(s => ({
                ...s,
                preferredName: (s.FirstName || "").split(" ")[0],
                source: "aeries",
              }));
              rostersByPeriod[cls.period] = studentsWithPreferred;
              logger.info("Parsed roster for period", {
                uid,
                period: cls.period,
                count: students.length,
              });
            }
          } catch (err) {
            logger.warn("Failed to parse roster for period", {
              uid,
              period: cls.period,
              error: err.message,
            });
          }
        }

        if (Object.keys(rostersByPeriod).length === 0) {
          return {
            success: false,
            error: "roster_requires_browser",
            fallback: "csv_upload",
            message: "Could not extract student data from Aeries. Please upload a roster CSV instead.",
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
