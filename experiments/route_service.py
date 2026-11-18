"""Bounded read-only route calculation via the hosted openrouteservice API."""
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

ENDPOINT='https://api.heigit.org/openrouteservice/v2/directions/'
PROFILES={'car':'driving-car','walk':'foot-walking'}

def valid_coordinates(point):
    return (isinstance(point,(list,tuple)) and len(point)==2
            and all(type(v) in (int,float) and math.isfinite(v) for v in point)
            and -90<=point[0]<=90 and -180<=point[1]<=180)

def load_route_key():
    """Load the root .env without replacing an existing environment variable."""
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1]/'.env',override=False)
    return os.getenv('ORS_API_KEY','')


def route(origin, destination, mode, api_key, opener=None, timeout=12):
    if mode not in PROFILES or not isinstance(api_key,str) or not api_key.strip():
        return {'status':'unavailable','reason':'missing_key_or_invalid_mode'}
    coords=[]
    for point in (origin,destination):
        if not valid_coordinates(point):return {'status':'invalid_coordinates'}
        lat,lon=point
        coords.append([lon,lat])
    request=urllib.request.Request(ENDPOINT+PROFILES[mode]+'/json',data=json.dumps({'coordinates':coords,'instructions':False}).encode('utf-8'),headers={'Authorization':api_key,'Content-Type':'application/json','Accept':'application/json'},method='POST')
    try:
        # Reject redirects to ensure the credential is never forwarded to a new host.
        transport=opener or urllib.request.build_opener(_NoRedirect())
        with transport.open(request,timeout=timeout) as response:
            body=response.read(1000001)
        if len(body)>1000000: return {'status':'invalid_response'}
        data=json.loads(body)
        summary=data['routes'][0]['summary']; distance=summary['distance']; duration=summary['duration']
        if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (distance,duration)):return {'status':'invalid_response'}
        return {'status':'ok','distance_m':distance,'duration_s':duration,'mode':mode,
                'source':'openrouteservice / OpenStreetMap','traffic_verified':False}
    except urllib.error.HTTPError as exc:
        return {'status':'unavailable','reason':'rate_limited' if exc.code==429 else ('authentication_or_quota' if exc.code in (401,403) else 'service_error'),'http_status':exc.code}
    except (OSError,ValueError,KeyError,IndexError,TypeError,OverflowError):
        return {'status':'unavailable','reason':'transport_or_response'}

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
