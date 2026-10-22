"""Task15-local per-scenario device leases; packaging never owns the device."""
import json
import time


def replace_once(script, before, after):
    if script.count(before) != 1:
        raise RuntimeError("Task15 device scheduling derivation changed: " + before[:70])
    return script.replace(before, after)


def owned_lock(script):
    script = replace_once(script, "fs.mkdirSync(lock);", """fs.mkdirSync(lock);
        fs.writeFileSync(path.join(lock, 'owner.json'), JSON.stringify({
          taskId: '15_account_deactivation', serial, pid: process.pid, token: 'task15-' + process.pid
        }), { flag: 'wx' });""")
    return replace_once(script, "fs.rmdirSync(lock);", """{ const ownerPath = path.join(lock, 'owner.json');
      const owner = JSON.parse(fs.readFileSync(ownerPath));
      if (owner.pid !== process.pid || owner.token !== 'task15-' + process.pid) {
        throw new Error('Task15 refuses to release a foreign canonical device lease');
      }
      fs.unlinkSync(ownerPath);
      fs.rmdirSync(lock); }""")


def base_case_leases(script, *, serial, deadline):
    epoch_ms = int((time.time() + max(0, deadline - time.monotonic())) * 1000)
    script = replace_once(script, "const serial = targets[0];", "const serial = " + json.dumps(serial) + ";\n"
        "  if (!targets.includes(serial)) throw new Error('Requested Task15 target is disconnected');")
    start = script.index("  const lockWaitStartedAt = Date.now();")
    end = script.index("\n  const startedAt = new Date();", start)
    acquire = script[start:end]
    acquire = acquire.replace("  const lockWaitStartedAt = Date.now();", "    lockWaitStartedAt = Date.now();")
    acquire = acquire.replace("lockWaitStartedAt + 3600 * 1000", str(epoch_ms))
    script = script[:start] + "  let lockWaitStartedAt = Date.now();\n  let locked = false;\n" + \
        "  async function acquireCaseLease() {\n" + acquire + "\n    locked = true;\n  }\n" + script[end:]
    inventory = """    const apps = run(['shell', 'bm', 'dump', '-a']);
    if (apps.split('\\n').some(line => line.trim() === bundleName)) {
      throw new Error('Task15 base candidate already installed before evaluator-owned execution');
    }
"""
    script = replace_once(script, inventory, "")
    script = replace_once(script, """      currentCase = spec.caseId;
      if (!run(['install'""", """      currentCase = spec.caseId;
      await acquireCaseLease();
      try {
""" + inventory + "      if (!run(['install'")
    script = replace_once(script, """      appOwned = false;
    }
    report.status = 'passed';""", """      appOwned = false;
      } finally {
        for (const remote of remoteLayouts.splice(0)) {
          run(['shell', 'rm', '-f', remote]);
          report.diagnostics.cleanup.remoteLayoutsRemoved += 1;
        }
        if (appOwned) {
          run(['uninstall', bundleName], [0], 120000);
          appOwned = false;
        }
        releaseCaseLease();
        await sleep(200);
      }
    }
    report.status = 'passed';""")
    script = replace_once(script,
        "try { fs.rmdirSync(lock); report.diagnostics.cleanup.deviceLockRemoved = true; } catch (_) {}",
        "if (locked) releaseCaseLease();")
    anchor = "  const startedAt = new Date();"
    script = replace_once(script, anchor, """  function releaseCaseLease() {
    if (!locked) return;
    fs.rmdirSync(lock);
    locked = false;
    report.diagnostics.cleanup.deviceLockRemoved = true;
  }
""" + anchor)
    # The unchanged startup gets a transport positive control before UI sampling.
    startup = "run(['shell', 'aa', 'start', '-a', 'EntryAbility', '-b', bundleName, '-m', 'entry']);"
    script = replace_once(script, startup, """run(['shell', 'power-shell', 'wakeup']);
      const launch = """ + startup + "\n      if (!launch.includes('start ability successfully')) throw new Error('Task15 original app launch rejected');")
    return owned_lock(script)


def native_scenario_lease(script, *, deadline):
    epoch_ms = int((time.time() + max(0, deadline - time.monotonic())) * 1000)
    script = replace_once(script, "const lockDeadline = lockWaitStartedAt + taskTimeoutMs;",
                          "const lockDeadline = " + str(epoch_ms) + ";")
    return owned_lock(script)
