import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from experiments.ingest_text_documents import build_corpus
from experiments.document_rag import load_corpus,retrieve

class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'notice.txt'
        self.text='Informations tourisme Côte d’Ivoire. '+('La visite est conditionnée à une autorisation. '*12)
        self.path.write_text(self.text,encoding='utf8')
        self.manifest=self.root/'manifest.json'
        self.doc={'id':'TEST_DOC','title':'Visite','file':'notice.txt','url':'https://example.org/notice',
            'publisher':'Test','consulted_at':'2026-11-17','license_note':'user confirms permission','rights_confirmed':True}
    def write(self,docs):self.manifest.write_text(json.dumps(docs),encoding='utf8')
    def test_chunks_preserve_offsets_hash_and_provenance(self):
        self.write([self.doc]);chunks=build_corpus(self.manifest,chunk_chars=100,overlap=10)
        self.assertGreater(len(chunks),1)
        for chunk in chunks:
            self.assertEqual(chunk['text'],self.text[chunk['start_char']:chunk['end_char']])
            self.assertEqual(chunk['source_file_sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())
            self.assertEqual(chunk['source_doc_id'],'TEST_DOC')
        file=self.root/'corpus.json';file.write_text(json.dumps(chunks,ensure_ascii=False),encoding='utf8')
        result=retrieve('autorisation visite',load_corpus(file))
        self.assertEqual(result[0]['source_doc_id'],'TEST_DOC')
        self.assertIn('source_file_sha256',result[0])
    def test_requires_explicit_rights_and_no_traversal(self):
        for update in ({'rights_confirmed':False},{'file':'../other.txt'},{'url':'https://example.org/?token=SECRET'},{'id':'../bad'}):
            self.write([{**self.doc,**update}])
            with self.subTest(update=update),self.assertRaises(ValueError):build_corpus(self.manifest)
    def test_duplicate_ids_rejected(self):
        self.write([self.doc,self.doc])
        with self.assertRaises(ValueError):build_corpus(self.manifest)

if __name__=='__main__':unittest.main()
