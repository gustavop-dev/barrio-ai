"""Gustavo's approved profile brand and render constraints, shared with evidence consumers."""
import unicodedata
from collections import Counter

BRAND_VERSION='PerfilLinkedIn-gustavo-addenda-6-v1'
SOURCE='docs/funcionalidades/estrategia-perfil.md#marca'
ACCENT='#0FF1CE';INK='#1E1E2B';PAPER='#F7F6F0';DEEP='#00715E'
TOKENS={'aguamarina':ACCENT,'tinta':INK,'papel':PAPER,'0ff1ce-hondo':DEEP}
FONT_FAMILY='Ubuntu';FONT_STYLES=('Regular','Bold');BANNER_FONT_STYLE='Regular'
PHOTO_SIZE=(800,800);BANNER_SIZE=(1584,396)
SAFE=(600,60,1260,336);COVER=(0,132,568,396);MOBILE=(317,0,1267,396)
# The copy budget leaves a margin inside TEXT and never shrinks the font.
TEXT=(600,60,1078,336);FIGURE=(1088,36,1260,372)
MAX_LINE_WIDTH=470;FONT_PX=56;LABEL_PX=22;LABEL_TRACKING_EM=.08
LABEL_Y=66;LINE_Y=126;LINE_HEIGHT=68


def banner_word(word):
    """Ignore surrounding punctuation/case, retaining contractions and hyphens."""
    word=unicodedata.normalize('NFKC',word).strip()
    while word and unicodedata.category(word[0]).startswith('P'):word=word[1:]
    while word and unicodedata.category(word[-1]).startswith('P'):word=word[:-1]
    return word.casefold()


def normalize_banner(banner):
    result=dict(banner);lines=result.get('lines',[])
    words=[banner_word(word) for line in lines for word in line.split()]
    counts=Counter(words)
    def valid(word):
        return (bool(word) and word[0].isalpha() and word[-1].isalpha()
            and all(ch.isalpha() or ch in "'’-" for ch in word) and counts[word]==1)
    highlight=banner_word(result.get('highlight') or '')
    if not valid(highlight):
        highlight=next((banner_word(word) for line in lines[1:]+lines[:1] for word in line.split()
            if valid(banner_word(word))),'')
    result['highlight']=highlight
    return result


def evidence():
    """Stable IDs accredit visual decisions, never biography or platform limits."""
    values={
        'marca.tokens':{'tokens':dict(TOKENS),'photo_background':ACCENT},
        'marca.fuente':{'family':FONT_FAMILY,'styles':list(FONT_STYLES),'banner_style':BANNER_FONT_STYLE,
            'renderer':'team_backend.infografias.font (bundled Ubuntu.ttf, Regular; no fallback)'},
        'marca.banner_layout':{'size_px':list(BANNER_SIZE),'background':INK,'text_color':PAPER,
            'accent':ACCENT,'safe':list(SAFE),'covered':list(COVER),'mobile':list(MOBILE),
            'mobile_scope':'Aproximación del tablero; comprobar después en LinkedIn real.'},
        'marca.restricciones_render':{'source':'team_backend.perfil_visual.banner',
            'photo_size_px':list(PHOTO_SIZE),'text':list(TEXT),'figure':list(FIGURE),
            'max_line_width_px':MAX_LINE_WIDTH,'font_px':FONT_PX,'label_px':LABEL_PX,
            'label_tracking_em':LABEL_TRACKING_EM,'line_count':2,'shrink_to_fit':False,
            'scope':'Restricciones de nuestro render; el ajuste de una frase exige render.banner_fit.'},
    }
    return [dict(id=eid,kind='brand',version=BRAND_VERSION,source=SOURCE,scope='photo/banner',values=value)
            for eid,value in values.items()]
