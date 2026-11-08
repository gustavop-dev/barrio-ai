#!/usr/bin/env python3
"""CI-only native shell capture and JS overlay; stdlib, no ZIP extraction.

guardar <android dir> <shell dir> <fingerprint report>
reemplazar <shell dir> <export dir> <fingerprint report> <unsigned apk>

Android res/ files are compiled by AAPT, sometimes renamed/crunched. Their exact
Metro inputs are in the native fingerprint, so preserve the compiled entries.
Only Metro's assets/ entries are replaced (including removal of obsolete files).
zipalign + apksigner must run AFTER reemplazar; the ZIP has no valid signature.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

BUNDLE = 'assets/index.android.bundle'


def resources_at(directory):
    return {
        file.relative_to(directory).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(directory.rglob('*'))
        if file.is_file() and file.relative_to(directory).as_posix() != 'raw/keep.xml'
    }


def bundle_assets(directory):
    return {'assets/' + file.relative_to(directory).as_posix(): file
            for file in sorted(directory.rglob('*')) if file.is_file()}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def guardar(android, shell, report_path):
    report = json.loads(report_path.read_text())
    generated = android / 'app/build/generated'
    res = generated / 'res/react/release'
    assets = bundle_assets(generated / 'assets/react/release')
    require(res.is_dir() and BUNDLE in assets, 'RN generated paths changed; inspect SDK/RN build output')
    require(resources_at(res) == report['resources'],
            'Gradle and export:embed produced different resources; do not cache this shell')
    source = android / 'app/build/outputs/apk/release/app-release.apk'
    with ZipFile(source) as apk:
        require(set(assets) <= set(apk.namelist()), 'Metro assets missing from the native APK')
    shell.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, shell / 'native.apk')
    # This is Expo's generated, non-secret debug keystore used by assembleRelease.
    shutil.copyfile(android / 'app/debug.keystore', shell / 'debug.keystore')
    report['bundle_assets'] = sorted(assets)
    (shell / 'metadata.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Native shell saved: {source}')


def signature(name):
    upper = name.upper()
    return upper.startswith('META-INF/') and (
        upper == 'META-INF/MANIFEST.MF' or upper.endswith(('.SF', '.RSA', '.DSA', '.EC'))
    )


def reemplazar(shell, exported, report_path, output):
    cached = json.loads((shell / 'metadata.json').read_text())
    report = json.loads(report_path.read_text())
    require(cached['fingerprint']['hash'] == report['fingerprint']['hash'], 'Native fingerprint mismatch')
    require(cached['resources'] == report['resources'] == resources_at(exported / 'res'),
            'Android resources changed; a full native build is required')
    assets = bundle_assets(exported / 'assets')
    require(BUNDLE in assets, f'Missing {BUNDLE}')
    old_assets = set(cached['bundle_assets'])
    require(BUNDLE in old_assets and all(name.startswith('assets/') for name in old_assets),
            'Invalid cached Metro asset inventory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(shell / 'native.apk') as source:
        entries = {entry.filename: entry for entry in source.infolist()}
        require(len(entries) == len(source.infolist()), 'Duplicate ZIP entries in native APK')
        require(BUNDLE in entries and old_assets <= entries.keys(), 'Cached bundle path/inventory changed')
        # First 8 bytes identify Hermes bytecode; next 4 identify the bytecode version.
        with source.open(BUNDLE) as bundle:
            native_header = bundle.read(12)
        with assets[BUNDLE].open('rb') as bundle:
            fresh_header = bundle.read(12)
        require(len(fresh_header) == 12 and fresh_header == native_header,
                'Hermes header/version differs from native APK; inspect SDK/RN/compiler')
        require(not (assets.keys() - old_assets) & entries.keys(), 'Metro would overwrite a native asset')
        # Rebuilding the ZIP drops the old APK v2/v3 signing block. Remove v1
        # signature files too; preserve META-INF services and other runtime data.
        with ZipFile(output, 'w') as target:
            for name, entry in entries.items():
                if name in old_assets or signature(name):
                    continue
                target.writestr(entry, source.read(name))
            for name, file in assets.items():
                compression = entries[name].compress_type if name in entries else ZIP_DEFLATED
                if name == BUNDLE:
                    compression = ZIP_STORED  # RN's default: memory-mappable Hermes bundle.
                target.write(file, name, compress_type=compression)
    with ZipFile(output) as apk:
        require(apk.read(BUNDLE) == assets[BUNDLE].read_bytes(), 'APK does not contain the current bundle')
        require(not (old_assets - assets.keys()) & set(apk.namelist()), 'Obsolete Metro assets survived')
        require(apk.testzip() is None, 'Corrupt repacked APK')
    print(f'Current Hermes bundle and {len(assets) - 1} companion assets written to {output}')


if __name__ == '__main__':
    command, *args = sys.argv[1:]
    if command == 'guardar' and len(args) == 3:
        guardar(*(Path(arg) for arg in args))
    elif command == 'reemplazar' and len(args) == 4:
        reemplazar(*(Path(arg) for arg in args))
    else:
        sys.exit(__doc__)
