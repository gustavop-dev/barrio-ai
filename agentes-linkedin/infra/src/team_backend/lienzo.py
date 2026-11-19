"""IMG-INF «lienzo libre»: an infographic the designer writes as one HTML+CSS document (INFOGRAFIA_LIENZO, off by default).

The designer writes the content of a 1080×1080 image's content area; the code
1. checks the document against an allowlist and REJECTS it with the reason (never strips it silently): no scripts, no
   event handlers, no external resources, links, images, iframes or forms, CSS from the brand palette only;
2. applies the same truth rules as the templates to its words: a figure needs a source from public_facts or sources;
3. renders it without a browser and without JavaScript (WeasyPrint, in a child process: lienzo_render.py) with the network
   blocked, one render at a time and under a time limit;
4. measures the layout: one page, nothing outside the content area, nothing under 28 px, palette colours, 4.5:1 contrast,
   no text over text; then draws the source and the foot itself, like a template does;
5. hands the PNG to the same vision check as a template (connectors_images, with the canvas' own extra points).
Any failure falls back to the template design of the same answer, then to the post's own key line and only last to
the brand card (imagenes.design/fallback).
No image model draws anything here (IMG-INF-08).
"""
import base64
import fcntl
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image, ImageDraw

from . import infografias
from .infografias import DEEP, INK, LINE, PAPER, SOFT, ACCENT


def enabled():
    """The switch. Off (default): the designer's request and every image are what they were without the canvas."""
    return os.environ.get('INFOGRAFIA_LIENZO', 'false').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


SIZE = 1080
# The content box: the board's 96 px margin on top and on both sides; under it, the code draws the source and the foot
# at the same places a template does (infografias.render).
AREA = (96, 96, 984, 840)
FONT = infografias.RESOURCE / 'fonts' / 'Ubuntu.ttf'
TOKENS = {'papel': PAPER, 'tinta': INK, 'tinta-suave': SOFT, 'linea': LINE, 'acento': DEEP, 'acento-tinta': ACCENT,
          'bajada-tinta': '#B9BCCB', 'postit': '#F8D47D', 'oxido': '#A54E35'}
PALETTE = frozenset(v.upper() for v in TOKENS.values())
MAX_BYTES = 20_000
MAX_WORDS = 90
TIMEOUT_S = 45  # the render's own limit (INFOGRAFIA_LIENZO_TIMEOUT_S); a 1 vCPU server takes a few seconds
MEMORY_MB = 1024  # address-space cap of the child process (measured peak ~100 MB resident, ~360 MB virtual)


def timeout_s():
    try:
        return max(5, min(120, int(os.environ.get('INFOGRAFIA_LIENZO_TIMEOUT_S') or TIMEOUT_S)))
    except ValueError:
        return TIMEOUT_S


def tokens_text():
    """The brand tokens as the designer reads them."""
    return ', '.join(f'--{name}: {value}' for name, value in TOKENS.items())


# --------------------------------------------------------------------------- document checks

TAGS = frozenset('div span p h1 h2 h3 h4 ul ol li table thead tbody tfoot tr th td caption section article header footer '
                 'figure figcaption strong em b i small br hr sup sub blockquote dl dt dd'.split())
VOID = frozenset(('br', 'hr'))
SCRIPTS = 'Sin scripts: el lienzo es solo HTML y CSS'
EMBEDS = 'Sin iframes ni contenido incrustado'
FORMS = 'Sin formularios ni controles'
MEDIA = 'Sin imágenes, svg, enlaces ni recursos externos: el lienzo es solo HTML y CSS'
REFUSED = {**{t: SCRIPTS for t in ('script', 'noscript', 'template', 'slot')},
           **{t: EMBEDS for t in ('iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'portal')},
           **{t: FORMS for t in ('form', 'input', 'button', 'select', 'textarea', 'option', 'optgroup', 'label',
                                  'fieldset', 'legend', 'output', 'datalist', 'dialog', 'details', 'summary')},
           **{t: MEDIA for t in ('img', 'svg', 'math', 'image', 'picture', 'video', 'audio', 'source', 'track', 'canvas',
                                  'link', 'base', 'a', 'area', 'map')}}
ATTRIBUTES = frozenset(('class', 'style', 'colspan', 'rowspan'))
URL_ATTRIBUTES = frozenset(('src', 'href', 'srcset', 'action', 'formaction', 'data', 'poster', 'background', 'xlink:href',
                            'ping', 'cite', 'longdesc', 'manifest', 'codebase', 'archive', 'usemap', 'lowsrc', 'dynsrc'))
CLASS = re.compile(r'[A-Za-z0-9_ -]{0,200}')


class _Sanitizer(HTMLParser):
    """Rebuilds the body from what it understood (tags and attributes of the allowlist, escaped text); the renderer only
    ever sees this rebuild, never the designer's string. The CSS of <style> is collected for check_css."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.css, self.texts, self.open = [], [], [], []
        self.skip = None  # 'style' or 'title' while inside one

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, closed=False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, closed=True)

    def _start(self, tag, attrs, closed):
        tag = tag.lower()
        if tag in REFUSED:
            raise ValueError(REFUSED[tag])
        if tag in ('html', 'head', 'body'):
            if any(name.lower() != 'lang' for name, _ in attrs):
                raise ValueError(f'<{tag}> sin atributos')
            return
        if tag == 'meta':
            if [name.lower() for name, _ in attrs] != ['charset']:
                raise ValueError('Solo <meta charset>: sin meta http-equiv ni refresh')
            return
        if tag in ('style', 'title'):
            if attrs:
                raise ValueError(f'<{tag}> sin atributos')
            self.skip = tag
            return
        if tag not in TAGS:
            raise ValueError(f'Etiqueta no permitida: <{tag}>')
        clean = []
        for name, value in attrs:
            name, value = name.lower(), value or ''
            if name.startswith('on'):
                raise ValueError('Sin manejadores de eventos (atributos on…)')
            if name in URL_ATTRIBUTES or re.search(r'javascript:|vbscript:|data:', value, re.I):
                raise ValueError(MEDIA)
            if name not in ATTRIBUTES:
                raise ValueError(f'Atributo no permitido: {name} (solo class, style, colspan y rowspan)')
            if name == 'class' and not CLASS.fullmatch(value):
                raise ValueError('Clases solo con letras, números, - y _')
            if name in ('colspan', 'rowspan') and not re.fullmatch(r'[1-4]', value.strip()):
                raise ValueError('colspan y rowspan de 1 a 4')
            if name == 'style':
                value = check_declarations(value)
            clean.append((name, value.strip()))
        self.out.append('<' + tag + ''.join(f' {n}="{html.escape(v, quote=True)}"' for n, v in clean) + '>')
        if tag in VOID:
            return
        if closed:
            self.out.append(f'</{tag}>')
        else:
            self.open.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in REFUSED:
            raise ValueError(REFUSED[tag])
        if tag in ('html', 'head', 'body', 'meta') or tag in VOID:
            return
        if tag in ('style', 'title'):
            self.skip = None
            return
        if tag not in TAGS:
            raise ValueError(f'Etiqueta no permitida: <{tag}>')
        if tag in self.open:  # close what was left open inside it; a stray end tag is ignored
            while self.open:
                last = self.open.pop()
                self.out.append(f'</{last}>')
                if last == tag:
                    break

    def handle_data(self, data):
        if self.skip == 'style':
            self.css.append(data)
        elif self.skip is None:
            self.out.append(html.escape(data, quote=False))
            self.texts.append(data)

    def handle_comment(self, data):
        pass  # dropped from the rebuild

    def handle_decl(self, decl):
        if decl.strip().lower() != 'doctype html':
            raise ValueError('Solo <!doctype html>')

    def unknown_decl(self, data):
        raise ValueError('Sin CDATA ni declaraciones')

    def handle_pi(self, data):
        raise ValueError('Sin instrucciones de procesamiento')


def sanitize(document):
    """(body, css, texts) of the designer's document, rebuilt; ValueError with the reason for anything outside the
    allowlist. `texts`: every visible text node, for the truth rules."""
    if not isinstance(document, str) or not document.strip():
        raise ValueError('El lienzo está vacío')
    if len(document.encode()) > MAX_BYTES:
        raise ValueError(f'Lienzo demasiado grande: más de {MAX_BYTES // 1000} KB')
    parser = _Sanitizer()
    parser.feed(document)
    parser.close()
    if parser.skip == 'style':
        raise ValueError('Un <style> sin cerrar')
    body = ''.join(parser.out) + ''.join(f'</{t}>' for t in reversed(parser.open))
    return body, check_css(''.join(parser.css)), parser.texts


# --------------------------------------------------------------------------- CSS checks

PROPERTIES = frozenset('''display flex flex-direction flex-wrap flex-flow flex-grow flex-shrink flex-basis order
justify-content justify-items justify-self align-items align-content align-self place-items place-content place-self
gap row-gap column-gap grid-template-columns grid-template-rows grid-column grid-row grid-column-start grid-column-end
grid-row-start grid-row-end grid-auto-flow grid-auto-rows grid-auto-columns width height min-width min-height max-width
max-height margin margin-top margin-right margin-bottom margin-left padding padding-top padding-right padding-bottom
padding-left box-sizing border border-top border-right border-bottom border-left border-width border-style border-color
border-top-width border-right-width border-bottom-width border-left-width border-top-style border-right-style
border-bottom-style border-left-style border-top-color border-right-color border-bottom-color border-left-color
border-radius border-top-left-radius border-top-right-radius border-bottom-left-radius border-bottom-right-radius
border-collapse border-spacing table-layout vertical-align color background background-color font-size line-height
font-weight font-family letter-spacing word-spacing text-align text-transform text-decoration text-decoration-line
text-decoration-color text-decoration-thickness white-space word-break overflow-wrap hyphens list-style list-style-type
list-style-position position top right bottom left inset z-index overflow overflow-x overflow-y font-variant-numeric
text-indent'''.split())
DECORATION = frozenset(('box-shadow', 'text-shadow', 'filter', 'backdrop-filter', 'opacity', 'transform', 'perspective',
                        'mix-blend-mode', 'clip-path', 'mask', 'background-image', 'animation', 'transition'))
FUNCTIONS = frozenset(('var', 'calc', 'repeat', 'minmax'))
# Where an ident may name a colour: only these words (no named colours: the palette, by its hex or its var()).
COLOUR_PROPERTIES = frozenset(p for p in PROPERTIES if 'color' in p or p in ('background', 'border', 'border-top',
                              'border-right', 'border-bottom', 'border-left', 'text-decoration'))
COLOUR_WORDS = frozenset(('transparent', 'currentcolor', 'inherit', 'none', 'solid', 'dashed', 'dotted', 'double',
                          'thin', 'medium', 'thick', 'underline', 'line-through'))


def _tinycss():
    import tinycss2  # a WeasyPrint dependency, light: the worker parses CSS, only the child renders
    return tinycss2


def _quote(text, limit=40):
    text = ' '.join(str(text).split())
    return f'«{text[:limit]}…»' if len(text) > limit else f'«{text}»'


def _value(prop, tokens):
    """Raise for anything in a declaration's value that could fetch, draw outside the palette or add text."""
    for token in tokens:
        kind = token.type
        if kind == 'url':
            raise ValueError('Sin url() ni recursos externos en el CSS')
        if kind == 'string':
            raise ValueError('Sin texto en el CSS (cadenas): todo texto va en el HTML')
        if kind == 'hash':
            if prop not in COLOUR_PROPERTIES or '#' + token.value.upper() not in PALETTE:
                raise ValueError(f'Color fuera de la paleta: #{token.value}')
        if kind == 'function':
            name = token.lower_name
            if name in ('url', 'image', 'image-set', 'cross-fade', 'element', 'src'):
                raise ValueError('Sin url() ni recursos externos en el CSS')
            if 'gradient' in name:
                raise ValueError('Sin degradados')
            if name not in FUNCTIONS:
                raise ValueError(f'Colores solo de la paleta; función CSS no permitida: {name}()')
            if name == 'var':
                args = [t for t in token.arguments if t.type not in ('whitespace', 'comment')]
                if len(args) != 1 or args[0].type != 'ident' or args[0].value[2:] not in TOKENS or not args[0].value.startswith('--'):
                    raise ValueError('var() solo con los colores de la paleta: ' + tokens_text())
            else:
                _value(prop, token.arguments)
        if kind in ('() block', '[] block', '{} block'):
            _value(prop, token.content)
        if kind == 'ident':
            word = token.lower_value
            if prop in COLOUR_PROPERTIES and word not in COLOUR_WORDS:
                raise ValueError(f'Colores solo de la paleta (hex o var()); «{word}» no vale en {prop}')
            if prop == 'position' and word not in ('static', 'relative', 'absolute'):
                raise ValueError('position: static, relative o absolute')
            if prop.startswith('overflow') and word != 'visible':
                raise ValueError('Sin overflow oculto: nada puede quedar cortado')
            if prop == 'display' and word == 'none':
                raise ValueError('Sin texto escondido (display: none)')
            if prop == 'font-weight' and word not in ('normal', 'inherit'):
                raise ValueError('Ubuntu regular: el bold es solo para el nombre 0ff1ce')
        if kind == 'number' and prop == 'font-weight' and token.value != 400:
            raise ValueError('Ubuntu regular: el bold es solo para el nombre 0ff1ce')
        if prop == 'font-size':
            if kind in ('percentage', 'number') or (kind == 'dimension' and token.lower_unit != 'px'):
                raise ValueError('font-size en px')
            if kind == 'dimension' and token.value < 28:
                raise ValueError(f'Nada por debajo de 28 px (font-size: {token.value:g}px)')


def check_declarations(text):
    """A declaration list (a style attribute or a rule's body), checked and serialized back; ValueError otherwise."""
    tinycss2 = _tinycss()
    parse = getattr(tinycss2, 'parse_blocks_contents', None) or tinycss2.parse_declaration_list
    out = []
    for item in parse(text, skip_whitespace=True, skip_comments=True):
        if item.type == 'error':
            raise ValueError(f'CSS inválido: {item.message}')
        if item.type != 'declaration':
            raise ValueError('Sin reglas anidadas en el CSS')
        name = item.lower_name
        if name.startswith('--'):
            raise ValueError('Sin variables propias: usa las de la paleta (' + tokens_text() + ')')
        if item.important:
            raise ValueError('Sin !important')
        if name in DECORATION:
            raise ValueError(f'Sin sombras, degradados, transparencias ni transformaciones ({name})')
        if name not in PROPERTIES:
            raise ValueError(f'Propiedad CSS no permitida: {name}')
        if name == 'font-family':
            continue  # the code imposes Ubuntu
        _value(name, item.value)
        out.append(f'{name}:{tinycss2.serialize(item.value).strip()}')
    return ';'.join(out)


PSEUDO = frozenset(('before', 'after', 'marker', 'first-letter', 'first-line', 'selection', 'placeholder', 'root'))


def _selector(tokens):
    """No ids (the code's own box), no html/body/:root (the page) and no pseudo-elements (they could add text)."""
    previous = None
    for i, token in enumerate(tokens):
        if token.type == 'hash':
            raise ValueError('Sin selectores de id: usa clases')
        if token.type == 'ident' and token.lower_value in ('html', 'body') and not (previous and previous.type == 'literal' and previous.value == '.'):
            raise ValueError('Sin selectores html ni body: el código fija la página')
        if token.type == 'literal' and token.value == ':':
            following = tokens[i + 1] if i + 1 < len(tokens) else None
            if following is not None and following.type == 'literal' and following.value == ':':
                raise ValueError('Sin pseudo-elementos (::before, ::after…): todo texto va en el HTML')
            word = getattr(following, 'lower_value', None) or getattr(following, 'lower_name', None)
            if word in PSEUDO:
                raise ValueError('Sin pseudo-elementos ni :root: todo texto va en el HTML y el código fija la página')
        if token.type == 'function':
            _selector(token.arguments)
        if token.type in ('() block', '[] block'):
            _selector(token.content)
        if token.type not in ('whitespace', 'comment'):
            previous = token


def check_css(text):
    """The designer's stylesheet, checked rule by rule and serialized back; ValueError with the reason otherwise."""
    if '<' in text:
        raise ValueError('CSS inválido: «<» dentro de <style>')
    tinycss2 = _tinycss()
    out = []
    for rule in tinycss2.parse_stylesheet(text, skip_whitespace=True, skip_comments=True):
        if rule.type == 'error':
            raise ValueError(f'CSS inválido: {rule.message}')
        if rule.type == 'at-rule':
            raise ValueError(f'Sin @{rule.lower_at_keyword} en el CSS (ni @import, @font-face ni @media)')
        _selector(rule.prelude)
        out.append(tinycss2.serialize(rule.prelude).strip() + '{' + check_declarations(tinycss2.serialize(rule.content)) + '}')
    return '\n'.join(out)


# --------------------------------------------------------------------------- truth rules and the document

def validate(spec, public=(), sources=()):
    """The full document the renderer gets, when the canvas passes every rule; ValueError with the reason otherwise.
    Its words follow the templates' rules (infografias.clean_text and sourced): every figure needs a source."""
    infografias.schema_check(spec, infografias.LIENZO, 'lienzo')
    body, css, texts = sanitize(spec['html'])
    words = ' '.join(' '.join(texts).split())
    title = ' '.join(spec['title'].split())
    if not title or len(title.split()) > 14:
        raise ValueError('Titular (lienzo.title): de 1 a 14 palabras')
    if len(words.split()) > MAX_WORDS:  # legibility at feed size; the board's own guide is 40
        raise ValueError(f'Demasiadas palabras: el lienzo admite {MAX_WORDS}')
    infografias.clean_text([title, *texts], spec['alt'])
    infografias.sourced([title, words], spec['source'], public, sources)
    return document(body, css, spec['fondo'])


def document(body, css, fondo):
    """The page the renderer gets: the brand's base, the designer's checked CSS, then what the code imposes (Ubuntu
    regular, and the content box nobody can move: the designer cannot use ids nor !important)."""
    dark = fondo == 'tinta'
    tokens = ';'.join(f'--{name}:{value}' for name, value in TOKENS.items())
    base = (f'@page{{size:{SIZE}px {SIZE}px;margin:0}}:root{{{tokens}}}'
            f'html,body{{margin:0;padding:0;width:{SIZE}px;height:{SIZE}px;background:{INK if dark else PAPER};'
            f'color:{PAPER if dark else INK};font-size:36px;line-height:1.3}}'
            'h1,h2,h3,h4,p,ul,ol,figure,blockquote,dl,table{margin:0}')
    x0, y0, x1, y1 = AREA
    imposed = ('*{font-family:Ubuntu !important;font-weight:400 !important;font-style:normal !important}'
               f'#lienzo{{position:absolute !important;left:{x0}px !important;top:{y0}px !important;'
               f'width:{x1 - x0}px !important;height:{y1 - y0}px !important;margin:0 !important;padding:0 !important;'
               'border:0 !important}')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{base}</style><style>{css}</style>'
            f'<style>{imposed}</style></head><body><div id="lienzo">{body}</div></body></html>')


# --------------------------------------------------------------------------- rendering

class Renderer:
    """WeasyPrint (HTML/CSS to PDF, no JavaScript engine) and pdfium (PDF to PNG) in a child process, so the worker never
    imports them, their memory goes back when it exits, a hang is killed at the time limit and the worker's keys never
    reach it (its environment is filtered). (png bytes, layout facts) of one document."""
    name = 'weasyprint'
    KEEP = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'XDG_CACHE_HOME', 'FONTCONFIG_FILE', 'FONTCONFIG_PATH')

    def render(self, page):
        script = Path(__file__).with_name('lienzo_render.py')
        request = json.dumps({'html': page, 'font': str(FONT), 'size': SIZE, 'memory_mb': MEMORY_MB}).encode()
        env = {k: v for k, v in os.environ.items() if k in self.KEEP}
        limit = timeout_s()
        with exclusive(limit):
            try:
                done = subprocess.run([sys.executable, '-I', str(script)], input=request, capture_output=True,
                                      timeout=limit, env=env, check=False)
            except subprocess.TimeoutExpired:
                raise ValueError(f'El render del lienzo superó {limit} s') from None
        if done.returncode != 0:
            last = (done.stderr.decode(errors='replace').strip().splitlines() or [''])[-1]
            raise ValueError(f'El render del lienzo falló ({done.returncode}): {last[:200]}')
        try:
            answer = json.loads(done.stdout)
            return base64.b64decode(answer['png'], validate=True), answer['facts']
        except (ValueError, KeyError, TypeError):
            raise ValueError('El render del lienzo devolvió una respuesta inválida') from None


RENDERER = None  # tests inject a fake with the same render(page) -> (png, facts)


def renderer():
    return RENDERER or Renderer()


_render_lock = threading.Lock()
LOCK_FILE = Path(tempfile.gettempdir()) / 'barrio-lienzo.lock'


@contextmanager
def exclusive(wait_s):
    """One render at a time: in this process (a lock) and in this container (a file lock), waiting at most `wait_s`."""
    deadline = time.monotonic() + wait_s
    if not _render_lock.acquire(timeout=wait_s):
        raise ValueError('Otro render del lienzo en curso')
    try:
        with open(LOCK_FILE, 'a+') as handle:
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise ValueError('Otro render del lienzo en curso') from None
                    time.sleep(0.2)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        _render_lock.release()


def layout_issues(facts):
    """What the measured layout breaks, as reasons for the one correction ([] when it holds)."""
    x0, y0, x1, y1 = AREA
    issues = []

    def outside(box, slack=1):
        a, b, c, d = box
        return a < x0 - slack or b < y0 - slack or c > x1 + slack or d > y1 + slack

    if facts.get('pages') != 1:
        issues.append('El contenido no cabe en el lienzo: ocupa más de una página')
    texts = [t for t in facts.get('texts') or [] if str(t.get('text', '')).strip()]
    if not texts:
        issues.append('El lienzo no tiene texto')
    for item in texts:
        quote = _quote(item['text'])
        if outside(item['box']):
            issues.append(f'Texto fuera del área o cortado: {quote}')
        if item['size'] < 28 - 0.01:
            issues.append(f'Texto por debajo de 28 px: {quote}')
        if item['color'] not in PALETTE or item.get('alpha', 1) < 1:
            issues.append(f'Color de texto fuera de la paleta: {quote}')
        elif infografias.contrast(item['color'], item['background']) < 4.5:
            issues.append(f'Contraste por debajo de 4,5:1: {quote}')
    for box in facts.get('boxes') or []:
        if outside(box['box']):
            issues.append('Un bloque se sale del área de contenido')
        if box.get('background') and (box['background'] not in PALETTE or box.get('alpha', 1) < 1):
            issues.append('Fondo fuera de la paleta o con transparencia')
        if any(color not in PALETTE for color in box.get('borders') or []):
            issues.append('Borde fuera de la paleta')
    # Text on text cannot be read: two lines overlapping by more than a quarter of the smaller one.
    for i, one in enumerate(texts):
        for other in texts[i + 1:]:
            a = max(one['box'][0], other['box'][0]), max(one['box'][1], other['box'][1])
            b = min(one['box'][2], other['box'][2]), min(one['box'][3], other['box'][3])
            shared = max(0, b[0] - a[0]) * max(0, b[1] - a[1])
            smaller = min((t['box'][2] - t['box'][0]) * (t['box'][3] - t['box'][1]) for t in (one, other))
            if smaller > 0 and shared > smaller / 4:
                issues.append(f'Textos superpuestos: {_quote(one["text"])} y {_quote(other["text"])}')
    return list(dict.fromkeys(issues))[:8]


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def finish(png, spec, name=None):
    """The rendered page with what the code draws itself under the content box, like a template: the source with its
    date (lienzo.source) and the foot, the author on the left and «1/1» on the right, at 28 px."""
    with Image.open(io.BytesIO(png)) as decoded:
        image = decoded.convert('RGB')
    if image.size != (SIZE, SIZE):
        raise ValueError(f'El render del lienzo no mide {SIZE}×{SIZE}')
    dark = spec['fondo'] == 'tinta'
    bg, fg, muted = (INK, PAPER, '#B9BCCB') if dark else (PAPER, INK, SOFT)
    x0, y0, x1, y1 = AREA
    # Nothing may be drawn outside the content box: the margins and the band of the source and the foot are still plain.
    for band in ((0, 0, SIZE, y0), (0, 0, x0, SIZE), (x1 + 1, 0, SIZE, SIZE), (0, y1 + 1, SIZE, SIZE)):
        colours = image.crop(band).getcolors(1)
        if colours is None or colours[0][1] != _rgb(bg):
            raise ValueError('El lienzo dibuja fuera de su área')
    draw = ImageDraw.Draw(image)
    face = infografias.font(28)

    def line(text, x, y, colour, width=888):
        rows, current = [], ''
        for word in text.split():
            if draw.textlength(word, font=face) > width:
                raise ValueError('Palabra demasiado ancha en la fuente')
            candidate = (current + ' ' + word).strip()
            if draw.textlength(candidate, font=face) > width:
                rows.append(current)
                current = word
            else:
                current = candidate
        if current:
            rows.append(current)
        for row in rows:
            draw.text((x, y), row, font=face, fill=colour, anchor='lt')
            y += 36
        return y

    source = spec['source']
    citation = ' · '.join(x for x in (source['label'], source['date']) if x)
    if citation and line(citation, 96, SIZE - 224, muted) > SIZE - 152:
        raise ValueError('La fuente invade el pie')
    line(infografias._signer(name), 96, SIZE - 128, fg)
    number = '1/1'
    draw.text((984 - draw.textlength(number, font=face), SIZE - 128), number, font=face, fill=fg, anchor='lt')
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def render(page, spec, name=None):
    """PNG bytes of a checked document (validate), after its layout passes layout_issues; ValueError otherwise."""
    png, facts = renderer().render(page)
    problems = layout_issues(facts)
    if problems:
        raise ValueError('; '.join(problems))
    return finish(png, spec, name)
