#!/usr/bin/env python3
"""Report of a QA run (.github/workflows/qa-movil.yml), standard library only.

Usage: informe.py <qa-artefactos>. Reads flujos.txt, junit/*.xml, maestro/*.log and logcat/logcat-completo.txt;
writes logcat/logcat-app.txt, logcat/logcat-errores.txt, informe.html and resultado.txt ('ok' or 'fallo'), and
prints the Markdown summary (job summary and PR comment) on stdout.
"""
import gzip
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

APP = 'co.projectapp.office'
# threadtime: "11-07 21:03:04.123  1234  1250 E ReactNativeJS: message"
LINE = re.compile(r'^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+)\s+([VDIWEFA])\s+(.*?)\s*: (.*)$')
START = re.compile(r'Start proc (\d+):' + re.escape(APP) + r'[/ ]')
CRASH = re.compile(r'FATAL EXCEPTION|Fatal signal \d+|ANR in ' + re.escape(APP) + r'|Process ' + re.escape(APP) + r' \(pid \d+\) has died|Force finishing activity ' + re.escape(APP))
ERROR_TAGS = {'ReactNativeJS', 'ReactNative', 'AndroidRuntime', 'unknown:ReactNative', 'Expo', 'ExpoModulesCore', 'libc', 'DEBUG', 'CRASH'}


def read_flows(out):
    flows = []
    path = out / 'flujos.txt'
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3:
                flows.append({'name': parts[0], 'code': int(parts[1]), 'seconds': int(parts[2])})
    for flow in flows:
        flow['failure'] = ''
        junit = out / 'junit' / f"{flow['name']}.xml"
        if junit.exists():
            try:
                root = ET.parse(junit).getroot()
                for case in root.iter('testcase'):
                    for tag in ('failure', 'error'):
                        node = case.find(tag)
                        if node is not None:
                            flow['failure'] = (node.get('message') or node.text or '').strip()
            except ET.ParseError:
                pass
        if flow['code'] != 0 and not flow['failure']:
            log = out / 'maestro' / f"{flow['name']}.log"
            if log.exists():
                lines = [l for l in log.read_text(errors='replace').splitlines() if l.strip()]
                flow['failure'] = next((l for l in reversed(lines) if 'FAILED' in l or 'Error' in l or 'failed' in l), lines[-1] if lines else '')
        flow['ok'] = flow['code'] == 0
    return flows


def split_logcat(out):
    """Keeps the app's lines (by pid), the crashes and the JS errors; compresses the full log."""
    full = out / 'logcat' / 'logcat-completo.txt'
    if not full.exists():
        return {'crash': False, 'crashes': [], 'js_errors': 0, 'present': False}
    text = full.read_text(errors='replace').splitlines()
    pids = {m.group(1) for line in text for m in [START.search(line)] if m}
    app, errors, crashes = [], [], []
    js_errors = 0
    for line in text:
        m = LINE.match(line)
        pid, level, tag = (m.group(1), m.group(3), m.group(4)) if m else (None, None, '')
        mine = pid in pids or APP in line
        crash = bool(CRASH.search(line)) and (mine or 'FATAL EXCEPTION' in line or 'Fatal signal' in line)
        if crash:
            crashes.append(line)
        if mine or tag in ('ReactNativeJS', 'ReactNative'):
            app.append(line)
        if crash or (level in ('E', 'F') and (mine or tag in ERROR_TAGS)) or (tag == 'ReactNativeJS' and level in ('W', 'E')):
            errors.append(line)
            if tag == 'ReactNativeJS' and level == 'E':
                js_errors += 1
    (out / 'logcat' / 'logcat-app.txt').write_text('\n'.join(app) + '\n')
    (out / 'logcat' / 'logcat-errores.txt').write_text('\n'.join(errors) + '\n')
    with gzip.open(out / 'logcat' / 'logcat-completo.txt.gz', 'wt') as fh:
        fh.write('\n'.join(text) + '\n')
    full.unlink()
    return {'crash': bool(crashes), 'crashes': crashes[:20], 'js_errors': js_errors, 'present': True}


def api_problems(out):
    log = out / 'api.log'
    if not log.exists():
        return {'5xx': 0, '429': 0, 'traceback': 0}
    text = log.read_text(errors='replace')
    status = re.findall(r'" (\d{3}) ', text)
    return {'5xx': sum(1 for s in status if s.startswith('5')), '429': status.count('429'), 'traceback': text.count('Traceback (most recent call last)')}


def write_html(out, flows, logcat, api):
    shots = sorted(p.name for p in (out / 'capturas').glob('*.png')) if (out / 'capturas').exists() else []
    fails = sorted(p.name for p in (out / 'capturas' / 'fallos').glob('*.png')) if (out / 'capturas' / 'fallos').exists() else []
    videos = sorted(p.name for p in (out / 'videos').glob('*.mp4')) if (out / 'videos').exists() else []
    rows = ''.join(
        f"<tr class=\"{'ok' if f['ok'] else 'ko'}\"><td>{html.escape(f['name'])}</td><td>{'pasa' if f['ok'] else 'falla'}</td>"
        f"<td>{f['seconds']} s</td><td><pre>{html.escape(f['failure'])}</pre></td></tr>" for f in flows)
    def gallery(prefix):
        items = [s for s in shots if s.startswith(prefix[:2] + '-')]
        items += [s for s in fails if s.startswith(prefix + '--')]
        vids = [v for v in videos if v.startswith(prefix + '-')]
        figs = ''.join(f'<figure><a href="capturas/{"fallos/" if s in fails else ""}{html.escape(s)}"><img loading="lazy" src="capturas/{"fallos/" if s in fails else ""}{html.escape(s)}"></a><figcaption>{html.escape(s)}</figcaption></figure>' for s in items)
        links = ' · '.join(f'<a href="videos/{html.escape(v)}">{html.escape(v)}</a>' for v in vids)
        return f'<h2>{html.escape(prefix)}</h2><p>Video: {links or "—"}</p><div class="g">{figs or "<p>Sin capturas.</p>"}</div>'
    body = ''.join(gallery(f['name']) for f in flows)
    crash = '<p class="ko">Crash de la app:</p><pre>' + html.escape('\n'.join(logcat['crashes'])) + '</pre>' if logcat['crash'] else '<p>Sin crashes en logcat.</p>'
    page = f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QA móvil</title><style>
body{{font:15px/1.45 system-ui,sans-serif;margin:16px;color:#1d1d1b;background:#f7f6f0}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ccc;padding:4px 8px;vertical-align:top;text-align:left}}tr.ok td:nth-child(2){{color:#00715e}}tr.ko td:nth-child(2),.ko{{color:#b3261e;font-weight:700}}
pre{{white-space:pre-wrap;margin:0;font-size:12px}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}}
figure{{margin:0}}img{{width:100%;border:1px solid #ccc}}figcaption{{font-size:12px;word-break:break-all}}</style>
<h1>QA móvil</h1><table><tr><th>Flujo</th><th>Resultado</th><th>Duración</th><th>Fallo</th></tr>{rows}</table>
{crash}<p>Errores de ReactNativeJS en logcat: {logcat['js_errors']} · API: {api['5xx']} respuestas 5xx, {api['429']} respuestas 429, {api['traceback']} tracebacks.</p>
{body}</html>"""
    (out / 'informe.html').write_text(page)


def main():
    out = Path(sys.argv[1])
    flows = read_flows(out)
    logcat = split_logcat(out)
    api = api_problems(out)
    write_html(out, flows, logcat, api)
    passed = sum(1 for f in flows if f['ok'])
    ok = bool(flows) and passed == len(flows) and not logcat['crash']
    (out / 'resultado.txt').write_text('ok\n' if ok else 'fallo\n')
    total = sum(f['seconds'] for f in flows)
    lines = ['## QA móvil', '',
             f"**{passed} de {len(flows)} flujos pasan** · crash: **{'sí' if logcat['crash'] else 'no'}** · "
             f"errores ReactNativeJS: {logcat['js_errors']} · API: {api['5xx']}×5xx, {api['429']}×429 · {total // 60} min de flujos", '',
             '| Flujo | Resultado | Duración | Motivo |', '|---|---|---|---|']
    for f in flows:
        reason = f['failure'].replace('\n', ' ').replace('|', '\\|')[:220]
        lines.append(f"| `{f['name']}` | {'✅ pasa' if f['ok'] else '❌ falla'} | {f['seconds']} s | {reason} |")
    if not flows:
        lines.append('| — | no se ejecutó ningún flujo | — | — |')
    if logcat['crash']:
        lines += ['', '<details><summary>Crash en logcat</summary>', '', '```', *logcat['crashes'][:10], '```', '</details>']
    if not logcat['present']:
        lines += ['', 'No hay logcat: el emulador no llegó a arrancar o el paso falló antes.']
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
