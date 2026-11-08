#!/usr/bin/env python3
"""Small, stdlib-only helpers for the CI session; no Expo/build invocation here."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def fingerprint(root, ref):
    # Hash committed native inputs, not JS, flow edits, generated android/ or node_modules/.
    # Include the build recipe and this implementation so a recipe change also invalidates the APK.
    # Keep local config plugins/modules/patches in the directories listed here.
    inputs = [
        'movil/package.json', 'movil/package-lock.json', 'movil/app.json', 'movil/app.config.js',
        'movil/app.config.ts', 'movil/eas.json', 'movil/.npmrc', 'movil/plugins', 'movil/modules',
        'movil/patches', 'movil/assets', 'movil/android', 'movil/ios', 'movil/scripts',
        'movil/metro.config.js', 'movil/babel.config.js', 'movil/react-native.config.js',
        'compartido/package.json', 'compartido/package-lock.json', 'compartido/plugins',
        'package.json', 'package-lock.json', '.npmrc',
        '.github/workflows/qa-sesion.yml', 'scripts/qa/sesion-util.py',
    ]
    tree = git(root, 'ls-tree', '-r', '-z', ref, '--', *inputs)
    return hashlib.sha256(b'qa-devclient-v1:android:x86_64:debug:OFFICE_QA_BUILD=1\0' + tree).hexdigest()


def selection(root, ref, initial):
    # Same TAG, tokenization and matching as plan.py. Only the no-tag default differs: idle.
    message = git(root, 'show', '-s', '--format=%B', ref).decode()
    tags = re.findall(r'\[qa:\s*([^\]]*)\]', message, re.I)
    if not initial.strip() and not tags:
        return []
    raw = initial.strip() or tags[-1].strip()
    wanted = [t for t in re.split(r'[\s,]+', raw) if t]
    names = sorted(p.stem for p in (root / 'movil/.maestro').glob('[0-9][0-9]-*.yaml'))
    if not wanted or any(t.lower() in ('todo', 'todos', 'all') for t in wanted):
        chosen = names
    else:
        chosen = [n for n in names if any(n == t or n.startswith(t) or t in n for t in wanted)]
    if not chosen:
        raise ValueError(f'Ningún flujo coincide con: {raw} (hay: {" ".join(names)})')
    return chosen


def prepare(root, dest, opener):
    shutil.copytree(root / 'movil/.maestro', dest)
    shutil.copyfile(opener, dest / 'comun/sesion-abrir.yaml')
    # Session-only copies: preserve launchApp/clearState/permissions and insert our opener after
    # that command's YAML block. The source flows and their release semantics stay unchanged.
    launch = re.compile(r'^( *)- launchApp(?::\s*(?:#.*)?|\s*(?:#.*)?)$')
    for path in dest.rglob('*.yaml'):
        if path.name == 'sesion-abrir.yaml':
            continue
        lines = path.read_text().splitlines(keepends=True)
        result = []
        i = 0
        while i < len(lines):
            match = launch.match(lines[i].rstrip('\n'))
            result.append(lines[i])
            i += 1
            if not match:
                continue
            indent = match[1]
            while i < len(lines):
                line = lines[i]
                if line.strip() and not line.lstrip().startswith('#') and len(line) - len(line.lstrip()) <= len(indent):
                    break
                result.append(line)
                i += 1
            relative = os.path.relpath(dest / 'comun/sesion-abrir.yaml', path.parent)
            result.append(f'{indent}- runFlow: {relative}\n')
        path.write_text(''.join(result))


def probe(root, sha):
    # A new query string alone can still get a stale Metro graph. This imported module makes the
    # actual bundle prove which reset Metro has observed. Only untracked/generated files change.
    entry = root / 'movil/node_modules/expo-router/entry.js'
    hook = "require('../../qa-sesion-head.js');\n"
    source = entry.read_text()
    if not source.startswith(hook):
        entry.write_text(hook + source)
    (root / 'movil/qa-sesion-head.js').write_text(f'globalThis.__QA_SESSION_SHA__ = "qa-sesion:{sha}";\n')


def tail(path, limit=256 * 1024):
    if not path.is_file():
        return ''
    with path.open('rb') as fh:
        fh.seek(max(0, path.stat().st_size - limit))
        return fh.read().decode(errors='replace')


def report(args):
    raw, dest = args.raw, args.dest
    dest.mkdir(parents=True)
    (dest / 'junit').mkdir()
    (dest / 'maestro').mkdir()
    rows = []
    screenshot_budget = 20 * 1024 * 1024
    records = (raw / 'flujos.txt').read_text().splitlines()
    completed = {line.split()[0] for line in records}
    # Setup errors/timeouts/cancellation still leave one explicit JUnit for every requested flow.
    selected = (raw / 'seleccion.txt').read_text().split() if (raw / 'seleccion.txt').is_file() else []
    for name in selected:
        if name not in completed:
            records.append(f'{name} 1 0')
            (raw / 'maestro' / f'{name}.log').write_text(
                f'ERROR: flujo no completado: {args.message}\n' + tail(raw / 'iteracion.log')
            )
    for line in records:
        name, code, seconds = line.split()
        code, seconds = int(code), int(seconds)
        log = tail(raw / 'maestro' / f'{name}.log')
        reason = ''
        source = raw / 'junit' / f'{name}.xml'
        try:
            xml = ET.parse(source)
            cases = list(xml.getroot().iter('testcase'))
            if not cases:
                raise ValueError('JUnit sin casos')
            for case in cases:
                for tag in ('failure', 'error', 'skipped'):
                    node = case.find(tag)
                    if node is not None:
                        code = code or 1
                        reason = (node.get('message') or node.text or tag).strip()
            shutil.copyfile(source, dest / 'junit' / source.name)
        except (OSError, ET.ParseError, ValueError):
            code = code or 1
            reason = 'Maestro no produjo un JUnit válido; ver log (fallo de arranque o timeout).'
        if code:
            error_lines = [s for s in log.splitlines() if re.search(r'FAILED|Error|failed|ERROR|TIMEOUT', s)]
            reason = reason or (error_lines[-1] if error_lines else f'Código {code}; ver log')
            # If a shell/setup failure happened outside Maestro, JUnit must still express the failure.
            if not (dest / 'junit' / f'{name}.xml').exists() or not any(
                node.tag in ('failure', 'error') for node in ET.parse(dest / 'junit' / f'{name}.xml').iter()
            ):
                suite = ET.Element('testsuite', name=name, tests='1', failures='1', time=str(seconds))
                case = ET.SubElement(suite, 'testcase', name=name, classname='qa-sesion', time=str(seconds))
                ET.SubElement(case, 'failure', message=reason).text = log[-4000:]
                ET.ElementTree(suite).write(dest / 'junit' / f'{name}.xml', encoding='utf-8', xml_declaration=True)
            # At most three screenshots of each failed flow, under a total 20 MiB cap; no videos.
            candidates = sorted((raw / 'maestro' / name).rglob('*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
            fallback = raw / 'capturas' / f'{name}.png'
            if fallback.is_file():
                candidates.insert(0, fallback)
            for i, path in enumerate(candidates[:3]):
                if path.stat().st_size > screenshot_budget:
                    continue
                screenshot_budget -= path.stat().st_size
                (dest / 'capturas' / name).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest / 'capturas' / name / f'{i}-{path.name}')
        (dest / 'maestro' / f'{name}.log').write_text(log)
        rows.append({'flujo': name, 'codigo': code, 'segundos': seconds, 'fallo': reason})
    for name in ('iteracion.log', 'metro.log', 'seed.log', 'autoprueba-fallos.log'):
        content = tail(raw / name)
        if content:
            (dest / 'maestro' / name).write_text(content)
    state = args.state
    if state == 'terminado':
        state = 'fallo' if any(r['codigo'] for r in rows) else 'ok'
    info = {'sha': args.sha, 'rama': args.branch, 'estado': state, 'mensaje': args.message,
            'inicio': args.start, 'fin': int(time.time()), 'flujos': rows}
    (dest / 'resultado.json').write_text(json.dumps(info, ensure_ascii=False, indent=2) + '\n')
    (dest / 'head-sha.txt').write_text(args.sha + '\n')
    server = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
    repo = os.environ['GITHUB_REPOSITORY']
    run = f"{server}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    lines = ['<!-- qa-sesion -->', '## QA en sesión', '', f'Estado: **{state}** · rama `{args.branch}`',
             f'Head: `{args.sha}` · [ejecución]({run})',
             f'Tiempo de la iteración: {info["fin"] - args.start} s (incluye bundle y siembra).', '',
             args.message, '', '| Flujo | Resultado | Tiempo | Paso o motivo del fallo |',
             '|---|---|---:|---|']
    for row in rows:
        reason = re.sub(r'\x1b\[[0-9;]*m', '', row['fallo']).replace('|', '\\|').replace('\n', ' ')[:300]
        lines.append(f'| {row["flujo"]} | {"PASS" if row["codigo"] == 0 else "FAIL"} | {row["segundos"]} s | {reason} |')
    if not rows:
        lines.append('| — | No se ejecutaron flujos | — | — |')
    lines += ['', f'Resultados: rama `qa-sesion/{args.branch}` (solo la última iteración).',
              'Logs limitados a 256 KiB cada uno; hasta 3 capturas por flujo fallido, 20 MiB en total.',
              'La sesión ayuda a iterar; el check final sigue siendo `qa-movil`.', '']
    (dest / 'resumen.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('huella', 'seleccionar', 'sonda'):
        p = sub.add_parser(name)
        p.add_argument('root', type=Path)
        p.add_argument('ref')
        if name == 'seleccionar':
            p.add_argument('--initial', default='')
    p = sub.add_parser('preparar')
    p.add_argument('root', type=Path)
    p.add_argument('dest', type=Path)
    p.add_argument('opener', type=Path)
    p = sub.add_parser('resumen')
    for name in ('raw', 'dest'):
        p.add_argument(name, type=Path)
    for name in ('branch', 'sha', 'state', 'message'):
        p.add_argument(name)
    p.add_argument('start', type=int)
    args = parser.parse_args()
    if args.command == 'huella':
        print(fingerprint(args.root, args.ref))
    elif args.command == 'seleccionar':
        print(' '.join(selection(args.root, args.ref, args.initial)))
    elif args.command == 'sonda':
        probe(args.root, args.ref)
    elif args.command == 'preparar':
        prepare(args.root, args.dest, args.opener)
    else:
        report(args)


if __name__ == '__main__':
    main()
