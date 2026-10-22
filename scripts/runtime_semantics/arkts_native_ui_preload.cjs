'use strict';

// Extend only the temporary test process's page list. Installed SDK code and
// candidate page bodies are unchanged; the test harness remains the entry page.
const Module = require('node:module');
const fs = require('node:fs');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
  const exports = originalLoad.apply(this, arguments);
  if (request.endsWith('replace-unit-test-index-file.js') && exports.ReplaceUnitTestIndexFile &&
      !exports.ReplaceUnitTestIndexFile.prototype.nativeCandidatePages) {
    const prototype = exports.ReplaceUnitTestIndexFile.prototype;
    const original = prototype.replacePagesInPreview;
    prototype.nativeCandidatePages = true;
    prototype.replacePagesInPreview = function(logger, pages) {
      const candidate = JSON.parse(fs.readFileSync(process.env.LTB_NATIVE_UI_PAGES, 'utf8'));
      const combined = [...new Set([...pages, ...candidate.src])];
      return original.call(this, logger, combined);
    };
  }
  return exports;
};
