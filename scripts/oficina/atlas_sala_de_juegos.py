"""Appends the game-room furniture of LimeZu Modern Interiors to the office sprite atlas.

The atlas (movil/assets/brand/sprites-atlas.png, copied to oficina/public/brand/) keeps its first 1460 rows: the
people and the office furniture. This script rebuilds one row below them with the game room (Sala de juegos) pieces,
so running it twice gives the same file. The LimeZu library is not in the repository (CREDITS.txt): pass its folder.

    uv run --no-project --with pillow==11.3.0 python scripts/oficina/atlas_sala_de_juegos.py "<…>/Modern Interiors completo"

The rectangles it prints are the ones in compartido/src/scene/atlas.ts.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / 'movil/assets/brand/sprites-atlas.png'
COPY = ROOT / 'oficina/public/brand/sprites-atlas.png'
BASE_HEIGHT = 1460
ROW_Y = BASE_HEIGHT + 1
# name: (theme sheet, [x, y, w, h] in the 16x16 sheet)
PIECES = {
    'tvConsole': ('14_Basement', (98, 760, 60, 34)),
    'speaker': ('6_Music_and_sport', (96, 6, 32, 37)),
    'cueRack': ('14_Basement', (50, 382, 13, 33)),
    'arcades': ('14_Basement', (0, 665, 33, 39)),
    'poolTable': ('14_Basement', (72, 409, 48, 38)),
    'drums': ('6_Music_and_sport', (4, 289, 43, 31)),
    'pouf': ('14_Basement', (230, 672, 20, 24)),
    'mic': ('6_Music_and_sport', (114, 245, 13, 27)),
    'guitar': ('6_Music_and_sport', (160, 44, 15, 31)),
    'armchair': ('14_Basement', (34, 596, 19, 27)),
}


def main(limezu: Path) -> None:
    sheets = limezu / '1_Interiors/16x16/Theme_Sorter'
    base = Image.open(ATLAS).convert('RGBA').crop((0, 0, 512, BASE_HEIGHT))
    height = ROW_Y + max(r[3] for _, r in PIECES.values())
    out = Image.new('RGBA', (512, height))
    out.paste(base, (0, 0))
    x = 0
    for name, (sheet, (sx, sy, w, h)) in PIECES.items():
        piece = Image.open(sheets / f'{sheet}_16x16.png').convert('RGBA').crop((sx, sy, sx + w, sy + h))
        out.paste(piece, (x, ROW_Y))
        print(f'  {name}: [{x}, {ROW_Y}, {w}, {h}],')
        x += w + 1
    assert x <= 512, x
    out.save(ATLAS, optimize=True)
    shutil.copyfile(ATLAS, COPY)


if __name__ == '__main__':
    main(Path(sys.argv[1]))
