"""Bounded read-only route calculation via the hosted openrouteservice API."""
import json
import math
import os
import random
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

ENDPOINT='https://api.heigit.org/openrouteservice/v2/directions/'
MATRIX_ENDPOINT='https://api.heigit.org/openrouteservice/v2/matrix/'
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
    # One route lookup has a single deadline across all attempts, not 12 seconds per retry.
    deadline=time.monotonic()+max(0,timeout)
    transport=opener or urllib.request.build_opener(_NoRedirect())
    last={'status':'unavailable','reason':'timeout','attempts':0}
    for attempt in range(1,4):
        remaining=deadline-time.monotonic()
        if remaining<=0:return last
        try:
            # Reject redirects to ensure the credential is never forwarded to a new host.
            with transport.open(request,timeout=max(.1,min(6,remaining))) as response:
                body=response.read(1000001)
            if len(body)>1000000:return {'status':'invalid_response','attempts':attempt}
            data=json.loads(body)
            summary=data['routes'][0]['summary']; distance=summary['distance']; duration=summary['duration']
            if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in (distance,duration)):
                return {'status':'invalid_response','attempts':attempt}
            return {'status':'ok','distance_m':distance,'duration_s':duration,'mode':mode,
                    'source':'openrouteservice / OpenStreetMap','traffic_verified':False,'attempts':attempt}
        except urllib.error.HTTPError as exc:
            last={'status':'unavailable','reason':'rate_limited' if exc.code==429 else (
                  'authentication_or_quota' if exc.code in (401,403) else 'service_error'),
                  'http_status':exc.code,'attempts':attempt}
            if exc.code not in (500,502,503,504):return last
        except (TimeoutError,socket.timeout):
            last={'status':'unavailable','reason':'timeout','attempts':attempt}
        except OSError:
            last={'status':'unavailable','reason':'transport','attempts':attempt}
        except (ValueError,KeyError,IndexError,TypeError,OverflowError):
            last={'status':'invalid_response','reason':'response_format','attempts':attempt}
        if attempt==3:return last
        delay=random.uniform(0,min(1,0.25*2**(attempt-1)))
        if time.monotonic()+delay>=deadline:return last
        time.sleep(delay)
    return last

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def matrix(origin, destinations, mode, api_key, opener=None, timeout=12):
    """One-to-many route distances; never return the supplied coordinates or key."""
    if mode not in PROFILES or not isinstance(api_key,str) or not api_key.strip():
        return {'status':'unavailable','reason':'missing_key_or_invalid_mode'}
    if not valid_coordinates(origin) or not isinstance(destinations,(list,tuple)) or not 1<=len(destinations)<=50 or any(not valid_coordinates(p) for p in destinations):
        return {'status':'invalid_coordinates'}
    locations=[[p[1],p[0]] for p in [origin,*destinations]]
    payload={'locations':locations,'sources':['0'],
             'destinations':[str(i) for i in range(1,len(locations))],
             'metrics':['distance','duration']}
    request=urllib.request.Request(MATRIX_ENDPOINT+PROFILES[mode],data=json.dumps(payload).encode('utf-8'),
                                   headers={'Authorization':api_key,'Content-Type':'application/json','Accept':'application/json'},method='POST')
    transport=opener or urllib.request.build_opener(_NoRedirect())
    deadline=time.monotonic()+max(0,timeout)
    last={'status':'unavailable','reason':'timeout','attempts':0}
    for attempt in range(1,4):
        remaining=deadline-time.monotonic()
        if remaining<=0:return last
        try:
            with transport.open(request,timeout=max(.1,min(6,remaining))) as response:
                body=response.read(1000001)
            if len(body)>1000000:return {'status':'invalid_response','attempts':attempt}
            data=json.loads(body)
            distances=data['distances'][0];durations=data['durations'][0]
            if (not isinstance(distances,list) or not isinstance(durations,list)
                    or len(distances)!=len(destinations) or len(durations)!=len(destinations)):
                return {'status':'invalid_response','attempts':attempt}
            for distance,duration in zip(distances,durations):
                if (distance is None and duration is None):continue
                if (type(distance) not in (int,float) or type(duration) not in (int,float)
                        or not all(math.isfinite(x) and x>=0 for x in (distance,duration))):
                    return {'status':'invalid_response','attempts':attempt}
            return {'status':'ok','distances_m':distances,'durations_s':durations,
                    'source':'openrouteservice / OpenStreetMap','traffic_verified':False,'attempts':attempt}
        except urllib.error.HTTPError as exc:
            last={'status':'unavailable','reason':'rate_limited' if exc.code==429 else (
                  'authentication_or_quota' if exc.code in (401,403) else 'service_error'),
                  'http_status':exc.code,'attempts':attempt}
            if exc.code not in (500,502,503,504):return last
        except (TimeoutError,socket.timeout):
            last={'status':'unavailable','reason':'timeout','attempts':attempt}
        except OSError:
            last={'status':'unavailable','reason':'transport','attempts':attempt}
        except (ValueError,KeyError,IndexError,TypeError,OverflowError):
            return {'status':'invalid_response','attempts':attempt}
        if attempt==3:return last
        delay=random.uniform(0,min(1,0.25*2**(attempt-1)))
        if time.monotonic()+delay>=deadline:return last
        time.sleep(delay)
    return last
