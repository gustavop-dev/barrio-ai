#!/usr/bin/env python3
"""Visual regression of the QA screenshots against the reference from main (.github/workflows/qa-movil.yml).

    visual.py comparar <qa-artefactos> <referencias>   compares capturas/*.png with the reference, writes visual/
    visual.py referencias <capturas> <anteriores> <salida>   builds the new reference (previous ∪ this run)

Both images are brought to 390x844 (the design boards' dp), the status bar and the configured masks are left out, and
a pixel counts as changed when a channel moves more than `umbral_pixel`. A screenshot changes when the changed share is
above its `tolerancia` (scripts/qa/visual.json, per name with fnmatch patterns). For each one over it, visual/ gets a
before | after | diff image. visual/resultado.json is read by informe.py. Needs Pillow (the workflow runs it with
`uv run --with pillow`); nothing else. It never fails the run: the workflow marks it (warning and the «QA visual» check).
"""
import fnmatch
import json
import sys
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

SIZE = (390, 844)
CONFIG = Path(__file__).with_name('visual.json')
GUTTER = 8


def config():
    data = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    data.setdefault('tolerancia', 0.015)
    data.setdefault('umbral_pixel', 40)
    data.setdefault('mascaras', [[0, 0, 390, 24]])
    data.setdefault('capturas', {})
    return data


def rules_for(name, cfg):
    """Tolerance, masks and whether to ignore, for one screenshot name (without .png)."""
    tolerance, masks, ignore = cfg['tolerancia'], list(cfg['mascaras']), False
    for pattern, rule in cfg['capturas'].items():
        if fnmatch.fnmatch(name, pattern):
            tolerance = rule.get('tolerancia', tolerance)
            masks += rule.get('mascaras', [])
            ignore = ignore or bool(rule.get('ignorar'))
    return tolerance, masks, ignore


def normal(path):
    return Image.open(path).convert('RGB').resize(SIZE, Image.BILINEAR)


def compare(before, after, masks, threshold):
    """(changed share, mask image of the changed pixels)."""
    diff = ImageChops.difference(before, after).convert('L').point(lambda v: 255 if v > threshold else 0)
    keep = Image.new('L', SIZE, 255)
    draw = ImageDraw.Draw(keep)
    for x, y, w, h in masks:
        draw.rectangle([x, y, x + w - 1, y + h - 1], fill=0)
    changed = ImageChops.multiply(diff, keep)
    counted = keep.histogram()[255]
    return (changed.histogram()[255] / counted if counted else 0.0), changed


def composite(before, after, changed):
    """antes | después | después desaturado con los píxeles que cambian en rojo."""
    width, height = SIZE
    out = Image.new('RGB', (width * 3 + GUTTER * 2, height), (255, 255, 255))
    out.paste(before, (0, 0))
    out.paste(after, (width + GUTTER, 0))
    faded = Image.blend(after.convert('L').convert('RGB'), Image.new('RGB', SIZE, (255, 255, 255)), 0.6)
    red = Image.new('RGB', SIZE, (220, 30, 30))
    out.paste(Image.composite(red, faded, changed), (2 * (width + GUTTER), 0))
    return out


def run_compare(artifacts, references):
    cfg = config()
    shots = {p.stem: p for p in sorted((artifacts / 'capturas').glob('[0-9][0-9]-*.png'))}
    refs = {p.stem: p for p in sorted(references.glob('[0-9][0-9]-*.png'))} if references.exists() else {}
    out = artifacts / 'visual'
    out.mkdir(parents=True, exist_ok=True)
    result = {'referencia': (references / 'origen.txt').read_text().strip() if (references / 'origen.txt').exists() else None,
              'comparadas': 0, 'cambian': [], 'nuevas': [], 'ignoradas': []}
    if not refs:
        result['sin_referencia'] = True
    for name, path in shots.items():
        tolerance, masks, ignore = rules_for(name, cfg)
        if ignore:
            result['ignoradas'].append(name)
            continue
        if name not in refs:
            if refs:
                result['nuevas'].append(name)
            continue
        before, after = normal(refs[name]), normal(path)
        share, changed = compare(before, after, masks, cfg['umbral_pixel'])
        result['comparadas'] += 1
        if share > tolerance:
            composite(before, after, changed).save(out / f'{name}.png', optimize=True)
            result['cambian'].append({'captura': name, 'cambio': round(share, 4), 'tolerancia': tolerance})
    result['cambian'].sort(key=lambda c: -c['cambio'])
    (out / 'resultado.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"comparadas {result['comparadas']}, cambian {len(result['cambian'])}, nuevas {len(result['nuevas'])}")


def run_references(shots_dir, previous, out, origin=''):
    """The new reference: the previous one, with this run's screenshots on top, at 390x844."""
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    for source in (previous, shots_dir):
        if not source.exists():
            continue
        for path in sorted(source.glob('[0-9][0-9]-*.png')):
            normal(path).save(out / path.name, optimize=True)
            count += 1
    (out / 'origen.txt').write_text(origin)
    print(f'referencia: {len(list(out.glob("*.png")))} capturas ({count} escritas)')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'comparar' and len(sys.argv) == 4:
        run_compare(Path(sys.argv[2]), Path(sys.argv[3]))
    elif mode == 'referencias' and len(sys.argv) in (5, 6):
        run_references(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5] if len(sys.argv) == 6 else '')
    else:
        sys.exit(__doc__)
