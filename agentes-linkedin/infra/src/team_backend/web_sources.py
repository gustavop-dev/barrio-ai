"""Public URLs and a small, bounded GitHub REST reader. This is not a general crawler.

Only api.github.com is contacted directly. DNS answers must all be public, the chosen address is
pinned for TLS/HTTP, redirects and environment proxies are disabled. No response URL is followed.
"""
import base64
import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx
from django.conf import settings

URL_PATTERN=re.compile(r'https?://[^\s<>"\u201c\u201d]+',re.I)
GITHUB_TRANSPORT=None  # Only tests inject httpx.MockTransport; LIVE_PROVIDERS still applies.


def live_web():
    if not settings.WEB_RESEARCH_ENABLED or os.environ.get('LIVE_PROVIDERS','false').lower()!='true':
        raise ValueError('Investigación web desactivada')


def _public_ip(value):
    ip=ipaddress.ip_address(value)
    if not ip.is_global or ip.is_multicast or ip.is_unspecified or (ip.version==6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global):
        raise ValueError('Dirección no pública')
    if ip.version==6 and (ip.sixtofour is not None or ip.teredo is not None):
        raise ValueError('Dirección de transición no admitida')
    return ip


def public_url(value):
    """Syntactic validation without DNS. Reject credentials, query secrets and ambiguous numeric hosts.

    Query strings are deliberately excluded in phase 1: a signed/private link must not reach a server tool.
    Fragments are never transmitted. DNS validation for seed URLs happens after the live gate.
    """
    if not isinstance(value,str) or not value or len(value)>2048 or re.search(r'[\s\\\x00-\x1f\x7f]',value):
        raise ValueError('URL inválida')
    try:
        parts=urlsplit(value);host=(parts.hostname or '').lower().rstrip('.')
        if parts.scheme.lower() not in ('http','https') or parts.username is not None or parts.password is not None:
            raise ValueError
        if parts.port not in (None,443 if parts.scheme.lower()=='https' else 80):raise ValueError
        if parts.query or '%' in host or not host:raise ValueError
        try:_public_ip(host)
        except ValueError:
            # A failed literal address must never be reinterpreted as DNS (127.1, integer/hex IPs, IPv6).
            if ':' in host or re.fullmatch(r'[0-9.]+',host) or re.match(r'^(?:0x[0-9a-f]+)(?:\.|$)',host):raise ValueError
            host=host.encode('idna').decode('ascii')
            if '.' not in host or host.endswith(('.localhost','.local','.internal','.lan','.home','.test','.invalid','.example')):
                raise ValueError
            if host in ('localhost','metadata.google.internal') or not re.fullmatch(r'[a-z0-9.-]+',host):raise ValueError
        netloc=f'[{host}]' if ':' in host else host
        return urlunsplit((parts.scheme.lower(),netloc,parts.path or '/','',''))
    except (ValueError,UnicodeError):raise ValueError('Solo enlaces públicos http(s), sin credenciales ni parámetros privados') from None


def public_addresses(host):
    try:
        addresses=list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
        if not addresses:raise ValueError
        for address in addresses:_public_ip(address)
        return addresses
    except (OSError,ValueError):raise ValueError('El destino no tiene una dirección pública verificable') from None


def detect_urls(text):
    """Ordered, deduplicated URL candidates. Validation is separate so rejected links remain visible as a limit."""
    urls=[]
    for match in URL_PATTERN.finditer(text or ''):
        url=match.group().rstrip('.,;:!?\'»')
        for opening,closing in (('(',')'),('[',']'),('{','}')):
            while url.endswith(closing) and url.count(closing)>url.count(opening):url=url[:-1]
        if url not in urls:urls.append(url)
    return urls


def github_repo(url):
    parts=urlsplit(public_url(url))
    if parts.hostname not in ('github.com','www.github.com'):return None
    path=parts.path.strip('/')
    match=re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9_.-]{1,100})',path)
    if not match:return None  # A file/issue URL must be read as that page, not replaced by the repo root.
    owner,repo=match.groups();repo=repo.removesuffix('.git')
    if repo in ('','.','..'):return None
    return owner,repo


def _github_get(client,address,path,token=''):
    host=f'[{address}]' if ':' in address else address
    headers={'Host':'api.github.com','Accept':'application/vnd.github+json','Accept-Encoding':'identity','User-Agent':'BarrioAI-public-research',
             'X-GitHub-Api-Version':'2022-11-28'}
    if token:headers['Authorization']='Bearer '+token
    with client.stream('GET',f'https://{host}{path}',headers=headers,extensions={'sni_hostname':'api.github.com'}) as response:
        if response.status_code!=200:raise ValueError('GitHub no disponible')
        if response.headers.get('content-encoding','identity').lower()!='identity':raise ValueError('Compresión no admitida')
        body=bytearray()
        for chunk in response.iter_bytes(chunk_size=8192):
            body.extend(chunk)
            if len(body)>settings.WEB_GITHUB_MAX_BYTES:raise ValueError('Respuesta GitHub demasiado extensa')
        try:return json.loads(body)
        except (ValueError,UnicodeError):raise ValueError('Respuesta GitHub inválida') from None


def read_github(url):
    """Description/topics/languages/README/recent commits from a proven public repo, never HTML scraping."""
    live_web()
    pair=github_repo(url)
    if pair is None:raise ValueError('No es la raíz de un repositorio público')
    owner,repo=pair;path=f'/repos/{owner}/{repo}';canonical=f'https://github.com/{owner}/{repo}'
    address=public_addresses('api.github.com')[0]
    if not 1<=settings.WEB_GITHUB_MAX_BYTES<=1048576 or not 0<settings.WEB_GITHUB_TIMEOUT_S<=30:
        raise ValueError('Límites GitHub inválidos')
    try:
        with httpx.Client(transport=GITHUB_TRANSPORT,timeout=settings.WEB_GITHUB_TIMEOUT_S,
                          follow_redirects=False,trust_env=False) as client:
            # Never use the optional token to discover/read a private repo, even if it grants access.
            info=_github_get(client,address,path)
            if not isinstance(info,dict) or info.get('private') is not False or info.get('visibility','public')!='public':
                raise ValueError('Repositorio no público')
            token=os.environ.get('GITHUB_TOKEN','')
            languages=_github_get(client,address,path+'/languages',token)
            readme=_github_get(client,address,path+'/readme',token)
            commits=_github_get(client,address,path+'/commits?per_page=3',token)
        if not isinstance(languages,dict) or not isinstance(readme,dict) or not isinstance(commits,list):raise ValueError
        if readme.get('encoding')!='base64':raise ValueError
        raw=base64.b64decode(readme.get('content',''),validate=False).decode('utf-8',errors='replace')
        readme_limit=settings.WEB_GITHUB_README_CHARS
        if not 1<=readme_limit<=20000:raise ValueError
        summary={'description':str(info.get('description') or '')[:2000],
                 'topics':list(info.get('topics') or [])[:30],'languages':languages,
                 'recent_commits':[{'sha':item['sha'],'message':item['commit']['message'][:1000],
                                    'date':item['commit']['committer']['date']} for item in commits[:3]]}
        summary_text=json.dumps(summary,ensure_ascii=False)
        return [
            {'url':canonical,'title':f'{owner}/{repo} · GitHub REST','quoted_text':summary_text[:12000],
             'kind':'github','truncated':len(summary_text)>12000},
            {'url':canonical+'#readme','title':f'{owner}/{repo} · README','quoted_text':raw[:readme_limit],
             'kind':'github','truncated':len(raw)>readme_limit},
        ]
    except (httpx.HTTPError,ValueError,TypeError,KeyError,IndexError):
        raise ValueError('No se pudo leer el repositorio público; puede usarse web_fetch') from None
