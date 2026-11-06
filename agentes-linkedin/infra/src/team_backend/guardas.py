"""Deterministic content guards shared by the autonomous gates (comments INT-03 and own posts CONT-09).

Confirmed user memory carries `uso_publico` (knowledge.memory.confirmed_blocks): public facts may be
attributed to Gustavo; private guidance (priorities, audience segment, cadence, limits) only orients
decisions and must never appear or be paraphrased in public text. These checks back up the model
reviewer: they are narrow on purpose and block on the safe side."""
import json
import re

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
# First-person lived experience; with no public facts confirmed it cannot be attributed to Gustavo.
EXPERIENCE=re.compile(r"\b(?:I|we)(?:'ve| have)?\s+(?:built|shipped|led|launched|delivered|migrated|scaled|grew|founded|hired|"
                      r"cut|reduced|increased|deployed|rebuilt|rewrote|implemented|designed|managed|closed|raised)\b|"
                      r"\b(?:my|our)\s+(?:clients?|customers?|team|startup|company|agency|project|projects|product)\b|"
                      r"\b(?:last|this)\s+(?:year|month|week|quarter)\s+(?:I|we)\b",re.I)

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

def invented_experience(text,public_facts):
    """With no publishable facts confirmed, first-person experience cannot be Gustavo's."""
    if public_facts:return []
    match=EXPERIENCE.search(text or '')
    return [f'Atribuye experiencia a Gustavo sin hechos públicos confirmados («{match.group(0)}»)'] if match else []
