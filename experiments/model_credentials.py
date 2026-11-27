"""Credentials for the integrated agent; never serialize them into reports."""
import getpass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def model_key(config, prompt=True):
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    name=config.get('api_key_env','AGENTLAB_API_KEY')
    key=os.getenv(name, '').strip()
    if key:
        return key
    url=urlsplit(config['base_url'])
    if url.scheme=='http' and url.hostname in ('localhost','127.0.0.1','::1'):
        return None
    if prompt:
        key=getpass.getpass('Clé du fournisseur LLM (saisie masquée) : ').strip()
    if not key:
        raise ValueError(name+' absente pour ce fournisseur distant')
    return key
