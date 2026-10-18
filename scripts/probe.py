#!/usr/bin/env python3
"""Build a version-locked observational IPA; execute only on GitHub Actions."""
import argparse
import json
import plistlib
import struct
import subprocess
import zipfile
from pathlib import Path
from ipa import MANIFEST, MachO, require, digest, extract, input_files, package

LIBRARY = 'Frameworks/QishuiProbeD1.dylib'
DYLIB_PATH = '@executable_path/' + LIBRARY
BUILD = 'D1'


def inject(data, dylib_path=DYLIB_PATH, expected_digest=MANIFEST['executable_sha256']):
    macho = MachO(data)
    require(digest(data) == expected_digest, 'Wrong executable')
    count, size = struct.unpack_from('<II', data, 16)
    pos = 32 + size
    raw = dylib_path.encode() + b'\0'
    length = (24 + len(raw) + 7) & ~7
    first_section = min(o for _, s, o, flags in macho.sections.values() if s and o and flags & 0xff not in (1, 0xc, 0x12))
    require(pos + length <= first_section, 'Insufficient header padding')
    require(data[pos:pos + length] == b'\0' * length, 'Nonzero load-command padding')
    for cmd, at in macho.commands:
        if cmd in (0xc, 0x80000018, 0x8000001f):
            name_at = at + struct.unpack_from('<I', data, at + 8)[0]
            require(data[name_at:data.index(b'\0', name_at)].decode() != dylib_path, 'Already injected')
    command = struct.pack('<IIIIII', 0xc, length, 24, 0, 0x10000, 0x10000) + raw
    command += b'\0' * (length - len(command))
    result = bytearray(data)
    struct.pack_into('<II', result, 16, count + 1, size + length)
    result[pos:pos + length] = command
    require(len(result) == len(data), 'Unexpected file size change')
    require(result[:16] == data[:16] and result[24:pos] == data[24:pos] and result[pos + length:] == data[pos + length:], 'Unexpected byte change')
    require(MachO(bytes(result)).sections == macho.sections, 'Injection changed section metadata')
    return bytes(result)


def edited_info(original):
    info = plistlib.loads(original)
    info['CFBundleDisplayName'] = '汽水诊断D1'
    info['QSProbeBuild'] = BUILD
    return info


def prepare(args):
    require(digest(Path(args.input).read_bytes()) == MANIFEST['ipa_sha256'], 'Wrong IPA')
    app, executable, data = input_files(args.input)
    require(MachO(data).cryptids() == [0], 'Input is encrypted')
    patched = inject(data)
    # Reject previously modified / unrelated executable before writing any package.
    bad = bytearray(data)
    bad[-1] ^= 1
    try:
        inject(bytes(bad))
    except ValueError:
        pass
    else:
        raise ValueError('Wrong-input rejection failed')
    work = Path(args.work)
    require(not work.exists(), 'Work directory must be new')
    extract(args.input, work)
    binary = work / executable
    original_entitlements = subprocess.run(['codesign', '-d', '--entitlements', ':-', str(binary)], capture_output=True, check=True).stdout
    entitlements = plistlib.loads(original_entitlements)
    (work / 'entitlements.plist').write_bytes(plistlib.dumps(entitlements))
    binary.write_bytes(patched)
    binary.chmod(binary.stat().st_mode | 0o111)
    lib = work / app / LIBRARY
    require(not lib.exists(), 'Input already has probe')
    lib.parent.mkdir(exist_ok=True)
    library_data = Path(args.dylib).read_bytes()
    MachO(library_data)
    lib.write_bytes(library_data)
    lib.chmod(0o755)
    info_path = work / app / 'Info.plist'
    info_path.write_bytes(plistlib.dumps(edited_info(info_path.read_bytes())))
    print(json.dumps({'build': BUILD, 'mode': 'observational_only', 'timer_patches_applied': False, 'input_rejection_check': 'passed'}))


def verify(args):
    app, executable, original = input_files(args.input)
    after_app, after_executable, output = input_files(args.output)
    require((app, executable) == (after_app, after_executable), 'App path changed')
    expected = inject(original)
    old, final = MachO(expected), MachO(output)
    require(old.sections == final.sections, 'Section metadata changed')
    checked = []
    for key, (_, size, offset, flags) in old.sections.items():
        if flags & 0xff in (1, 0xc, 0x12):
            continue
        require(expected[offset:offset + size] == output[offset:offset + size], 'App code or data section changed: ' + str(key))
        checked.append('/'.join(key))
    # The new dependency must survive signing at the same appended command slot.
    _, original_cmd_size = struct.unpack_from('<II', original, 16)
    at = 32 + original_cmd_size
    cmd, size = struct.unpack_from('<II', expected, at)
    require(cmd == 0xc and expected[at:at + size] == output[at:at + size], 'Probe dependency lost during signing')
    with zipfile.ZipFile(args.input) as before, zipfile.ZipFile(args.output) as after:
        require(after.testzip() is None, 'ZIP CRC failure')
        old_names = {n for n in before.namelist() if not n.endswith('/') and '/_CodeSignature/' not in n}
        new_names = {n for n in after.namelist() if not n.endswith('/') and '/_CodeSignature/' not in n}
        require(new_names - old_names == {app + '/' + LIBRARY} and not old_names - new_names, 'Unexpected resource changes')
        info_path = app + '/Info.plist'
        require(plistlib.loads(after.read(info_path)) == edited_info(before.read(info_path)), 'Unexpected Info.plist changes')
        for name in old_names - {executable, info_path}:
            require(before.read(name) == after.read(name), 'Unrelated resource changed: ' + name)
        require(after.read(app + '/' + LIBRARY) == Path(args.dylib).read_bytes(), 'Probe library differs from signed build')
    report = dict(build=BUILD, mode='observational_only', runtime_tested=False, app_sections_unchanged=checked,
                  app_code_patches_applied=False, input_sha256=digest(Path(args.input).read_bytes()),
                  output_sha256=digest(Path(args.output).read_bytes()), status='signature_and_packaging_checks_passed')
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ['build', 'mode', 'runtime_tested', 'status']}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ['input', 'dylib', 'work']: p.add_argument('--' + name, required=True)
    p.set_defaults(func=prepare)
    p = sub.add_parser('verify')
    for name in ['input', 'output', 'dylib', 'report']: p.add_argument('--' + name, required=True)
    p.set_defaults(func=verify)
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
