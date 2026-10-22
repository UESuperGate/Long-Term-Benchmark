"""Derive evaluator-only certificate read readiness without editing shared fixtures."""
import json
from pathlib import Path

import task14_15_formal_core as core
from task15_device_scheduling import replace_once

READINESS = """export async function readCertificateApiWithReadiness(call, driver, observations, method) {
  for (let attempt = 1; attempt <= 80; attempt++) {
    try {
      const response = await call();
      observations.push({ method, attempt, succeeded: true });
      return response;
    } catch (error) {
      observations.push({ method, attempt, succeeded: false, code: error?.code, error: String(error) });
      if (error?.code !== 201 || attempt === 80) throw error;
      await driver.delayMs(100);
    }
  }
  throw new Error('Actual certificate API readiness exhausted');
}

"""


def derive_fixture(original):
    script = replace_once(original, "  const certificateName = 'LTB Task15 ' + config.nonce;",
        "  result.certificateApiReadiness = [];\n  const certificateName = 'LTB Task15 ' + config.nonce;")
    script = replace_once(script,
        "await certificateManager.getAllUserTrustedCertificates(certificateManager.CertScope.CURRENT_USER)",
        "await readCertificateApiWithReadiness(() => certificateManager.getAllUserTrustedCertificates("
        "certificateManager.CertScope.CURRENT_USER), driver, result.certificateApiReadiness, 'getAllUserTrustedCertificates')")
    script = replace_once(script, "await certificateManager.getUserTrustedCertificate(item.uri)",
        "await readCertificateApiWithReadiness(() => certificateManager.getUserTrustedCertificate(item.uri), "
        "driver, result.certificateApiReadiness, 'getUserTrustedCertificate')")
    return READINESS + script


def prepare(evidence):
    directory = evidence / "native-environment-fixtures"
    directory.mkdir()
    native = core.ROOT / "state_tests/runtime/arkts/native"
    original_fixture = native / "Task15NativeE2E.js"
    original_installer = native / "Task15NativeUi.install.cjs"
    fixture = directory / "Task15NativeE2E.js"
    fixture.write_text(derive_fixture(original_fixture.read_text()))
    installer = directory / "Task15NativeUi.install.cjs"
    code = original_installer.read_text().replace("__dirname", json.dumps(str(native)))
    code = replace_once(code, "const file = path.join(" + json.dumps(str(native)) + ", name), bytes = fs.readFileSync(file);",
        "const file = name === 'Task15NativeE2E.js' ? " + json.dumps(str(fixture.resolve())) +
        " : path.join(" + json.dumps(str(native)) + ", name), bytes = fs.readFileSync(file);")
    installer.write_text(code)
    core.write(directory / "manifest.json", {
        "productionModified": False, "canonicalAssertionsModified": False,
        "certificateResultFabricated": False, "permissionGrantedByEvaluator": False,
        "changes": "Bounded retries only for actual certificate API permission code 201; success requires the actual SDK call",
        "files": [{"original": str(original), "originalSha256": core.sha256(original),
                   "derived": str(derived), "derivedSha256": core.sha256(derived)}
                  for original, derived in ((original_fixture, fixture), (original_installer, installer))]})
    return fixture.resolve(), installer.resolve()


def derive_runtime(script, fixture, installer):
    target = "require(path.join(root, 'state_tests/runtime/arkts/native/Task15NativeUi.install.cjs'))"
    injection = """const originalInstaller = %s;
    if (generatedBuilderSource.split(originalInstaller).length !== 2) {
      throw new Error('Task15 evaluator installer derivation changed');
    }
    generatedBuilderSource = generatedBuilderSource.replace(originalInstaller, %s);
    """ % (json.dumps(target), json.dumps("require(" + json.dumps(str(installer)) + ")"))
    script = replace_once(script, "fs.writeFileSync(generatedBuilder, generatedBuilderSource);",
                          injection + "fs.writeFileSync(generatedBuilder, generatedBuilderSource);")
    script = replace_once(script, "path.join(root, 'state_tests/runtime/arkts/native/Task15NativeE2E.js')",
                          json.dumps(str(fixture)))
    return replace_once(script, "'logging only; shared packager source remains untouched'",
        "'logging and evaluator-only actual certificate permission readiness; production, canonical assertions and HTTPS verification unchanged'")
