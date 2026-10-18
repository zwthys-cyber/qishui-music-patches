#!/usr/bin/env python3
"""Prepare/verify R3 on GitHub Actions, using the paths confirmed by device logs."""
import argparse
import json
import plistlib
import struct
import subprocess
import zipfile
from pathlib import Path
import ipa
from ipa import MachO, require, digest, input_files, extract
from probe import inject

MANIFEST = json.loads((Path(__file__).resolve().parents[1] / 'patches-r3.json').read_text())
ipa.MANIFEST = MANIFEST
LIBRARY = 'Frameworks/QishuiR3.dylib'
LOAD_PATH = '@executable_path/' + LIBRARY


def expected_binary(original, obj):
    patched = ipa.apply(original, ipa.replacements(obj))
    return inject(patched, dylib_path=LOAD_PATH, expected_digest=digest(patched))


def info_after(raw):
    info = plistlib.loads(raw)
    info['CFBundleDisplayName'] = '汽水R3'
    info['QSProbeBuild'] = 'R3'
    return info


def prepare(args):
    require(digest(Path(args.input).read_bytes()) == MANIFEST['ipa_sha256'], 'Wrong input IPA')
    app, executable, original = input_files(args.input)
    modified = expected_binary(original, args.object)
    work = Path(args.work)
    require(not work.exists(), 'Work directory must be new')
    extract(args.input, work)
    binary = work / executable
    ent = subprocess.run(['codesign', '-d', '--entitlements', ':-', str(binary)], capture_output=True, check=True).stdout
    (work / 'entitlements.plist').write_bytes(plistlib.dumps(plistlib.loads(ent)))
    binary.write_bytes(modified)
    binary.chmod(binary.stat().st_mode | 0o111)
    target = work / app / LIBRARY
    require(not target.exists(), 'Library already present')
    target.parent.mkdir(exist_ok=True)
    library = Path(args.dylib).read_bytes()
    MachO(library)
    target.write_bytes(library)
    target.chmod(0o755)
    info = work / app / 'Info.plist'
    info.write_bytes(plistlib.dumps(info_after(info.read_bytes())))
    print(json.dumps({'build':'R3', 'splash_sites':len(MANIFEST['patches']), 'r1_r2_wait_patches_applied':False}))


def verify(args):
    app, executable, original = input_files(args.input)
    after_app, after_executable, final = input_files(args.output)
    require((app, executable) == (after_app, after_executable), 'Changed bundle path')
    expected = expected_binary(original, args.object)
    old_macho, final_macho = MachO(expected), MachO(final)
    require(old_macho.sections == final_macho.sections, 'Section metadata changed')
    require(final_macho.cryptids() == [0], 'Encryption state changed')
    checked = []
    for key, (_, size, offset, flags) in old_macho.sections.items():
        if flags & 0xff in (1, 0xc, 0x12): continue
        require(expected[offset:offset + size] == final[offset:offset + size], 'Section mismatch: ' + str(key))
        checked.append('/'.join(key))
    _, original_size = struct.unpack_from('<II', original, 16)
    at = 32 + original_size
    cmd, size = struct.unpack_from('<II', expected, at)
    require(cmd == 0xc and expected[at:at + size] == final[at:at + size], 'Load command lost')
    with zipfile.ZipFile(args.input) as before, zipfile.ZipFile(args.output) as after:
        require(after.testzip() is None, 'Bad ZIP CRC')
        old = {n for n in before.namelist() if not n.endswith('/') and '/_CodeSignature/' not in n}
        new = {n for n in after.namelist() if not n.endswith('/') and '/_CodeSignature/' not in n}
        require(new - old == {app + '/' + LIBRARY} and not old - new, 'Unexpected new/missing resources')
        info = app + '/Info.plist'
        require(plistlib.loads(after.read(info)) == info_after(before.read(info)), 'Unexpected metadata change')
        require(after.read(app + '/' + LIBRARY) == Path(args.dylib).read_bytes(), 'Unexpected injected library bytes')
        for name in old - {executable, info}:
            require(before.read(name) == after.read(name), 'Unexpected resource change: ' + name)
    # Regression: refuse a wrong executable and a manifest with incorrect original instructions.
    wrong = bytearray(original)
    wrong[MANIFEST['patches'][0]['offset']] ^= 1
    try:
        expected_binary(bytes(wrong), args.object)
    except ValueError: pass
    else: raise ValueError('Wrong input was accepted')
    patches = ipa.replacements(args.object)
    try:
        ipa.apply(original, [(dict(p, expected='00' * len(code)), code) for p,code in patches])
    except ValueError: pass
    else: raise ValueError('Wrong site guard was accepted')
    report = dict(build='R3', status='static_signature_packaging_and_guard_checks_passed', runtime_tested=False,
                  server_reward_tested=False, input_sha256=digest(Path(args.input).read_bytes()),
                  output_sha256=digest(Path(args.output).read_bytes()), checked_sections=checked,
                  splash_patches=MANIFEST['patches'], r1_r2_wait_patches_applied=False,
                  limitations=['Video completion and server entitlement remain unverified on device', 'Front entry popup may still appear'])
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:report[k] for k in ['build','status','runtime_tested','server_reward_tested']}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for x in ['input','object','dylib','work']: p.add_argument('--'+x, required=True)
    p.set_defaults(func=prepare)
    p = sub.add_parser('verify')
    for x in ['input','object','dylib','output','report']: p.add_argument('--'+x, required=True)
    p.set_defaults(func=verify)
    args=parser.parse_args();args.func(args)

if __name__ == '__main__': main()
