const {join} = require("path");

/**
 * Puppeteer configuration for Firebase Cloud Functions.
 *
 * Cloud Build caches node_modules between builds. Without this config,
 * the Puppeteer postinstall step may be skipped on cache hits, causing
 * "Chromium not found" errors at runtime.
 *
 * @type {import("puppeteer").Configuration}
 */
module.exports = {
  cacheDirectory: join(__dirname, "node_modules", ".puppeteer_cache"),
};
