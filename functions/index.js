/**
 * Firebase Cloud Functions for Attendance Taker
 *
 * authenticateTeacher: Validates Aeries credentials, encrypts the password
 * with Fernet, stores credentials in Firestore, and issues a Firebase
 * custom auth token so the teacher can sign in to the app.
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

admin.initializeApp();
const db = admin.firestore();

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AERIES_LOGIN_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx";

// Fake email domain used to create Firebase Auth accounts for teachers.
// Aeries usernames are not real email addresses, so we manufacture one.
const AUTH_EMAIL_DOMAIN = "aeries.attendance.local";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Fetch the Aeries login page and extract ASP.NET form tokens.
 * Returns { viewstate, viewstateGenerator, eventValidation } or throws.
 */
async function fetchAeriesFormTokens() {
  const response = await fetch(AERIES_LOGIN_URL, {
    method: "GET",
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
    },
    redirect: "manual",
  });

  const html = await response.text();
  const $ = cheerio.load(html);

  const viewstate = $("input[name='__VIEWSTATE']").val() || "";
  const viewstateGenerator =
    $("input[name='__VIEWSTATEGENERATOR']").val() || "";
  const eventValidation =
    $("input[name='__EVENTVALIDATION']").val() || "";

  return {viewstate, viewstateGenerator, eventValidation};
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

    const response = await fetch(AERIES_LOGIN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (compatible; AttendanceTaker/2.0)",
      },
      body: body.toString(),
      redirect: "manual",
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
  } catch (err) {
    logger.warn("Aeries validation failed with error — proceeding without validation", {
      error: err.message,
    });
    return {valid: false, reason: "aeries_unreachable"};
  }
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
    time: Date.now(),
    iv: null, // fernet will generate a random IV
  });
  return token.encode(plaintext);
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
  const randomPassword =
    admin.auth().createCustomToken // guard just to use admin reference
      ? Math.random().toString(36).slice(2) +
        Math.random().toString(36).slice(2)
      : "not-used";

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
        // 2. Validate Aeries credentials (graceful degradation on failure)
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
          return {success: false, error: "Invalid Aeries credentials"};
        }

        if (!credentialsValidated && validation.reason === "aeries_unreachable") {
          // Proceed anyway — credentials will be validated when cloud sync runs
          logger.warn("Aeries unreachable — proceeding without real-time validation", {
            username: cleanUsername,
          });
        }

        // ------------------------------------------------------------------
        // 3. Resolve Firebase Auth user (create if first login)
        // ------------------------------------------------------------------
        let firebaseUser = await findFirebaseUserByUsername(cleanUsername);
        const isNewUser = firebaseUser === null;

        if (isNewUser) {
          logger.info("Creating new Firebase Auth user", {
            username: cleanUsername,
          });
          firebaseUser = await createFirebaseUser(cleanUsername);
        }

        const uid = firebaseUser.uid;

        // ------------------------------------------------------------------
        // 4. Encrypt Aeries password with Fernet
        // ------------------------------------------------------------------
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

        // ------------------------------------------------------------------
        // 5. Store encrypted credentials in Firestore (admin SDK — bypasses rules)
        // ------------------------------------------------------------------
        const credentialsRef = db
            .collection("teachers")
            .doc(uid)
            .collection("credentials")
            .doc("aeries");

        await credentialsRef.set({
          aeriesUsername: cleanUsername,
          encryptedPassword: encryptedPassword,
          validated: credentialsValidated,
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        });

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
