"""Resolve an explicitly named starting place, without guessing among matches."""
import json
import math
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from experiments.injection_guard import normalize
from experiments.route_service import valid_coordinates

GEOCODER='https://api.heigit.org/pelias/v1/search'
_ORIGIN=re.compile(
    r'\b(?:(?:je suis|je me trouve|je loge)\s+(?:à|a|au|aux|chez|dans)|je pars\s+(?:de|du|de la)|depuis)\s+'
    r'(.+?)(?:,\s*(?=(?:quel|quelle|où|ou|tu|je cherche|y a)\b)|[;?]|\.\s+|\s+et\s+(?=(?:quel|quelle|où|ou|tu|je)\b))',re.I)
_TYPE=re.compile(r'\b(?:restaurants?|restos?|cafés?|hotels?|hôtels?|bars?|glaciers?|fast[ -]?foods?)\b',re.I)
_NEAR=re.compile(r'\b(?:plus proche|près|pres|à côté|a cote|pas loin|autour)\b',re.I)


def named_origin_request(question):
    """Only accept a clear first-person origin and an explicit nearby place type."""
    m=_ORIGIN.search(question)
    if not m or not _TYPE.search(question[m.end():]) or not _NEAR.search(question[m.end():]):
        return None
    name=m.group(1).strip(' .\u00a0')
    name=re.sub(r"^(?:l['’]\s*|le\s+|la\s+)", '', name,flags=re.I)
    if not 4<=len(name)<=120 or re.search(r'[\r\n<>]',name):
        return None
    return name


def local_origin(db_path, name):
    """A unique catalogue name match is enough; multiple matches need clarification."""
    term=normalize(name)
    category=next((value for prefix,value in (('hotel ','hotel'),('restaurant ','restaurant'),('cafe ','cafe'))
                   if term.startswith(prefix)),None)
    term=re.sub(r'^(?:hotel|hôtel|restaurant|cafe)\s+', '', term)
    if len(term)<4:return {'status':'not_found'}
    con=sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        rows=[dict(row) for row in con.execute(
            'SELECT source_id,name,district,latitude,longitude FROM places WHERE instr(name_norm,?)>0'
            + (' AND category=?' if category else '')+' ORDER BY name_norm,source_id LIMIT 6',
            (term,category) if category else (term,))]
    finally:con.close()
    rows=[row for row in rows if valid_coordinates((row['latitude'],row['longitude']))]
    exact=[row for row in rows if normalize(row['name'])==term]
    if exact:rows=exact
    else:
        prefix=[row for row in rows if normalize(row['name']).startswith(term+' ')]
        if prefix:rows=prefix
    if len(rows)>1:return {'status':'ambiguous','choices':[{'name':r['name'],'district':r['district']} for r in rows[:4]]}
    if not rows:return {'status':'not_found'}
    row=rows[0]
    return {'status':'ok','name':row['name'],'location':(row['latitude'],row['longitude']),
            'source':'catalogue','source_id':row['source_id']}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def geocode_origin(name, api_key, opener=None, timeout=8):
    """Bounded Côte d'Ivoire search; send no keys or coordinates back to the model."""
    if not isinstance(api_key,str) or not api_key.strip():return {'status':'unavailable','reason':'missing_key'}
    if not isinstance(name,str) or not 4<=len(name)<=120:return {'status':'not_found'}
    requested_number=re.match(r'^\s*(\d+[A-Za-z]?)\s+',name)
    url=GEOCODER+'?'+urllib.parse.urlencode({'text':name,'boundary.country':'CIV',
                                              'layers':'venue,address','size':5})
    req=urllib.request.Request(url,headers={'Authorization':api_key,'Accept':'application/json'})
    try:
        with (opener or urllib.request.build_opener(_NoRedirect())).open(req,timeout=max(.1,min(timeout,8))) as response:
            raw=response.read(1000001)
        if len(raw)>1000000:return {'status':'unavailable','reason':'oversized_response'}
        data=json.loads(raw)
        features=data['features']
        if not isinstance(features,list):raise ValueError()
        matches=[]
        rejected={'wrong_country':0,'unsupported_layer':0,'low_confidence':0,
                  'wrong_house_number':0,'invalid_record':0}
        layers={};match_types={}
        for feature in features[:5]:
            try:
                props=feature['properties']; lon,lat=feature['geometry']['coordinates'][:2]
                if not isinstance(props,dict):raise ValueError()
            except (KeyError,IndexError,TypeError,ValueError):
                rejected['invalid_record']+=1
                continue
            label=props.get('label')
            country=props.get('country_a')
            confidence=props.get('confidence')
            layer=props.get('layer');match_type=props.get('match_type')
            if isinstance(layer,str) and layer in ('venue','address','street','neighbourhood','locality','localadmin','region','country'):
                layers[layer]=layers.get(layer,0)+1
            if isinstance(match_type,str) and match_type in ('exact','interpolated','fallback'):
                match_types[match_type]=match_types.get(match_type,0)+1
            if (not isinstance(label,str) or len(label)>180 or
                    not valid_coordinates((lat,lon))):
                rejected['invalid_record']+=1
                continue
            if country not in ('CIV','CI'):
                rejected['wrong_country']+=1
                continue
            if layer not in ('venue','address'):
                rejected['unsupported_layer']+=1
                continue
            if (type(confidence) not in (int,float) or not math.isfinite(confidence)
                    or confidence<.8):
                rejected['low_confidence']+=1
                continue
            if requested_number and str(props.get('housenumber','')).casefold()!=requested_number.group(1).casefold():
                rejected['wrong_house_number']+=1
                continue
            matches.append({'name':label,'location':(lat,lon),'source':'geocoding'})
        if len(matches)>1:return {'status':'ambiguous','choices':[{'name':x['name']} for x in matches[:4]]}
        if matches:return {'status':'ok',**matches[0]}
        return {'status':'not_found','reason':'no_results' if not features else 'no_confident_match',
                'candidate_count':len(features),
                'diagnostics':{'layers':layers,'match_types':match_types,'rejected':rejected}}
    except urllib.error.HTTPError as exc:
        return {'status':'unavailable','reason':'rate_limited' if exc.code==429 else
                'authentication_or_quota' if exc.code in (401,403) else 'service_error'}
    except (urllib.error.URLError,TimeoutError,OSError):
        return {'status':'unavailable','reason':'transport'}
    except (ValueError,KeyError,IndexError,TypeError):
        return {'status':'unavailable','reason':'response_format'}
