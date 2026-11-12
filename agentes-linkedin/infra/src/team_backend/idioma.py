"""Spanish or English, from the most frequent short words of a text.

The language rule of comments and replies (Gustavo, 2026-11-12: «cuando el post o la conversación está en español,
responder en español»). The lead asked Jev whether the comment and the post share a language, and Jev scored an English
comment under an English post at 0.04, so the check is deterministic and free. `detect` answers None when a text is too
short or too mixed to tell, and then no rule blocks on it."""
import re

WORD=re.compile(r"[a-záéíóúüñ]+(?:'[a-z]+)?")
# Words frequent in one language and rare in the other; shared or ambiguous ones («no», «a», «me», «son») are left out.
SPANISH=frozenset('el la los las del que y en un una unos unas por para con es lo al pero como más muy esto eso esa ese ya '
                  'también porque cuando sobre qué cómo yo tú tu mi su sus hay está están ser fue era sí algo todo cada '
                  'entre hasta desde donde parece siento creo vez otra otro ahí eso así bien'.split())
ENGLISH=frozenset("the and of to is that for with you it this are be on was but have what how if or my your we they at as "
                  "do can just about there their an by from i it's i'm don't would could should which when who been more "
                  "than then them these those into because".split())
MIN_WORDS=4  # marker words needed before deciding


def detect(text):
    """'es', 'en' or None."""
    text=(text or '').lower()
    words=WORD.findall(text)
    spanish=sum(w in SPANISH for w in words)+2*(text.count('¿')+text.count('¡'))
    english=sum(w in ENGLISH for w in words)
    if max(spanish,english)<MIN_WORDS:return None
    if spanish>=2*english:return 'es'
    if english>=2*spanish:return 'en'
    return None


def english_on_spanish(text,post_text):
    """True when a comment is clearly in English on a post clearly in Spanish. The reverse (Spanish on an English post)
    is right when the conversation under the post is in Spanish, which only the drafter sees, so it is not blocked."""
    return detect(post_text)=='es' and detect(text)=='en'


def mismatch(text,reference):
    """The language of `reference` when `text` is clearly in the other one, else None (a reply answers in the language
    of the comment it replies to)."""
    expected,got=detect(reference),detect(text)
    return expected if expected and got and got!=expected else None
