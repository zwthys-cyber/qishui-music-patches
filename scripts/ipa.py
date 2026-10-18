#!/usr/bin/env python3
"""Version-locked patch preparation and independent packaged-IPA checks (Actions only)."""
import argparse
import hashlib
import json
import plistlib
import struct
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'patches.json').read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MachO:
    def __init__(self, data):
        self.data = data
        require(data[:4] == bytes.fromhex('cffaedfe'), 'Expected thin little-endian Mach-O 64')
        require(struct.unpack_from('<I', data, 4)[0] == 0x100000c, 'Expected ARM64')
        self.sections = {}
        self.commands = []
        pos = 32
        count, size = struct.unpack_from('<II', data, 16)
        for _ in range(count):
            cmd, length = struct.unpack_from('<II', data, pos)
            require(length >= 8 and pos + length <= 32 + size, 'Invalid load command')
            self.commands.append((cmd, pos))
            if cmd == 0x19:
                nsects = struct.unpack_from('<I', data, pos + 64)[0]
                for index in range(nsects):
                    at = pos + 72 + index * 80
                    name = data[at:at + 16].split(b'\0')[0].decode()
                    segment = data[at + 16:at + 32].split(b'\0')[0].decode()
                    address, length2, offset = struct.unpack_from('<QQI', data, at + 32)
                    flags = struct.unpack_from('<I', data, at + 64)[0]
                    self.sections[(segment, name)] = (address, length2, offset, flags)
            pos += length

    def cryptids(self):
        return [struct.unpack_from('<I', self.data, p + 16)[0]
                for c, p in self.commands if c == 0x2c]

    def symbol_bytes(self, name, length):
        text_address, text_size, text_offset, _ = self.sections[('__TEXT', '__text')]
        for cmd, pos in self.commands:
            if cmd != 2:
                continue
            symoff, count, stroff, _ = struct.unpack_from('<IIII', self.data, pos + 8)
            for index in range(count):
                at = symoff + index * 16
                string_index, kind, section, _, value = struct.unpack_from('<IBBHQ', self.data, at)
                if not string_index:
                    continue
                start = stroff + string_index
                symbol = self.data[start:self.data.index(b'\0', start)].decode()
                if symbol != '_' + name:
                    continue
                require(kind & 0xe == 0xe and section == 1, 'Patch must be a defined __text symbol')
                require(text_address <= value and value + length <= text_address + text_size, 'Stub outside text')
                offset = text_offset + value - text_address
                return self.data[offset:offset + length]
        raise ValueError('Missing compiled stub: ' + name)


def input_files(path):
    with zipfile.ZipFile(path) as archive:
        infos = [n for n in archive.namelist() if n.count('/') == 2 and n.endswith('/Info.plist')]
        require(len(infos) == 1, 'Expected exactly one top-level app')
        info = plistlib.loads(archive.read(infos[0]))
        require(info['CFBundleIdentifier'] == MANIFEST['bundle_id'], 'Wrong bundle identifier')
        require(info['CFBundleShortVersionString'] == MANIFEST['version'], 'Wrong app version')
        require(info['CFBundleExecutable'] == MANIFEST['executable'], 'Wrong executable')
        app_path = infos[0].rsplit('/', 1)[0]
        executable_path = app_path + '/' + info['CFBundleExecutable']
        return app_path, executable_path, archive.read(executable_path)


def replacements(obj):
    macho = MachO(Path(obj).read_bytes())
    result = []
    expected_stubs = {
        'qs_skip_wait': bytes.fromhex('1f2003d5'),
        'qs_full_progress': struct.pack('<I', 0x1e22c120),
        'qs_completed_watch_time': struct.pack('<IIII', 0xd2e81588, 0xf2c40008, 0x9e670100, 0xd65f03c0),
        'qs_finish_native': struct.pack('<I', 0x14000026),
        'qs_one_second': bytes.fromhex('00106e1ec0035fd61f2003d5'),
    }
    for patch in MANIFEST['patches']:
        size = len(bytes.fromhex(patch['expected']))
        code = macho.symbol_bytes(patch['symbol'], size)
        require(code == expected_stubs[patch['symbol']], 'Assembler output differs from reviewed instruction encoding')
        result.append((patch, code))
    return result


def apply(data, patches):
    require(digest(data) == MANIFEST['executable_sha256'], 'Executable SHA256 mismatch; refusing to patch')
    macho = MachO(data)
    require(macho.cryptids() == [0], 'Executable must already be decrypted')
    _, text_size, text_offset, _ = macho.sections[('__TEXT', '__text')]
    result = bytearray(data)
    covered = set()
    for patch, code in patches:
        offset = patch['offset']
        expected = bytes.fromhex(patch['expected'])
        require(data[offset:offset + len(expected)] == expected, 'Original bytes mismatch: ' + patch['name'])
        require(text_offset <= offset and offset + len(code) <= text_offset + text_size, 'Patch outside executable section')
        region = set(range(offset, offset + len(code)))
        require(not covered.intersection(region), 'Overlapping patches')
        covered.update(region)
        result[offset:offset + len(code)] = code
    require(len(result) == len(data), 'Patch changed executable size')
    require(all(a == b or i in covered for i, (a, b) in enumerate(zip(data, result))), 'Unexpected executable changes')
    return bytes(result)


def extract(path, output):
    output = Path(output)
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            relative = PurePosixPath(entry.filename)
            require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe ZIP member')
            mode = entry.external_attr >> 16
            require(mode & 0o170000 != 0o120000, 'Unexpected symlink in IPA')
            target = output.joinpath(*relative.parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
                if mode & 0o777:
                    target.chmod(mode & 0o777)


def prepare(args):
    require(digest(Path(args.input).read_bytes()) == MANIFEST['ipa_sha256'], 'IPA SHA256 mismatch')
    app_path, executable_path, data = input_files(args.input)
    patches = replacements(args.object)
    patched = apply(data, patches)
    work = Path(args.work)
    require(not work.exists(), 'Work directory must be new')
    extract(args.input, work)
    executable = work / executable_path
    entitlements = subprocess.run(['codesign', '-d', '--entitlements', ':-', str(executable)],
                                  capture_output=True, check=True).stdout
    require(entitlements.strip(), 'Input signature contains no readable entitlements')
    parsed = plistlib.loads(entitlements)
    require(isinstance(parsed, dict), 'Invalid entitlement plist')
    (work / 'entitlements.plist').write_bytes(plistlib.dumps(parsed))
    executable.write_bytes(patched)
    executable.chmod(executable.stat().st_mode | 0o111)
    # Exercise failure paths in CI, including a changed binary and a wrong patch-site guard.
    altered = bytearray(data)
    altered[patches[0][0]['offset']] ^= 1
    try:
        apply(bytes(altered), patches)
    except ValueError:
        pass
    else:
        raise ValueError('Wrong-binary rejection failed')
    wrong_patch = [(dict(p, expected='00' * len(code)), code) for p, code in patches]
    try:
        apply(data, wrong_patch)
    except ValueError:
        pass
    else:
        raise ValueError('Wrong-site rejection failed')
    (work / 'paths.json').write_text(json.dumps({'app': app_path, 'executable': executable_path}))
    print(json.dumps({'prepared': app_path, 'patches': len(patches), 'negative_checks': 'passed'}))


def package(args):
    work = Path(args.work)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted((work / 'Payload').rglob('*')):
            if file.is_file():
                archive.write(file, file.relative_to(work))
    print(output)


def verify(args):
    _, executable_path, original = input_files(args.input)
    _, output_path, final = input_files(args.output)
    require(executable_path == output_path, 'App path changed')
    expected = apply(original, replacements(args.object))
    original_macho, final_macho = MachO(expected), MachO(final)
    require(final_macho.cryptids() == [0], 'Encryption state changed')
    require(original_macho.sections == final_macho.sections, 'Section table changed')
    checked_sections = []
    for key, (_, size, offset, flags) in original_macho.sections.items():
        if flags & 0xff in (1, 0xc, 0x12):  # zero-fill sections have no file bytes
            continue
        require(expected[offset:offset + size] == final[offset:offset + size], 'Signed section content differs: ' + str(key))
        checked_sections.append('/'.join(key))
    with zipfile.ZipFile(args.input) as before, zipfile.ZipFile(args.output) as after:
        require(after.testzip() is None, 'Output ZIP has a corrupt entry')
        names_before = {n for n in before.namelist() if not n.endswith('/')}
        names_after = {n for n in after.namelist() if not n.endswith('/')}
        changed_resources = []
        for name in names_before | names_after:
            if name == executable_path or '/_CodeSignature/' in name:
                continue
            require(name in names_before and name in names_after, 'Resource added or removed: ' + name)
            require(before.read(name) == after.read(name), 'Resource changed: ' + name)
        resource_count = len(names_after) - 1
    report = {
        'status': 'static_and_packaging_checks_passed',
        'runtime_tested': False,
        'server_reward_tested': False,
        'input_sha256': digest(Path(args.input).read_bytes()),
        'output_sha256': digest(Path(args.output).read_bytes()),
        'checked_sections': checked_sections,
        'resource_count': resource_count,
        'patches': [dict(p, replacement=code.hex()) for p, code in replacements(args.object)],
        'limitations': ['Experimental local waiting changes only', 'Actual playback and server rewards need a TrollStore device'],
    }
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'runtime_tested': False, 'patches': len(report['patches'])}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--input', required=True)
    p.add_argument('--object', required=True)
    p.add_argument('--work', required=True)
    p.set_defaults(func=prepare)
    p = sub.add_parser('package')
    p.add_argument('--work', required=True)
    p.add_argument('--output', required=True)
    p.set_defaults(func=package)
    p = sub.add_parser('verify')
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--object', required=True)
    p.add_argument('--report', required=True)
    p.set_defaults(func=verify)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
