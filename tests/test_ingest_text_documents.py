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

class SentenceSplittingTests(unittest.TestCase):
    def test_sentence_boundaries_cover_text_and_preserve_offsets(self):
        from experiments.ingest_text_documents import sentence_spans
        text=('Première phrase contenant assez de détails pour le visiteur. '
              'La deuxième phrase donne des informations complémentaires sur le musée. '
              'Une troisième phrase décrit les conditions de visite du site. '
              'La dernière phrase indique un lien vers les autorités concernées.')
        spans=list(sentence_spans(text,110,20))
        self.assertGreater(len(spans),1)
        self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][1],len(text))
        for i,(start,end) in enumerate(spans):
            self.assertLessEqual(end-start,110)
            self.assertTrue(text[start:end].rstrip().endswith('.'))
            if i:self.assertLessEqual(start,spans[i-1][1])
            if start:self.assertIn(text[start-2:start].strip(),('.',))

    def test_long_sentence_falls_back_without_gap(self):
        from experiments.ingest_text_documents import sentence_spans
        text='Une phrase '+('longue description sans ponctuation '*20)+'termine.'
        spans=list(sentence_spans(text,100,10))
        self.assertEqual(spans[-1][1],len(text))
        self.assertTrue(all(0<b-a<=100 for a,b in spans))
        self.assertTrue(all(spans[i][0]<=spans[i-1][1] for i in range(1,len(spans))))

    def test_sentence_mode_retains_source_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);text=('Une phrase complète avec des mots. '*14)
            (p/'doc.txt').write_text(text,encoding='utf8')
            (p/'manifest.json').write_text(json.dumps([{'id':'D','title':'Titre','file':'doc.txt','url':'https://example.org/a','publisher':'P','consulted_at':'2026-11-18','license_note':'permission','rights_confirmed':True}]),encoding='utf8')
            chunks=build_corpus(p/'manifest.json',100,10,split_mode='sentences')
            self.assertGreater(len(chunks),1)
            for c in chunks:
                self.assertEqual(c['text'],text[c['start_char']:c['end_char']])
                self.assertTrue(c['text'].rstrip().endswith('.'))
