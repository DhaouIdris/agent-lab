"""Create a new RAG corpus from user-authorized UTF-8 plain text files."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

def sentence_spans(text, chunk_chars, overlap):
    """Prefer sentence boundaries, falling back to words for oversized sentences.

    Offsets are Python string offsets; overlap is a maximum, not a guarantee.
    A lightweight heuristic, not linguistic sentence segmentation.
    """
    boundaries = [0]
    for match in re.finditer(r'[.!?]+[”»\"\')\]]*(?=\s|$)|\n\s*\n', text):
        end=match.end()
        # A period following a single initial or a common abbreviation is not a split.
        prefix=text[max(0,end-8):end].lower()
        if re.search(r'\b(?:m|mme|dr|pr|st|etc|ex)\.$',prefix):
            continue
        while end<len(text) and text[end].isspace():end+=1
        if end>boundaries[-1]:boundaries.append(end)
    if boundaries[-1]!=len(text):boundaries.append(len(text))
    start=0
    while start<len(text):
        limit=min(len(text),start+chunk_chars)
        candidates=[x for x in boundaries if start<x<=limit]
        if candidates:
            end=max(candidates)
        else:
            end=limit
            if end<len(text):
                space=text.rfind(' ',start+chunk_chars//2,end)
                if space>start:end=space+1
        yield start,end
        if end==len(text):break
        eligible=[x for x in boundaries if start<x<end and x>=end-overlap]
        start=min(eligible) if eligible else end


def build_corpus(manifest_path,chunk_chars=800,overlap=120,split_mode='characters'):

    if type(chunk_chars)!=int or type(overlap)!=int or not 100<=chunk_chars<=4000 or not 0<=overlap<chunk_chars//2:
        raise ValueError('Invalid chunk parameters')
    if split_mode not in ('characters','sentences'):raise ValueError('Invalid split mode')
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
        sha=hashlib.sha256(raw).hexdigest();index=0
        def legacy_spans():
            start=0
            while start<len(text):
                end=min(len(text),start+chunk_chars)
                if end<len(text):
                    boundary=text.rfind(' ',start+chunk_chars//2,end)
                    if boundary>start:end=boundary
                yield start,end
                if end==len(text):break
                start=max(start+1,end-overlap)
        spans=sentence_spans(text,chunk_chars,overlap) if split_mode=='sentences' else legacy_spans()
        for start,end in spans:
            excerpt=text[start:end]
            if excerpt.strip():
                index+=1
                docs.append({'id':f"{doc['id']}__{index:04}",'source_doc_id':doc['id'],'chunk_index':index,
                    'start_char':start,'end_char':end,'source_file_sha256':sha,'title':doc['title'],'text':excerpt,
                    'url':doc['url'],'publisher':doc['publisher'],'consulted_at':doc['consulted_at'],
                    'source_updated_at':doc.get('source_updated_at'),'content_type':'user_supplied_text',
                    'license_note':doc['license_note'],'rights_confirmed_by_user':True})
    return docs

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--chunk-chars',type=int,default=800);p.add_argument('--overlap',type=int,default=120)
    p.add_argument('--split-mode',choices=('characters','sentences'),default='characters')
    args=p.parse_args();out=Path(args.out)
    if out.exists():p.error('Output already exists')
    docs=build_corpus(args.manifest,args.chunk_chars,args.overlap,split_mode=args.split_mode)
    with out.open('x',encoding='utf-8') as f:json.dump(docs,f,ensure_ascii=False,indent=2)
    print(json.dumps({'documents':len({d['source_doc_id'] for d in docs}),'passages':len(docs),'output':str(out)},ensure_ascii=False))

if __name__=='__main__':main()
