#!/usr/bin/env node
const { access } = require('fs/promises');
const path = require('path');

async function main() {
  try {
    const dbPath = path.join(__dirname, '..', 'data');
    await access(dbPath);
    console.log('✅ Data directory exists at', dbPath);
    console.log('Setup check completed successfully.');
  } catch (err) {
    console.error('⚠️  Data directory missing. Run `mkdir -p server/data` before starting the server.');
    process.exitCode = 1;
  }
}

main();
