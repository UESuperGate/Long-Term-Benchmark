"""V7 exact native startup/ack identity, including same-JVM init-script reentry."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

ROOT = Path(__file__).resolve().parents[2]
HOOK = Path(__file__).with_name('task17_gradle_native_gate_v7.init.gradle')
OPTION = '-Dorg.gradle.native=false'
UNSUPPORTED = 'org.gradle.internal.nativeintegration.jna.UnsupportedEnvironment'
PROPERTIES_SYNTAX = 'task17.strict-flat-properties.v2'
DIST = Path.home() / '.gradle/wrapper/dists/gradle-8.10-bin/deqhafrv1ntovfmgh0nh3npr9/gradle-8.10'
JARS = {
    'gradle-launcher-8.10.jar': 'cd0d96e515426305a534f5ea33db3643277725c9b3397d59a95acc2f454ec85b',
    'gradle-daemon-main-8.10.jar': '1b48a4f789635f5e825e3f40d60a3cc3c28db2c7178e5d465835ec04215461f4',
    'gradle-client-services-8.10.jar': '9adbf2213a15b8de5a9f0a64e5a269cd3d927ac67892fd0306a17d5ccd270adc',
    'gradle-daemon-server-8.10.jar': '931daa495f153b00b2fb6f42730269491dd0984dc692d9684e09fe2ce424d2ad',
    'gradle-native-8.10.jar': '546545f19c0feb25c8d7ca36fee4660c714660e38f68d2c3e401e3f487810234',
    'native-platform-0.22-milestone-26.jar': '727e0ca0a6f5ca865b56c98c73dd47cab9c38781672956ac1f80197249f2a423',
}


class NativeGateError(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise NativeGateError('Task17 native gate: ' + reason)


def is_gradle(argv):
    return Path(argv[0]).name == 'gradlew' or Path(argv[0]).absolute() == DIST / 'bin/gradle'


def properties(raw):
    """Accept only the reviewed flat-line subset, NOT full Java Properties syntax.

    Reject continuations and controls rather than approximate Java natural-line
    comment semantics or Python's broader splitlines behavior. No values emitted.
    """
    text = raw.decode('iso-8859-1')
    require(all(char in '\r\n' or (ord(char) >= 0x20 and not 0x7f <= ord(char) <= 0x9f)
                for char in text), 'unreviewed control character in bootstrap properties')
    logical = []
    for line in re.split(r'\r\n|\r|\n', text):
        line = line.lstrip(' ')
        if not line:
            continue
        if line[0] in '#!':
            require('\\' not in line, 'unreviewed backslash in properties comment')
            continue
        trailing = len(line) - len(line.rstrip('\\'))
        require(trailing % 2 == 0, 'properties continuation is outside the reviewed subset')
        logical.append(line)

    def decode(value):
        result, index = [], 0
        while index < len(value):
            char = value[index]
            index += 1
            if char == '\\':
                require(index < len(value), 'incomplete properties escape')
                char = value[index]
                index += 1
                if char == 'u':
                    digits = value[index:index + 4]
                    require(len(digits) == 4 and all(c in '0123456789abcdefABCDEF' for c in digits),
                            'invalid properties Unicode escape')
                    char, index = chr(int(digits, 16)), index + 4
                else:
                    char = {'t': '\t', 'n': '\n', 'r': '\r', 'f': '\f'}.get(char, char)
            result.append(char)
        decoded = ''.join(result)
        require(all(ord(char) >= 0x20 and not 0x7f <= ord(char) <= 0x9f
                    and not 0xd800 <= ord(char) <= 0xdfff for char in decoded),
                'unreviewed decoded control/surrogate in bootstrap properties')
        return decoded

    rows = {}
    for line in logical:
        if not line or line[0] in '#!':
            continue
        index, escaped = 0, False
        while index < len(line):
            char = line[index]
            if not escaped and char in '=:\t \f':
                break
            escaped = not escaped if char == '\\' else False
            index += 1
        key = decode(line[:index])
        rest = line[index:].lstrip(' \t\f')
        if rest.startswith(('=', ':')):
            rest = rest[1:].lstrip(' \t\f')
        value = decode(rest)
        require(key not in rows or not (key.startswith('org.gradle.') or key.startswith('systemProp.org.gradle.')),
                'ambiguous duplicate bootstrap property')
        rows[key] = value
    return rows


def check_properties(values, jdk):
    for key in ('org.gradle.native', 'systemProp.org.gradle.native', 'org.gradle.daemon', 'systemProp.org.gradle.daemon'):
        require(key not in values or values[key] == 'false', 'conflicting bootstrap property: ' + key)
    for key in ('org.gradle.jvmargs', 'systemProp.org.gradle.jvmargs'):
        require(key not in values or values[key] == '-Xmx4g -Dfile.encoding=UTF-8 -XX:+UseG1GC',
                'conflicting bootstrap property: ' + key)
    for key in ('org.gradle.java.home', 'systemProp.org.gradle.java.home'):
        require(key not in values or Path(values[key]).resolve() == jdk.resolve(),
                'conflicting bootstrap property: ' + key)
    require('org.gradle.daemon.registry.base' not in values and 'systemProp.org.gradle.daemon.registry.base' not in values,
            'unreviewed daemon registry override')


def prepare(argv, env, cwd, output, name, remaining, deadline, record):
    """Return a new argv/env; never silently repair an unset startup property."""
    require(env.get('JAVA_TOOL_OPTIONS') == OPTION, 'explicit inherited native=false missing')
    require(env.get('GRADLE_OPTS') == '-Dorg.gradle.daemon=false ' + OPTION, 'launcher native gate missing')
    require(not any(env.get(key) for key in ('JAVA_OPTS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS')),
            'unreviewed JVM environment override')
    source = Path(cwd)
    props = source / 'gradle/wrapper/gradle-wrapper.properties'
    text = props.read_text()
    require(re.search(r'^distributionUrl=https\\://services\.gradle\.org/distributions/gradle-8\.10-bin\.zip$',
                      text, re.MULTILINE), 'unsupported wrapper/distribution')
    require('distributionSha256Sum=5b9c5eb3f9fc2c94abaea57d90bd78747ca117ddbbf96c859d3741181a12bf2a' in text,
            'distribution checksum missing')
    project_properties = properties((source / 'gradle.properties').read_bytes())
    require(project_properties.get('org.gradle.jvmargs') == '-Xmx4g -Dfile.encoding=UTF-8 -XX:+UseG1GC',
            'unreviewed build JVM arguments; do not lower original heap')
    require(env.get('JAVA_HOME'), 'explicit reviewed JAVA_HOME missing')
    jdk = Path(env['JAVA_HOME'])
    check_properties(project_properties, jdk)
    require(not (source / 'gradle/gradle-daemon-jvm.properties').exists(), 'unreviewed daemon JVM criteria')
    home = Path(env.get('GRADLE_USER_HOME') or Path.home() / '.gradle').absolute()
    require(not env.get('GRADLE_USER_HOME') or Path(env['GRADLE_USER_HOME']).is_absolute(), 'relative Gradle user home')
    require(Path(argv[0]).absolute() == DIST / 'bin/gradle' or
            home.resolve() == (Path.home() / '.gradle').resolve(), 'wrapper would resolve an unpinned distribution home')
    user_properties = home / 'gradle.properties'
    user_record = {'path': str(user_properties), 'exists': False}
    if user_properties.exists() or user_properties.is_symlink():
        require(not user_properties.is_symlink() and user_properties.is_file()
                and user_properties.stat().st_size <= 1024 * 1024, 'unsafe/oversized user bootstrap properties')
        check_properties(properties(user_properties.read_bytes()), jdk)
        user_record = dict(record(user_properties, deadline), exists=True)
    for item in argv[1:]:
        require(not str(item).startswith(('-Dorg.gradle.native', '-Dorg.gradle.jvmargs',
                                         '-Dorg.gradle.java.home', '-g', '--gradle-user-home')),
                'unexpected bootstrap override in argv')
    pins = []
    launcher = record(DIST / 'bin/gradle', deadline)
    require(launcher['sha256'] == '156b2ce0875cb4ca404b904aa6dcc1c13c684a1985767b298c0f32e82ef3187b',
            'unreviewed cached launcher')
    for name_in_dist, expected in JARS.items():
        remaining(deadline)
        item = record(DIST / 'lib' / name_in_dist, deadline)
        require(item['sha256'] == expected, 'unreviewed cached implementation: ' + name_in_dist)
        pins.append(item)
    directory = Path(output) / 'gradle-native-bootstrap' / name
    directory.mkdir(parents=True, exist_ok=False)
    context = {'protocol': 'task17.gradle-native-gate.v7', 'nonce': uuid.uuid4().hex,
               'receipt': str(directory / 'jvm.json'), 'ack': str(directory / 'host-ack.json'),
               'hostProof': str(directory / 'host-proof.json'), 'supportedJars': pins,
               'cachedLauncher': launcher,
               'hook': record(HOOK, deadline), 'wrapperProperties': record(props, deadline),
               'actualGradleUserHome': str(home), 'userBootstrapProperties': user_record,
               'propertiesSyntaxPolicy': PROPERTIES_SYNTAX,
               'startupEnvironment': {'JAVA_TOOL_OPTIONS': OPTION,
                                      'GRADLE_OPTS': '-Dorg.gradle.daemon=false ' + OPTION,
                                      'JAVA_HOME': str(jdk), 'otherJvmOverridesAbsent': True},
               'originalGradleProperties': record(source / 'gradle.properties', deadline),
               'requiresReceipt': '--version' not in argv}
    actual_env = dict(env, TASK17_NATIVE_GATE_NONCE=context['nonce'],
                      TASK17_NATIVE_GATE_RECEIPT=context['receipt'], TASK17_NATIVE_GATE_ACK=context['ack'])
    actual_argv = list(argv)
    if context['requiresReceipt']:
        actual_argv[1:1] = ['--init-script', str(HOOK)]
    return actual_argv, actual_env, context


def inspect_live(context, process, record, deadline):
    """A hook blocks before settings/build evaluation until this live host check."""
    path = Path(context['receipt'])
    if not path.exists():
        return None
    require(stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink() and path.stat().st_size <= 65536,
            'invalid receipt file/type/size')
    row = json.loads(path.read_bytes())
    require(row.get('protocol') == context['protocol'] and row.get('nonce') == context['nonce'], 'receipt identity')
    require(row.get('gradleVersion') == '8.10' and row.get('nativeProperty') == 'false'
            and row.get('processEnvironmentClass') == UNSUPPORTED and row.get('nativeIntegrations') is False
            and row.get('maybeDetachProcess') is False, 'native-disable implementation not observed')
    require(row.get('inheritedJavaToolOptions') == OPTION, 'build JVM did not inherit startup option')
    require(isinstance(row.get('javaHome'), str) and Path(row['javaHome']).resolve() ==
            Path(context['startupEnvironment']['JAVA_HOME']).resolve(), 'actual JVM home changed')
    require(isinstance(row.get('gradleUserHome'), str) and Path(row['gradleUserHome']).resolve() ==
            Path(context['actualGradleUserHome']).resolve(), 'actual daemon registry home changed')
    require(type(row.get('pid')) is int and row['pid'] > 1, 'missing actual JVM PID')
    args = row.get('vmArgs')
    require(isinstance(args, list) and '-Xmx4g' in args and '-XX:+UseG1GC' in args and OPTION in args,
            'actual original heap/GC/startup native option missing')
    try:
        pgid, sid = os.getpgid(row['pid']), os.getsid(row['pid'])
    except ProcessLookupError as error:
        raise NativeGateError('JVM vanished before live host verification') from error
    require(pgid == process.pid and sid == process.pid, 'JVM escaped owned wrapper PGID/SID')
    return {'protocol': context['protocol'], 'nonce': context['nonce'], 'receipt': record(path, deadline),
            'actualJvmPid': row['pid'], 'wrapperPid': process.pid, 'actualPgid': pgid, 'actualSid': sid,
            'actualJvmParentPid': row.get('parentPid'),
            'sameOwnedGroupAndSession': True, 'jvmMode': 'launcher' if row['pid'] == process.pid else 'child',
            'unsupportedEnvironmentNoDetachObserved': True}


def check_bound_inputs(context, record, deadline):
    for item in (context['supportedJars'] + [context['cachedLauncher'], context['hook'],
                                           context['wrapperProperties'], context['originalGradleProperties']]):
        require(record(item['path'], deadline) == item, 'bootstrap input changed after launch')
    user = context['userBootstrapProperties']
    path = Path(user['path'])
    if user['exists']:
        require(dict(record(path, deadline), exists=True) == user, 'user bootstrap properties changed after launch')
    else:
        require(not path.exists() and not path.is_symlink(), 'user bootstrap properties appeared after launch')
    if context['requiresReceipt']:
        return validate_reentry(context, record, deadline)
    return None


def read_small(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536,
            'missing/unsafe native acceptance artifact')
    return path.read_bytes()


def validate_reentry(context, record, deadline):
    """Recompute immutable first receipt, original host ack and every init event."""
    proof_raw = read_small(context['hostProof'])
    require(hashlib.sha256(proof_raw).hexdigest() == context['originalHostProofSha256'], 'original live host proof changed')
    proof = json.loads(proof_raw)
    receipt = read_small(context['receipt'])
    receipt_sha = hashlib.sha256(receipt).hexdigest()
    require(record(context['receipt'], deadline) == proof['receipt'], 'startup receipt was rewritten')
    row = json.loads(receipt)
    require(row['nonce'] == context['nonce'] and row['protocol'] == context['protocol'] and
            row['pid'] == proof['actualJvmPid'] and row['parentPid'] == proof['actualJvmParentPid'],
            'startup identity no longer matches live host proof')
    ack = read_small(context['ack'])
    ack_sha = hashlib.sha256(ack).hexdigest()
    require(ack_sha == context['originalHostAckSha256'], 'original host ack bytes changed')
    require(json.loads(ack) == {'nonce': context['nonce'], 'receiptSha256': receipt_sha}, 'host ack identity changed')
    accepted_path = Path(context['receipt'] + '.accepted-ack.json')
    accepted_raw = read_small(accepted_path)
    expected = {'protocol': 'task17.native-gate-acceptance.v7', 'nonce': context['nonce'],
                'pid': row['pid'], 'parentPid': row['parentPid'],
                'startupReceiptSha256': receipt_sha, 'hostAckSha256': ack_sha}
    require(accepted_raw == (json.dumps(expected, separators=(',', ':')) + '\n').encode(),
            'first accepted acknowledgement bytes/identity changed')
    events = []
    directory = Path(context['receipt']).parent / 'evaluations'
    require(directory.is_dir() and not directory.is_symlink(), 'missing native init evaluations')
    for path in sorted(directory.iterdir()):
        require(path.suffix == '.json', 'unexpected native init evaluation artifact')
        event = json.loads(read_small(path))
        require(set(event) == {'protocol', 'nonce', 'pid', 'parentPid', 'startupReceiptSha256',
                               'hostAckSha256', 'mode', 'gradleInstanceIdentity', 'currentDir'},
                'incomplete/unknown init evaluation fields')
        require(event['protocol'] == 'task17.native-gate-evaluation.v7' and
                all(event[key] == expected[key] for key in ('nonce', 'pid', 'parentPid',
                                                           'startupReceiptSha256', 'hostAckSha256')),
                'init reentry identity/bytes differ')
        require(event['mode'] in {'initial', 'identical-reentry'} and
                type(event['gradleInstanceIdentity']) is int and isinstance(event['currentDir'], str),
                'unknown init evaluation mode/actual owner')
        events.append({'record': record(path, deadline), 'actual': event})
    require(events and sum(event['actual']['mode'] == 'initial' for event in events) == 1,
            'missing/duplicate first initialization')
    return {'firstAcceptedAck': record(accepted_path, deadline), 'originalHostAck': record(context['ack'], deadline),
            'startupReceipt': record(context['receipt'], deadline), 'evaluations': events,
            'identicalReentries': sum(event['actual']['mode'] == 'identical-reentry' for event in events)}


def acknowledge(context, proof, atomic):
    atomic(Path(context['hostProof']), proof)
    context['originalHostProofSha256'] = hashlib.sha256((json.dumps(proof, indent=2) + '\n').encode()).hexdigest()
    body = {'nonce': context['nonce'], 'receiptSha256': proof['receipt']['sha256']}
    atomic(Path(context['ack']), body)
    context['originalHostAckSha256'] = hashlib.sha256((json.dumps(body, indent=2) + '\n').encode()).hexdigest()
