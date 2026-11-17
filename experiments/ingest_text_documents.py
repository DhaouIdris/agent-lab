"""Create a new RAG corpus from user-authorized UTF-8 plain text files."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

def build_corpus(manifest_path,chunk_chars=800,overlap=120):
    if type(chunk_chars)!=int or type(overlap)!=int or not 100<=chunk_chars<=4000 or not 0<=overlap<chunk_chars//2:
        raise ValueError('Invalid chunk parameters')
    manifest_path=Path(manifest_path).resolve();root=manifest_path.parent
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if not isinstance(manifest,list) or not manifest:raise ValueError('Manifest must be a non-empty list')
    docs=[];seen=set()
    for doc in manifest:
        if not isinstance(doc,dict) or any(not isinstance(doc.get(k),str) or not doc[k].strip() for k in ('id','title','file','url','publisher','consulted_at','license_note')):
            raise ValueError('Missing required document metadata')
        if doc.get('rights_confirmed') is not True:raise ValueError('Each document must declare rights_confirmed=true')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',doc['id']) or doc['id'] in seen:raise ValueError('Invalid or duplicate document ID')
        seen.add(doc['id'])
        u=urlsplit(doc['url'])
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('URL must be HTTPS without credentials, query or fragment')
        path=(root/doc['file']).resolve()
        if not path.is_relative_to(root) or path.suffix.lower()!='.txt' or not path.is_file():raise ValueError('Document must be a .txt file inside the manifest directory')
        raw=path.read_bytes()
        if len(raw)>1000000:raise ValueError('Document exceeds 1 MB')
        text=raw.decode('utf-8-sig')
        if not text.strip():raise ValueError('Document is empty')
        sha=hashlib.sha256(raw).hexdigest();start=0;index=0
        while start<len(text):
            end=min(len(text),start+chunk_chars)
            if end<len(text):
                boundary=text.rfind(' ',start+chunk_chars//2,end)
                if boundary>start:end=boundary
            excerpt=text[start:end]
            if excerpt.strip():
                index+=1
                docs.append({'id':f"{doc['id']}__{index:04}",'source_doc_id':doc['id'],'chunk_index':index,
                    'start_char':start,'end_char':end,'source_file_sha256':sha,'title':doc['title'],'text':excerpt,
                    'url':doc['url'],'publisher':doc['publisher'],'consulted_at':doc['consulted_at'],
                    'source_updated_at':doc.get('source_updated_at'),'content_type':'user_supplied_text',
                    'license_note':doc['license_note'],'rights_confirmed_by_user':True})
            if end==len(text):break
            start=max(start+1,end-overlap)
    return docs

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--chunk-chars',type=int,default=800);p.add_argument('--overlap',type=int,default=120)
    args=p.parse_args();out=Path(args.out)
    if out.exists():p.error('Output already exists')
    docs=build_corpus(args.manifest,args.chunk_chars,args.overlap)
    with out.open('x',encoding='utf-8') as f:json.dump(docs,f,ensure_ascii=False,indent=2)
    print(json.dumps({'documents':len({d['source_doc_id'] for d in docs}),'passages':len(docs),'output':str(out)},ensure_ascii=False))

if __name__=='__main__':main()
