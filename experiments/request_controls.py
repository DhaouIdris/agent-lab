"""Local request checks. These are bounded baselines, not a complete PII or emergency classifier."""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

from experiments.injection_guard import normalize


_EMAIL = re.compile(r'(?<![\w.])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?!\w)', re.I)
_IBAN = re.compile(r'\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b', re.I)
_NIR = re.compile(r'\b[12][ ]?\d{2}[ ]?(?:0[1-9]|1[0-2])[ ]?\d{2}[ ]?\d{3}[ ]?\d{3}[ ]?\d{2}\b')
_PHONE = re.compile(r'(?<!\w)(?:\+225[ .-]?(?:\d[ .-]?){10}|\+33[ .-]?[1-9](?:[ .-]?\d{2}){4}|0[1-9](?:[ .-]?\d{2}){4})(?!\w)')
_PASSPORT = re.compile(r'\b(?:passeport|passport)\s*(?:n[°o.]?\s*|number\s*|[:#]\s*)[A-Z0-9]{6,12}\b',re.I)
_CARD = re.compile(r'(?<!\d)(?:\d[ -]?){13,19}(?!\d)')
_URGENT = re.compile(r'\b(?:je (?:fais un malaise|ne respire plus|suis en train de mourir|suis attaque[e]?|saigne abondamment)|'
                     r'quelqu.un (?:ne respire plus|est inconscient)|au secours[, !]*.*(?:incendie|agression)|'
                     r'i (?:can.t breathe|am being attacked)|someone (?:is unconscious|is not breathing)|'
                     r'j.ai (?:une )?(?:douleur thoracique|douleur a la poitrine).{0,80}(?:evanouis|perds connaissance)|'
                     r'on me menace.{0,50}(?:arme|couteau|pistolet)|'
                     r'(?:my friend|someone).{0,80}(?:collapsed|will not wake up)|'
                     r'(?:feu|incendie) (?:dans|chez) (?:mon|ma|notre) (?:appartement|maison|immeuble|domicile)|'
                     r'(?:fumee|smoke)(?: noire)? (?:qui )?(?:sort|sortent|s.echappe|coming out)\s+(?:de|des|du|par|from)\b.{0,100}(?:fenetres?|immeuble|batiment|salle|appartement)|'
                     r'alarme incendie.{0,35}(?:declenche|retentit).{0,100}(?:fumee|smoke)|'
                     r'(?:collision frontale|accident frontal).{0,65}(?:violente?|grave|bless|voitur))\b')


def _luhn(number):
    digits=[int(x) for x in number if x.isdigit()]
    if not 13<=len(digits)<=19:return False
    total=0
    for i,digit in enumerate(reversed(digits)):
        if i%2:
            digit*=2
            if digit>9:digit-=9
        total+=digit
    return total%10==0


def redact_pii(message: str) -> str:
    """Mask common explicit formats; false negatives require a stronger upstream service."""
    result=message
    for pattern,tag in ((_EMAIL,'[EMAIL_MASQUÉ]'),(_IBAN,'[IBAN_MASQUÉ]'),
                        (_NIR,'[NIR_MASQUÉ]'),(_PASSPORT,'[PASSEPORT_MASQUÉ]'),
                        (_PHONE,'[TELEPHONE_MASQUÉ]')):
        result=pattern.sub(tag,result)
    return _CARD.sub(lambda m:'[CARTE_MASQUÉE]' if _luhn(m.group()) else m.group(),result)


def check_emergency_intent(message: str) -> bool:
    return bool(_URGENT.search(normalize(message)))


def emergency_response(territory: str = 'CI', message: str = '') -> str:
    english=bool(re.search(r'\b(?:i|my friend|someone)\b',normalize(message)))
    if territory == 'CI':
        if english:
            return ('If you are in Côte d’Ivoire and this is an immediate emergency, '
                    'call 185 (medical emergency), 180 (fire service) or 100 (police), as appropriate.')
        return ('Si vous êtes en Côte d’Ivoire et qu’il s’agit d’une urgence immédiate, '
                'appelez le 185 (SAMU), le 180 (pompiers) ou le 100 (police), selon la situation.')
    if english:return 'If you are in immediate danger, call your local emergency services.'
    return 'En cas de danger immédiat, appelez les services d’urgence de votre pays.'


def resolve_temporal_context(message: str, current_ts: datetime | None = None,
                             timezone: str = 'Africa/Abidjan') -> dict:
    zone=ZoneInfo(timezone)
    now=(current_ts or datetime.now(zone)).astimezone(zone)
    text=normalize(message)
    dates={}
    if re.search(r'\b(?:aujourd.hui|today|maintenant|now)\b',text):dates['today']=now.date().isoformat()
    if re.search(r'\b(?:demain|tomorrow)\b',text):dates['tomorrow']=(now.date()+timedelta(days=1)).isoformat()
    if re.search(r'\b(?:ce week.end|this weekend)\b',text):
        saturday=now.date()+timedelta(days=(5-now.weekday())%7)
        dates['weekend']=[saturday.isoformat(),(saturday+timedelta(days=1)).isoformat()]
    return {'territory_timezone':timezone,'current_datetime_iso':now.isoformat(),
            'resolved_dates':dates,'holidays':'unavailable_without_verified_calendar'}
