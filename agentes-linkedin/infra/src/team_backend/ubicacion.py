"""Where a LinkedIn member says they are: the United States, Latin America or elsewhere, from the location text.

Gustavo, 12/11/2026: the neighborhood is built to position him in the United States («la idea es que linkedin nos
mande a posicionarnos allá»). A buyer must be there; the rest of the community goes first when it is there and may
also come from Latin America («preferiblemente comunidad USA»). LinkedIn writes locations in the member's language
and often without the country («New York City Metropolitan Area», «San Francisco Bay Area»), so states and the big
metropolitan areas count as the United States. An empty or unknown text is None: no rule may guess it."""
import re
import unicodedata

US_STATES=('alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho '
           'illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi '
           'missouri montana nebraska nevada ohio oklahoma oregon pennsylvania tennessee texas utah vermont virginia '
           'washington wisconsin wyoming').split()+['new hampshire','new jersey','new mexico','new york','north carolina',
           'north dakota','rhode island','south carolina','south dakota','west virginia','district of columbia','puerto rico']
US_COUNTRY=['united states','estados unidos','usa','u.s.','u.s.a.','eeuu','ee. uu.','ee.uu.']
# Cities and metropolitan areas; a Latin American country in the same text wins («San José, Costa Rica»).
US_PLACES=['bay area','silicon valley',
           'new york city','nueva york','los angeles','san francisco','san diego','san jose','miami','boston','chicago',
           'seattle','austin','houston','dallas','atlanta','denver','philadelphia','phoenix','orlando','tampa','nashville',
           'washington dc','washington d.c.','raleigh','salt lake city','portland, oregon','fort lauderdale']
# Places that share a US state's name: «Georgia» alone is ambiguous with the country, so its capital decides.
NOT_US=['tbilisi','tiflis']
LATAM=['argentina','bolivia','brasil','brazil','chile','colombia','costa rica','cuba','ecuador','el salvador','guatemala',
       'honduras','mexico','méxico','nicaragua','panama','panamá','paraguay','peru','perú','republica dominicana',
       'república dominicana','dominican republic','uruguay','venezuela','bogota','bogotá','medellin','medellín','cali',
       'barranquilla','buenos aires','santiago de chile','lima','quito','guadalajara','monterrey','ciudad de mexico',
       'mexico city','caracas','montevideo','sao paulo','são paulo','rio de janeiro','san salvador']


def _plain(text):
    text=unicodedata.normalize('NFKD',(text or '').lower())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _has(text,place):
    place=_plain(place)
    return re.search(r'(?<![a-z])'+re.escape(place)+r'(?![a-z])',text) is not None


def region(location):
    """'us', 'latam', 'otro' or None (no location)."""
    text=_plain(location).strip()
    if not text:return None
    if any(_has(text,p) for p in NOT_US):return 'otro'
    # The country or a state settles it («New Mexico» is a state, «Mexico City» is not); then Latin America; then a
    # US city alone.
    if any(_has(text,p) for p in US_COUNTRY+US_STATES):return 'us'
    if any(_has(text,p) for p in LATAM):return 'latam'
    if any(_has(text,p) for p in US_PLACES):return 'us'
    return 'otro'


RANK={'us':0,'latam':1,'otro':2,None:3}

def rank(location):
    """Sort key: the United States first, then Latin America, then the rest and unknown."""
    return RANK[region(location)]
