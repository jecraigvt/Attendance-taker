#!/usr/bin/env node
const readline = require('readline');
const bcrypt = require('bcrypt');
const { initDb, getDb } = require('../lib/db');

async function askQuestion(prompt) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise((resolve) => {
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(answer);
    });
  });
}

async function main() {
  await initDb();
  const name = process.argv[2] || await askQuestion('Teacher name: ');
  const email = process.argv[3] || await askQuestion('Teacher email: ');
  const password = process.argv[4] || await askQuestion('Password (will be hashed): ');

  if (!name || !email || !password) {
    console.error('Name, email, and password are required');
    process.exit(1);
  }

  const db = getDb();
  const existing = await db.get('SELECT id FROM teachers WHERE email = ?', email);
  if (existing) {
    console.error('A teacher with that email already exists.');
    process.exit(1);
  }

  const hash = await bcrypt.hash(password, 12);
  const result = await db.run('INSERT INTO teachers (name, email, password_hash) VALUES (?, ?, ?)', name, email, hash);
  console.log('Created teacher with id', result.lastID);
}

main().catch((error) => {
  console.error('Failed to seed teacher', error);
  process.exit(1);
});
