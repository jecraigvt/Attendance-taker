/**
 * migrate-to-tenants.js
 *
 * Copies Jeremy's attendance data from the flat Firestore path to a per-teacher
 * path structure. Idempotent — safe to re-run without duplicating records.
 *
 * Source root : artifacts/attendance-taker-56916/public/
 * Target root : teachers/{jeremy_uid}/
 *
 * Usage:
 *   FIREBASE_KEY_PATH=/path/to/service-account.json node migrate-to-tenants.js
 *
 * If FIREBASE_KEY_PATH is not set, defaults to the attendance-sync directory.
 */

'use strict';

const admin = require('firebase-admin');
const path  = require('path');
const fs    = require('fs');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const PROJECT_ID = 'attendance-taker-56916';
const APP_ID     = 'attendance-taker-56916';
const SRC_ROOT   = `artifacts/${APP_ID}/public`;

const DEFAULT_KEY = path.join(
  __dirname,
  'attendance-sync',
  'attendance-key.json'
);
const KEY_PATH = process.env.FIREBASE_KEY_PATH || DEFAULT_KEY;

const JEREMY_EMAIL       = 'jeremy@rollcall.local';
const JEREMY_DISPLAY     = 'Mr. Ramos';

// Firestore batch write limit
const BATCH_LIMIT = 499;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function log(msg)  { console.log(`[migrate] ${msg}`); }
function warn(msg) { console.warn(`[WARN]    ${msg}`); }
function err(msg)  { console.error(`[ERROR]   ${msg}`); }

/**
 * Commit the current batch and return a fresh one.
 */
async function flushBatch(db, batch, ops) {
  if (ops > 0) {
    await batch.commit();
    log(`  Flushed batch of ${ops} writes.`);
  }
  return { batch: db.batch(), ops: 0 };
}

/**
 * Copy a single Firestore document from src to dst.
 * Skips the write if the target document already exists.
 * Returns 'written' | 'skipped'.
 */
async function copyDoc(db, srcRef, dstRef, batchHolder) {
  const dstSnap = await dstRef.get();
  if (dstSnap.exists) {
    log(`  already migrated: ${dstRef.path}`);
    return 'skipped';
  }

  const srcSnap = await srcRef.get();
  if (!srcSnap.exists) {
    warn(`  source missing:   ${srcRef.path} — skipping`);
    return 'skipped';
  }

  batchHolder.batch.set(dstRef, srcSnap.data());
  batchHolder.ops += 1;

  if (batchHolder.ops >= BATCH_LIMIT) {
    const result = await flushBatch(db, batchHolder.batch, batchHolder.ops);
    batchHolder.batch = result.batch;
    batchHolder.ops   = result.ops;
  }

  return 'written';
}

// ---------------------------------------------------------------------------
// Init Firebase Admin
// ---------------------------------------------------------------------------

function initFirebase() {
  if (!fs.existsSync(KEY_PATH)) {
    err(`Service account key not found at: ${KEY_PATH}`);
    err('Set FIREBASE_KEY_PATH env var or place key at the default path.');
    process.exit(1);
  }

  const serviceAccount = require(KEY_PATH);
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
    projectId: PROJECT_ID,
  });

  log(`Firebase initialized. Project: ${PROJECT_ID}`);
  log(`Key: ${KEY_PATH}`);
}

// ---------------------------------------------------------------------------
// Resolve (or create) Jeremy's UID
// ---------------------------------------------------------------------------

async function resolveJeremyUid() {
  log(`\nResolving teacher UID for ${JEREMY_EMAIL}…`);

  let userRecord;
  try {
    userRecord = await admin.auth().getUserByEmail(JEREMY_EMAIL);
    log(`  Found existing Auth user: ${userRecord.uid}`);
  } catch (e) {
    if (e.code === 'auth/user-not-found') {
      log(`  No Auth user found — creating one…`);
      userRecord = await admin.auth().createUser({
        email:       JEREMY_EMAIL,
        displayName: JEREMY_DISPLAY,
        emailVerified: true,
      });
      log(`  Created Auth user: ${userRecord.uid}`);
    } else {
      throw e;
    }
  }

  return userRecord.uid;
}

// ---------------------------------------------------------------------------
// Write teacher profile doc
// ---------------------------------------------------------------------------

async function writeTeacherProfile(db, uid) {
  const profileRef = db.doc(`teachers/${uid}/profile`);
  const snap = await profileRef.get();

  if (snap.exists) {
    log(`\nTeacher profile already exists — skipping.`);
    return;
  }

  log(`\nWriting teacher profile at teachers/${uid}/profile…`);
  await profileRef.set({
    displayName: JEREMY_DISPLAY,
    email:       JEREMY_EMAIL,
    createdAt:   admin.firestore.FieldValue.serverTimestamp(),
    migratedAt:  admin.firestore.FieldValue.serverTimestamp(),
    tardyConfig: {
      method:        'nth-student',
      nthStudent:    5,
      graceMinutes:  8,
    },
  });
  log(`  Profile written.`);
}

// ---------------------------------------------------------------------------
// Migrate config (single doc)
// ---------------------------------------------------------------------------

async function migrateConfig(db, uid, batchHolder) {
  log(`\nMigrating config…`);
  const srcRef = db.doc(`${SRC_ROOT}/config`);
  const dstRef = db.doc(`teachers/${uid}/config`);
  const result = await copyDoc(db, srcRef, dstRef, batchHolder);
  return { total: 1, written: result === 'written' ? 1 : 0, skipped: result === 'skipped' ? 1 : 0 };
}

// ---------------------------------------------------------------------------
// Migrate rosters
// ---------------------------------------------------------------------------

async function migrateRosters(db, uid, batchHolder) {
  log(`\nMigrating rosters…`);
  const srcCol = db.collection(`${SRC_ROOT}/rosters/periods`);
  const periods = await srcCol.get();

  let written = 0;
  let skipped = 0;

  for (const periodDoc of periods.docs) {
    const srcRef = db.doc(`${SRC_ROOT}/rosters/periods/${periodDoc.id}`);
    const dstRef = db.doc(`teachers/${uid}/rosters/periods/${periodDoc.id}`);
    const result = await copyDoc(db, srcRef, dstRef, batchHolder);
    if (result === 'written') written++;
    else skipped++;
  }

  log(`  Rosters: ${written} written, ${skipped} skipped (of ${periods.size} total)`);
  return { total: periods.size, written, skipped };
}

// ---------------------------------------------------------------------------
// Migrate attendance
// ---------------------------------------------------------------------------

async function migrateAttendance(db, uid, batchHolder) {
  log(`\nMigrating attendance records…`);

  // List all date subcollections under data/attendance/
  const attendanceRoot = db.collection(`${SRC_ROOT}/data/attendance`);
  const dateDocs = await attendanceRoot.get();

  let totalDocs    = 0;
  let writtenDocs  = 0;
  let skippedDocs  = 0;

  for (const dateDoc of dateDocs.docs) {
    const date = dateDoc.id;
    log(`  Date: ${date}`);

    // Copy period meta doc
    const metaSrcRef = db.doc(`${SRC_ROOT}/data/attendance/${date}/meta/currentPeriod`);
    const metaDstRef = db.doc(`teachers/${uid}/attendance/${date}/meta/currentPeriod`);
    const metaResult = await copyDoc(db, metaSrcRef, metaDstRef, batchHolder);
    totalDocs++;
    if (metaResult === 'written') writtenDocs++;
    else skippedDocs++;

    // List periods for this date
    const periodsCol = db.collection(`${SRC_ROOT}/data/attendance/${date}/periods`);
    const periodDocs = await periodsCol.get();

    for (const periodDoc of periodDocs.docs) {
      const period = periodDoc.id;

      // List students for this period
      const studentsCol = db.collection(
        `${SRC_ROOT}/data/attendance/${date}/periods/${period}/students`
      );
      const studentDocs = await studentsCol.get();

      for (const studentDoc of studentDocs.docs) {
        const srcRef = db.doc(
          `${SRC_ROOT}/data/attendance/${date}/periods/${period}/students/${studentDoc.id}`
        );
        const dstRef = db.doc(
          `teachers/${uid}/attendance/${date}/periods/${period}/students/${studentDoc.id}`
        );
        const result = await copyDoc(db, srcRef, dstRef, batchHolder);
        totalDocs++;
        if (result === 'written') writtenDocs++;
        else skippedDocs++;
      }
    }
  }

  log(`  Attendance: ${writtenDocs} written, ${skippedDocs} skipped (of ${totalDocs} total)`);
  return { total: totalDocs, written: writtenDocs, skipped: skippedDocs };
}

// ---------------------------------------------------------------------------
// Count verification
// ---------------------------------------------------------------------------

async function countDocs(db, collectionPath, depth = 1) {
  // Recursively count all documents under a path up to a given depth.
  // For our use case we just need flat collection counts.
  const col = db.collection(collectionPath);
  const snap = await col.get();
  return snap.size;
}

async function verifyMigration(db, uid) {
  log(`\n${'='.repeat(60)}`);
  log(`VERIFICATION TABLE`);
  log(`${'='.repeat(60)}`);

  const checks = [
    {
      name:    'Rosters (periods)',
      srcPath: `${SRC_ROOT}/rosters/periods`,
      dstPath: `teachers/${uid}/rosters/periods`,
    },
    {
      name:    'Attendance (date-level docs)',
      srcPath: `${SRC_ROOT}/data/attendance`,
      dstPath: `teachers/${uid}/attendance`,
    },
  ];

  let allMatch = true;

  // Header
  console.log(
    `${'Collection'.padEnd(35)} ${'OLD'.padStart(6)} ${'NEW'.padStart(6)} ${'STATUS'.padStart(8)}`
  );
  console.log('-'.repeat(60));

  for (const check of checks) {
    const oldCount = await countDocs(db, check.srcPath);
    const newCount = await countDocs(db, check.dstPath);
    const match    = oldCount === newCount;
    const status   = match ? 'OK' : 'MISMATCH';
    if (!match) allMatch = false;

    console.log(
      `${check.name.padEnd(35)} ${String(oldCount).padStart(6)} ${String(newCount).padStart(6)} ${status.padStart(8)}`
    );
  }

  // Config (single doc)
  const configSrc = await db.doc(`${SRC_ROOT}/config`).get();
  const configDst = await db.doc(`teachers/${uid}/config`).get();
  const configMatch = configSrc.exists === configDst.exists;
  if (!configMatch) allMatch = false;
  console.log(
    `${'Config (doc)'.padEnd(35)} ${String(configSrc.exists ? 1 : 0).padStart(6)} ${String(configDst.exists ? 1 : 0).padStart(6)} ${(configMatch ? 'OK' : 'MISMATCH').padStart(8)}`
  );

  console.log('-'.repeat(60));
  log(`=`.repeat(60));

  if (allMatch) {
    log(`All counts match. Migration verified.`);
  } else {
    err(`Count mismatches detected. Review the table above.`);
  }

  return allMatch;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`  Attendance Taker — Tenant Migration Script`);
  console.log(`  ${new Date().toISOString()}`);
  console.log(`${'='.repeat(60)}\n`);

  initFirebase();
  const db  = admin.firestore();
  const uid = await resolveJeremyUid();

  log(`\nTeacher UID: ${uid}`);
  log(`Source root: ${SRC_ROOT}`);
  log(`Target root: teachers/${uid}/`);

  // Write teacher profile (idempotent — skips if exists)
  await writeTeacherProfile(db, uid);

  // Shared mutable batch holder
  const batchHolder = { batch: db.batch(), ops: 0 };

  // Migrate each collection
  const configStats    = await migrateConfig(db, uid, batchHolder);
  const rosterStats    = await migrateRosters(db, uid, batchHolder);
  const attendanceStats = await migrateAttendance(db, uid, batchHolder);

  // Flush any remaining writes
  if (batchHolder.ops > 0) {
    await flushBatch(db, batchHolder.batch, batchHolder.ops);
  }

  // Summary
  log(`\nMigration complete.`);
  log(`  Config:     ${configStats.written} written, ${configStats.skipped} skipped`);
  log(`  Rosters:    ${rosterStats.written} written, ${rosterStats.skipped} skipped`);
  log(`  Attendance: ${attendanceStats.written} written, ${attendanceStats.skipped} skipped`);

  // Verification
  const allMatch = await verifyMigration(db, uid);

  if (!allMatch) {
    err(`\nVerification failed — see MISMATCH rows above.`);
    process.exit(1);
  }

  log(`\nDone. Old paths are untouched at: ${SRC_ROOT}`);
  process.exit(0);
}

main().catch((e) => {
  err(`Unexpected error: ${e.message}`);
  console.error(e);
  process.exit(1);
});
