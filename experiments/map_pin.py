"""Loopback-only map pin pilot for nearby route ranking; no model or geocoder."""
import argparse
import json
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from experiments.nearby_places import CATEGORIES
from experiments.compare_nearby_shortlists import compare_case
from experiments.place_links import osm_place_url
from experiments.route_service import load_route_key, valid_coordinates
from experiments.unified_agent import ask, fetch_matrix, format_route_distance, format_route_duration

HERE=Path(__file__).resolve().parent
NAMES={'restaurant':'restaurants','cafe':'cafés','hotel':'hôtels','bar':'bars',
       'fast_food':'fast-foods','ice_cream':'glaciers'}
BOUNDS=(4.0,11.0,-9.0,-2.0)  # broad screening box, not a political boundary


def validated_pin(payload):
    if type(payload) is not dict or set(payload)!={'category','mode','lat','lon'}:
        return None,(400,{'status':'invalid_request','message':'Choisis un point et un type de lieu.'})
    category=payload['category'];mode=payload['mode'];origin=(payload['lat'],payload['lon'])
    if type(category) is not str or category not in CATEGORIES or mode not in ('walk','car'):
        return None,(400,{'status':'invalid_request','message':'Choisis un type de lieu et un mode valides.'})
    if not valid_coordinates(origin) or not (BOUNDS[0]<=origin[0]<=BOUNDS[1]
                                              and BOUNDS[2]<=origin[1]<=BOUNDS[3]):
        return None,(400,{'status':'invalid_location','message':'Choisis un point sur la carte en Côte d’Ivoire.'})
    return (category,mode,origin),None


def nearby_from_pin(payload,db,matrix_service=fetch_matrix):
    """Validate untrusted browser input before invoking the existing read-only agent route."""
    parsed,error=validated_pin(payload)
    if error:return error
    category,mode,origin=parsed
    question=f"Quels {NAMES[category]} sont proches de moi {'en voiture' if mode=='car' else 'à pied'} ?"
    result=ask(None,db,[],question,user_location=origin,matrix_service=matrix_service)
    if result['output']['abstain']:
        return 200,{'status':result.get('guard_status','unavailable'),
                    'message':result['output']['answer'],'places':[]}
    ranked=next((row.get('result',{}).get('ranked',[]) for row in result['trace']
                 if row.get('tool')=='rank_nearby'),[])
    if not ranked:
        return 503,{'status':'unavailable','message':'Je ne peux pas afficher ces trajets pour le moment.'}
    return 200,{'status':'ok','places':[{'name':item['name'],
        'url':osm_place_url(item['source_id']),
        'distance':format_route_distance(item['distance_m']),
        'duration':format_route_duration(item['duration_s'])} for item in ranked],
        'mode':mode}


def compare_from_pin(payload,db,matrix_service=fetch_matrix):
    """On request, compare 12 versus 50 candidates with a single bounded matrix call."""
    parsed,error=validated_pin(payload)
    if error:return error
    category,mode,origin=parsed
    case={'id':'PIN','category':category,'mode':mode,'origin':origin}
    def routed_matrix(point,destinations,travel_mode,key,timeout):
        return matrix_service(point,destinations,travel_mode,timeout=timeout)
    public,private=compare_case(case,db,'',matrix_service=routed_matrix)
    if public['status']!='ok':
        return 200,{'status':public['status'],
                    'message':'Je ne peux pas comparer ces trajets pour le moment.','places':[]}
    if not private['wide_top3']:
        return 200,{'status':'no_reachable_candidates',
                    'message':'Aucun trajet vers ces lieux n’a pu être calculé.','places':[]}
    def named(rows):
        return [{'name':p['name'],'url':osm_place_url(p['source_id']),
                 'distance':format_route_distance(p['distance_m'])} for p in rows]
    return 200,{'status':'ok','short':named(private['short_top3']),
                'wide':named(private['wide_top3']),
                'matching_in_radius':public['matching_in_radius'],
                'candidate_count':public['candidate_count'],
                'nearest_regret':(format_route_distance(public['nearest_regret_m'])
                                  if public['nearest_regret_m'] is not None else None),
                'top3_changed':public['wide_top3_missing_from_short']>0}


def make_handler(db,token,matrix_service=fetch_matrix,clock=time.monotonic):
    """Keep request data and the ORS key out of HTTP responses and access logs."""
    class Handler(BaseHTTPRequestHandler):
        last_request=0.0

        def log_message(self,format,*args):
            pass

        def respond(self,status,body,content_type):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
            self.send_header('Content-Security-Policy',
                "default-src 'none'; script-src 'self' https://cdn.jsdelivr.net; "
                "style-src 'self' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://cdn.jsdelivr.net https://tile.openstreetmap.org; "
                "connect-src 'self'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self,status,data):
            self.respond(status,json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8'),
                         'application/json; charset=utf-8')

        def do_GET(self):
            if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':
                self.send_error(403)
                return
            if self.path=='/':
                html=(HERE/'map_pin.html').read_text(encoding='utf-8').replace('__MAP_TOKEN__',token)
                self.respond(200,html.encode('utf-8'),'text/html; charset=utf-8')
            elif self.path in ('/map_pin.js','/map_pin.css'):
                content=(HERE/self.path[1:]).read_bytes()
                self.respond(200,content,'text/javascript; charset=utf-8' if self.path.endswith('.js')
                             else 'text/css; charset=utf-8')
            else:self.send_error(404)

        def do_POST(self):
            expected=f'http://127.0.0.1:{self.server.server_port}'
            if (self.path not in ('/api/nearby','/api/compare') or self.headers.get('Origin')!=expected
                    or self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}'
                    or self.headers.get('X-Map-Token')!=token):
                self.send_json(403,{'status':'forbidden'})
                return
            if self.headers.get('Content-Type','').split(';',1)[0].strip()!='application/json':
                self.send_json(415,{'status':'invalid_content_type'})
                return
            try:length=int(self.headers.get('Content-Length',''))
            except ValueError:length=0
            if not 1<=length<=512:
                self.send_json(413,{'status':'invalid_size'})
                return
            try:payload=json.loads(self.rfile.read(length))
            except (ValueError,UnicodeError):
                self.send_json(400,{'status':'invalid_json'})
                return
            now=clock()
            if now-self.__class__.last_request<1.5:
                self.send_json(429,{'status':'slow_down','message':'Attends un instant avant une autre recherche.'})
                return
            try:
                action=nearby_from_pin if self.path=='/api/nearby' else compare_from_pin
                status,response=action(payload,db,matrix_service)
            except (ValueError,sqlite3.Error,KeyError,TypeError):
                self.send_json(503,{'status':'unavailable','message':'La recherche est momentanément indisponible.'})
                return
            if status==200 and response['status']=='ok':self.__class__.last_request=now
            self.send_json(status,response)
    return Handler


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default='local_data/lieux.sqlite')
    p.add_argument('--port',type=int,default=8765)
    args=p.parse_args(argv)
    if not Path(args.db).is_file():p.error('Catalogue SQLite introuvable')
    if not 1024<=args.port<=65535:p.error('Port invalide')
    if not load_route_key():p.error('ORS_API_KEY absente du fichier .env ou de l’environnement')
    server=HTTPServer(('127.0.0.1',args.port),make_handler(args.db,secrets.token_urlsafe(32)))
    print(f'Ouvre http://127.0.0.1:{args.port}/ dans ton navigateur. Ctrl+C pour arrêter.',flush=True)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
