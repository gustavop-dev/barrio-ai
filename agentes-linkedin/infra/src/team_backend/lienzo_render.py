"""The child process that renders one «lienzo libre» (lienzo.Renderer runs it as `python -I lienzo_render.py`).

Input on stdin, JSON: {"html": the checked page, "font": the bundled Ubuntu.ttf, "size": 1080, "memory_mb": cap}.
Output on stdout, JSON: {"png": base64 of the 1080×1080 PNG, "facts": the measured layout for lienzo.layout_issues}.
It never imports Django nor the backend, and it has no network: sockets refuse to open and the only URL WeasyPrint may
fetch is the bundled font (any other URL stops the render). WeasyPrint has no JavaScript engine at all.
"""
import base64
import io
import json
import resource
import socket
import sys


def _no_network(*args, **kwargs):
    raise OSError('El render del lienzo no tiene red')


def _block_network():
    socket.socket = _no_network  # type: ignore[assignment,misc]
    socket.create_connection = _no_network  # type: ignore[assignment]
    socket.getaddrinfo = _no_network  # type: ignore[assignment]
    socket.socketpair = _no_network  # type: ignore[assignment]


def _hex(color, fallback=None):
    """('#RRGGBB', alpha) of a computed colour; `currentcolor` resolves to `fallback` (the box's text colour)."""
    if isinstance(color, str):
        return fallback if fallback is not None and color.lower() == 'currentcolor' else ('', 0.0)
    srgb = color.to('srgb')
    return '#' + ''.join(f'{max(0, min(255, round(v * 255))):02X}' for v in srgb.coordinates), float(srgb.alpha)


def _rect(x, y, width, height):
    return [round(x, 1), round(y, 1), round(x + width, 1), round(y + height, 1)]


def facts_of(document):
    """The layout as lienzo.layout_issues reads it: every text with its box, size, colour and the background under it,
    and every painted box (a background or a border) with its colours."""
    texts, boxes = [], []
    page = document.pages[0]._page_box if document.pages else None

    def visit(box, background):
        box = getattr(box, '_box', box)  # an absolutely positioned box is wrapped in a placeholder
        style = box.style
        tag = getattr(box, 'element_tag', None) or ''
        color = _hex(style['color'])
        if tag not in ('html', 'body') and box is not page:
            fill = _hex(style['background_color'])
            borders = []
            for side in ('top', 'right', 'bottom', 'left'):
                if style[f'border_{side}_width'] and style[f'border_{side}_style'] not in ('none', 'hidden'):
                    borders.append(_hex(style[f'border_{side}_color'], color)[0])
            if fill[1] > 0 or borders:
                boxes.append({'tag': tag, 'box': _rect(box.border_box_x(), box.border_box_y(), box.border_width(),
                                                       box.border_height()),
                              'background': fill[0] if fill[1] > 0 else '', 'alpha': fill[1], 'borders': borders})
            if fill[1] > 0:
                background = fill[0]
        if hasattr(box, 'text') and box.text and box.text.strip():
            texts.append({'tag': tag, 'text': box.text, 'box': _rect(box.position_x, box.position_y, box.width, box.height),
                          'size': float(style['font_size']), 'color': color[0], 'alpha': color[1],
                          'background': background})
        for child in getattr(box, 'children', ()) or ():
            visit(child, background)

    root = _hex(page.style['background_color']) if page is not None else ('', 0)
    if page is not None:
        html_box = page.children[0] if page.children else None
        for candidate in (html_box, *(getattr(html_box, 'children', ()) or ())):
            fill = _hex(candidate.style['background_color']) if candidate is not None else ('', 0)
            if fill[1] > 0:
                root = fill
                break
        visit(page, root[0])
    return {'pages': len(document.pages), 'background': root[0], 'texts': texts, 'boxes': boxes}


def main():
    request = json.loads(sys.stdin.buffer.read())
    cap = int(request.get('memory_mb') or 0) * 2**20
    if cap:
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))

    import pypdfium2
    import weasyprint
    from weasyprint.text.fonts import FontConfiguration
    from weasyprint.urls import FatalURLFetchingError, URLFetcher, URLFetcherResponse, path2url

    _block_network()  # after the imports: ssl and urllib subclass socket.socket when imported

    font_url = path2url(request['font'])

    class OnlyTheFont(URLFetcher):
        """Fetches the bundled font and nothing else: any other URL means the page was not the checked one."""

        def fetch(self, url, headers=None):
            if url != font_url:
                raise FatalURLFetchingError(f'URL no permitida en el lienzo: {url[:80]}')
            with open(request['font'], 'rb') as handle:
                return URLFetcherResponse(url, handle.read(), {'Content-Type': 'font/ttf'})

    fetcher = OnlyTheFont()
    fonts = FontConfiguration()
    face = weasyprint.CSS(string=f"@font-face{{font-family:Ubuntu;src:url('{font_url}')}}", font_config=fonts,
                          url_fetcher=fetcher)
    document = weasyprint.HTML(string=request['html'], url_fetcher=fetcher).render(
        font_config=fonts, stylesheets=[face])
    facts = facts_of(document)
    pdf = pypdfium2.PdfDocument(document.copy(document.pages[:1]).write_pdf())
    try:
        # CSS px are 0.75 pt: the 1080 px page is 810 pt, back to 1080 px at 96/72 (lienzo.finish checks the size).
        image = pdf[0].render(scale=96 / 72, draw_annots=False).to_pil().convert('RGB')
    finally:
        pdf.close()
    out = io.BytesIO()
    image.save(out, format='PNG')
    json.dump({'png': base64.b64encode(out.getvalue()).decode(), 'facts': facts}, sys.stdout)


if __name__ == '__main__':
    main()
