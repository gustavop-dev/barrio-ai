"""Deterministic content guards shared by the autonomous gates (comments INT-03 and own posts CONT-09).

Confirmed user memory carries `uso_publico` (knowledge.memory.confirmed_blocks): public facts may be
attributed to Gustavo; private guidance (priorities, audience segment, cadence, limits) only orients
decisions and must never appear or be paraphrased in public text. These checks back up the model
reviewer: they are narrow on purpose and block on the safe side."""
import json
import re
import unicodedata

# Private orientation from the internal brief (docs/brief-gustavo-posicionamiento.md, 2026-11-06). The editorial
# circuit adds it to the confirmed private memory so the director can use it and the verifier can catch leaks.
BASELINE_GUIDANCE=[
    {'key':'brief.prioridad','guidance':'Prioridad estratégica 60% oportunidades personales en startups / 40% contratos de '
     'ProjectApp. Orienta la elección de temas y modalidades; no es una cuota de posts ni se menciona.'},
    {'key':'brief.audiencia','guidance':'Foco inicial: founders de startups tempranas en EE. UU., preferentemente presemilla con '
     'inversión, con afinidad hispanohablante declarada y abierta a otros founders. Nunca se publica el segmento.'},
    {'key':'brief.limites','guidance':'Sin humo, sin temas que Gustavo no domina, sin experiencias, cifras ni clientes inventados. '
     'Remuneraciones, bandas salariales, LLC, cobros y la futura incorporación a Beloz nunca se publican.'},
]
PRIVATE=re.compile(r'\b60\s*/\s*40\b|\b60\s*%[^.\n]{0,80}\b40\s*%|\b40\s*%[^.\n]{0,80}\b60\s*%|hispanohablante|'
                   r'(?:spanish[- ]speaking|hispanic|latin[oa]s?|latinx|latam|latin[- ]american)\s+(?:founders?|ceos?|entrepreneurs?|startups?)|'
                   r'\$?\s?5[,.]?000\s*(?:-|–|to)\s*\$?\s?7[,.]?999|\bLLC\b|\bbeloz\b',re.I)
# First-person lived experience; with no public facts confirmed it cannot be attributed to Gustavo. Spanish
# forms matter because comments follow the language of the post and Gustavo's voice tells stories in first person.
EXPERIENCE=re.compile(r"\b(?:I|we)(?:'ve| have)?\s+(?:built|shipped|led|launched|delivered|migrated|scaled|grew|founded|hired|"
                      r"cut|reduced|increased|deployed|rebuilt|rewrote|implemented|designed|managed|closed|raised)\b|"
                      r"\b(?:my|our)\s+(?:clients?|customers?|team|startup|company|agency|project|projects|product)\b|"
                      r"\b(?:last|this)\s+(?:year|month|week|quarter)\s+(?:I|we)\b|"
                      r"\b(?:constru[ií]|lanc[ée]|lider[ée]|implement[ée]|dise[ñn][ée]|migr[ée]|escal[ée]|fund[ée]|contrat[ée]|"
                      r"desplegu[ée]|reescrib[ií]|entregu[ée]|constru[ií]mos|lanzamos|lideramos|implementamos|dise[ñn]amos|"
                      r"migramos|escalamos|fundamos|contratamos|desplegamos|reescribimos|entregamos)\b|"
                      r"\b(?:mis|mi|nuestr[oa]s?)\s+(?:clientes?|equipo|startup|empresa|agencia|proyectos?|producto)\b",re.I)

def blocks():
    """(public_facts, private_guidance): confirmed memory, the brief's private orientation and Gustavo's current
    orientation, so the leak checks also protect what he tells the team."""
    from knowledge import memory
    from .orientacion import text
    public,private=memory.confirmed_blocks()
    current=text()
    return public,private+BASELINE_GUIDANCE+([{'key':'orientacion','guidance':current}] if current else [])

def _words(value):
    raw=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    return re.findall(r'[a-z0-9áéíóúñü]+',raw.lower())

def _shingles(value,n=6):
    words=_words(value)
    return {' '.join(words[i:i+n]) for i in range(len(words)-n+1)}

def private_leaks(text,private_guidance=()):
    """Reasons why `text` would expose private guidance; empty when it does not."""
    reasons=[]
    if PRIVATE.search(text or ''):reasons.append('Deja traslucir orientación privada de Gustavo (prioridades, segmento o condiciones)')
    shingles=_shingles(text or '')
    for item in private_guidance:
        if shingles & _shingles(item.get('guidance','')):
            reasons.append(f'Reproduce orientación privada ({item.get("key")})');break
    return reasons

# Comparing a claim with the facts: words that carry no evidence (function words in English and Spanish, time words and
# the experience verbs themselves: a fact that says «built» does not support every «I built»).
STOP=frozenset('''a about after again ago all also an and any are as at back be because been before but by can could did do does
done each even every first for from had has have he her here him his how i if in into is it its just last like lot made make many
me more most much my no not of off on one only or other our out over really same she should since so some still such than that the
their them then there these they thing things this those three time times to two under up us very was way we were what when where
which while who why will with would year years month months week weeks quarter day days you your
al algo algun alguna alguno anos ano aqui asi cada como con cuando de del desde donde el ella ellos en entre era es esa ese eso esta
estas este esto estos fue habia hace hasta hizo la las le les lo los mas me mes meses mi mis muy nos nosotros nuestra nuestras
nuestro nuestros o otra otro para pasado pasada pero por porque que se semana semanas ser si sin sobre son su sus tambien tiene todo
todos toda todas tu un una uno unos unas ya yo
built shipped led launched delivered migrated scaled grew founded hired cut reduced increased deployed rebuilt rewrote implemented
designed managed closed raised ve construi lance lidere implemente disene migre escale funde contrate desplegue reescribi entregue
construimos lanzamos lideramos implementamos disenamos migramos escalamos fundamos contratamos desplegamos reescribimos
entregamos'''.split())
# Bilingual families, so a fact written in Spanish supports a claim in English and vice versa. Having a team, a company
# or clients is one family: any confirmed organisation of Gustavo supports «my team», «our clients» or «mi empresa».
FAMILY={**dict.fromkeys('''team equipo company companie empresa agency agencie agencia studio estudio startup founder fundador fundadora
cofounder client cliente customer'''.split(),'organizacion'),
        **dict.fromkeys('product producto project proyecto'.split(),'producto'),'ai':'ia'}
NUMBER=re.compile(r'\d+(?:[.,]\d+)*')
SENTENCE=re.compile(r'(?<=[.!?])\s+|\n+')
MAX_CLAIMS=3

def _plain(value):
    raw=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    return ''.join(c for c in unicodedata.normalize('NFKD',raw.lower()) if not unicodedata.combining(c))

def _evidence(value):
    """Content words of a text, accent-free, plural-folded and mapped to their bilingual family."""
    words=set()
    for word in re.findall(r'[a-z][a-z0-9]+',_plain(value)):
        word=word[:-1] if len(word)>4 and word.endswith('s') else word
        if word not in STOP:words.add(FAMILY.get(word,word))
    return words

def _numbers(value):
    return {re.sub(r'[.,]','',n) for n in NUMBER.findall(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False))}

def _fact_text(fact):
    """A public fact as text: its value and the words of its memory key (e.g. trayectoria.projectapp)."""
    if not isinstance(fact,dict):return _plain(fact)
    return ' '.join([str(fact.get('key','')).replace('.',' ').replace('_',' '),_plain(fact.get('fact',''))])

def experience_claims(text):
    """First-person experience claims: (sentence, trigger) for each sentence that attributes lived experience."""
    claims=[]
    for sentence in SENTENCE.split(text or ''):
        match=EXPERIENCE.search(sentence)
        if match:claims.append((sentence.strip(),match.group(0)))
    return claims

def invented_experience(text,public_facts):
    """Reasons why `text` attributes experience to Gustavo that his confirmed public facts do not support.
    With no public facts, any first-person experience is invented. With facts, each claim (the sentence around the
    trigger) is compared with them and flagged only when nothing backs it: a number about his work that no fact
    contains, or neither a content word nor a number in common with any fact. Narrow on purpose (one shared word is
    enough, and having a team, company or clients counts as one family): the verifier stays the main judge."""
    claims=experience_claims(text)
    if not public_facts:
        return [f'Atribuye experiencia a Gustavo sin hechos públicos confirmados («{trigger}»)' for _,trigger in claims[:MAX_CLAIMS]]
    facts=' '.join(_fact_text(f) for f in public_facts)
    known_words,known_numbers=_evidence(facts),_numbers(facts)
    reasons=[]
    for sentence,trigger in claims:
        quote=sentence if len(sentence)<=160 else sentence[:157]+'...'
        numbers=_numbers(sentence);figures=sorted(numbers-known_numbers)
        if figures:reasons.append(f'Cifra sobre el trabajo de Gustavo que no consta en sus hechos públicos («{figures[0]}» en «{quote}»)')
        elif not (_evidence(sentence)&known_words or numbers&known_numbers):
            reasons.append(f'Atribuye a Gustavo una experiencia que no consta en sus hechos públicos («{quote}»)')
        if len(reasons)>=MAX_CLAIMS:break
    return reasons
