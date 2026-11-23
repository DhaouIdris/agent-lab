"""Bounded candidate selection before route-distance ranking."""
import math
import sqlite3
from pathlib import Path

from experiments.route_service import valid_coordinates

CATEGORIES={'restaurant','cafe','hotel','bar','fast_food','ice_cream'}
MAX_CANDIDATES=12
MAX_COMPARISON_CANDIDATES=50
RADIUS_KM=10


def air_distance_km(a,b):
    """Only a cheap shortlist heuristic; never show this as a travel distance."""
    lat1,lon1=map(math.radians,a)
    lat2,lon2=map(math.radians,b)
    delta=lat2-lat1;dlon=lon2-lon1
    h=math.sin(delta/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 12742*math.asin(min(1,math.sqrt(h)))


def candidates(db_path, origin, category, limit=MAX_CANDIDATES):
    if (not valid_coordinates(origin) or category not in CATEGORIES
            or type(limit) is not int or not 1<=limit<=MAX_COMPARISON_CANDIDATES):
        raise ValueError('Invalid nearby query')
    con=sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    cursor=None
    try:
        cursor=con.execute('SELECT source_id,name,category,district,latitude,longitude FROM places WHERE category=?',(category,))
        matched=[]
        for row in cursor:
            place=dict(row)
            pos=(place['latitude'],place['longitude'])
            if not valid_coordinates(pos):continue
            distance=air_distance_km(origin,pos)
            if distance<=RADIUS_KM:matched.append((distance,place['source_id'],place))
        matched.sort(key=lambda item:(item[0],item[1]))
        return [place for _,_,place in matched[:limit]],len(matched)
    finally:
        if cursor is not None:cursor.close()
        con.close()
