#!/usr/bin/env node
'use strict';

// Matrix room-directory lookup is an authenticated-client operation in this
// benchmark episode, but the Matrix endpoint itself is public and the SDK does
// not attach an access token. Derive V2 from the sealed V1 implementation so
// the only behavior change is the admission rule for that endpoint.
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');

const sourceFile = path.join(__dirname, 'task14_matrix_provider_v1.cjs');
let source = fs.readFileSync(sourceFile, 'utf8');

function replaceOnce(before, after) {
  if (source.split(before).length !== 2) {
    throw new Error('Task14 provider V2 derivation changed: ' + before);
  }
  source = source.replace(before, after);
}

replaceOnce("    provider: 'task14_matrix_provider_v1',", "    provider: 'task14_matrix_provider_v2',");
replaceOnce('  let baseUrl;', '  let baseUrl;\n  let successfulLoginSequence = 0;');
replaceOnce(
  "        return reply(record, response, 200, {\n          user_id: expected.userId,",
  "        successfulLoginSequence = record.sequence;\n        return reply(record, response, 200, {\n          user_id: expected.userId,"
);
replaceOnce(
  "        if (request.method !== 'GET' || !hasProductionAuth(record)) {\n          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'Missing evaluator access token' }, 'unauthorized');\n        }\n        if (!config)",
  "        const admittedPublicDirectoryRequest = request.method === 'GET' && record.tls.encrypted &&\n          successfulLoginSequence > 0 && successfulLoginSequence < record.sequence;\n        record.directoryAdmission = { mode: 'tls_after_valid_login', admitted: admittedPublicDirectoryRequest,\n          successfulLoginSequence };\n        if (!admittedPublicDirectoryRequest) {\n          return reply(record, response, 401, { errcode: 'M_UNKNOWN_TOKEN', error: 'No admitted evaluator login episode' }, 'unauthorized');\n        }\n        if (!config)"
);

const derived = new Module(__filename + ':derived', module);
derived.filename = sourceFile;
derived.paths = module.paths;
derived._compile(source, sourceFile);
module.exports = derived.exports;
