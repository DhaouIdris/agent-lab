import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.model_credentials import model_key
from experiments.model_config import load_model_config


ROOT=Path(__file__).resolve().parents[1]


class ShareableModelConfigTests(unittest.TestCase):
    def load(self, **updates):
        data=json.loads((ROOT/'model.example.json').read_text(encoding='utf-8'))
        data.update(updates)
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'model.json'
            file.write_text(json.dumps(data),encoding='utf-8')
            return load_model_config(file)

    def test_remote_and_local_model(self):
        self.assertEqual(self.load()['auth_header'],'bearer')
        self.assertEqual(self.load(base_url='http://localhost:11434/v1',token_parameter='max_tokens')['token_parameter'],'max_tokens')

    def test_rejects_unsafe_endpoints_and_embedded_secret(self):
        for url in ('http://public.example/v1','https://user:pass@example.org/v1',
                    'https://example.org/v1?key=secret','https://example.org/v1/chat/completions'):
            with self.subTest(url=url),self.assertRaises(ValueError):self.load(base_url=url)
        with self.assertRaises(ValueError):self.load(api_key='secret')

    def test_local_no_key_remote_requires_one(self):
        with patch.dict('os.environ',{'AGENTLAB_API_KEY':''}),patch('experiments.model_credentials.load_dotenv'):
            self.assertIsNone(model_key({'base_url':'http://127.0.0.1:8000/v1'},prompt=False))
            with self.assertRaises(ValueError):model_key({'base_url':'https://example.org/v1'},prompt=False)
        with patch.dict('os.environ',{'AGENTLAB_API_KEY':'test-key'}),patch('experiments.model_credentials.load_dotenv'):
            self.assertEqual(model_key({'base_url':'https://example.org/v1'},prompt=False),'test-key')
        with patch.dict('os.environ',{'AGENTLAB_API_KEY':'azure-key','OPENAI_API_KEY':'openai-key'}),patch('experiments.model_credentials.load_dotenv'):
            self.assertEqual(model_key({'base_url':'https://api.openai.com/v1','api_key_env':'OPENAI_API_KEY'},prompt=False),'openai-key')
        with self.assertRaises(ValueError):self.load(api_key_env='BAD-VAR')
