"""Experimental CSV-to-SQLite catalogue; separate from the frozen agent benchmark."""
import argparse
import csv
import hashlib
import json
import math
import sqlite3
import unicodedata
from pathlib import Path

SOURCE="https://data.gouv.ci/datasets/hotels-et-restauration-en-cote-divoire"
ATTRIBUTION="© OpenStreetMap contributors; ODbL 1.0, https://www.openstreetmap.org/copyright"
CATEGORIES={"hotel":"hotel","hôtel":"hotel","cafe":"cafe","café":"cafe","restaurant":"restaurant","bar":"bar"}

def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))

def import_csv(csv_path,db_path):
    csv_path=Path(csv_path);db_path=Path(db_path)
    if db_path.exists():raise ValueError('Database already exists: choose a new output path')
    digest=hashlib.sha256()
    with csv_path.open('rb') as binary:
        for block in iter(lambda:binary.read(1024*1024),b''):digest.update(block)
    counts={'rows':0,'inserted':0,'rejected':0,'duplicates':0}
    con=sqlite3.connect(db_path)
    try:
        con.executescript('''CREATE TABLE places (source_id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, district TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL, name_norm TEXT NOT NULL, district_norm TEXT NOT NULL);
        CREATE INDEX places_category ON places(category); CREATE INDEX places_district ON places(district_norm);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
        with csv_path.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            required={'id','nom_de_l_etablissement','categorie','geometry','ville_ou_commune'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):raise ValueError('Unsupported CSV columns; expected HF dataset fields: '+', '.join(sorted(required)))
            for row in reader:
                counts['rows']+=1
                try:
                    source_id=(row['id'] or '').strip();name=(row['nom_de_l_etablissement'] or '').strip()
                    category=CATEGORIES.get((row['categorie'] or '').strip().casefold())
                    geo=json.loads(row['geometry']);coords=geo['coordinates']
                    if geo.get('type')!='Point' or len(coords)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) for x in coords):raise ValueError()
                    lon,lat=coords
                    if not (-90<=lat<=90 and -180<=lon<=180) or not source_id or not name or not category:raise ValueError()
                    district=(row['ville_ou_commune'] or '').strip()
                except (ValueError,TypeError,KeyError,IndexError,json.JSONDecodeError):
                    counts['rejected']+=1;continue
                cur=con.execute('INSERT OR IGNORE INTO places VALUES (?,?,?,?,?,?,?,?)',(source_id,name,category,district,lat,lon,norm(name),norm(district)))
                counts['inserted' if cur.rowcount else 'duplicates']+=1
        if counts['inserted']==0:raise ValueError('No usable records; database not created')
        meta={'source':SOURCE,'attribution':ATTRIBUTION,'source_published_update':'2022-09-23','file_sha256':digest.hexdigest(),'input_filename':csv_path.name,'counts':counts,'current_status_verified':False}
        con.executemany('INSERT INTO metadata VALUES (?,?)',[(k,json.dumps(v,ensure_ascii=False)) for k,v in meta.items()]);con.commit()
    except Exception:
        con.close();db_path.unlink(missing_ok=True);raise
    con.close();return meta

def search(db_path,category=None,district=None,query=None,limit=10):
    if not 1<=limit<=50:raise ValueError('limit must be 1..50')
    if category is not None and category not in set(CATEGORIES.values()):raise ValueError('unsupported category')
    if not Path(db_path).is_file():raise ValueError('Database does not exist')
    con=sqlite3.connect(Path(db_path).resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        clauses=[];params=[]
        if category:clauses.append('category=?');params.append(category)
        # Literal substring match; LIKE wildcards in user input have no special meaning.
        if district:clauses.append('instr(district_norm,?)>0');params.append(norm(district))
        if query:clauses.append('instr(name_norm,?)>0');params.append(norm(query))
        sql='SELECT source_id,name,category,district,latitude,longitude FROM places'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY name_norm,source_id LIMIT ?'
        params.append(limit)
        return {'items':[dict(x) for x in con.execute(sql,params)],'limit':limit,'current_status_verified':False,'warning':'Historical 2022 data; opening, availability and current activity are unverified; incomplete inventory.','source':SOURCE,'attribution':ATTRIBUTION}
    finally:con.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('import-csv');a.add_argument('--csv',required=True);a.add_argument('--db',required=True)
    a=s.add_parser('search');a.add_argument('--db',required=True);a.add_argument('--category',choices=['hotel','cafe','restaurant','bar']);a.add_argument('--district');a.add_argument('--query');a.add_argument('--limit',type=int,default=10)
    a=p.parse_args()
    result=import_csv(a.csv,a.db) if a.cmd=='import-csv' else search(a.db,a.category,a.district,a.query,a.limit)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
