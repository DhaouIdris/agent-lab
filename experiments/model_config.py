"""Provider-neutral configuration for the integrated agent."""
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

DEFAULTS={
    'auth_header':'bearer', 'api_version':None, 'token_parameter':'max_tokens',
    'max_output_tokens':1200, 'min_interval_seconds':0, 'turn_timeout_seconds':180,
}
OPTIONAL_METADATA={'underlying_model','model_version','region','deployment_type',
                   'input_price_per_million','output_price_per_million','currency'}


def load_model_config(path):
    config=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(config,dict):
        raise ValueError('Configuration must be a JSON object')
    if set(config)-({'base_url','deployment'}|set(DEFAULTS)|OPTIONAL_METADATA):
        raise ValueError('Unknown config fields; do not put credentials in the config')
    config={**DEFAULTS,**config}
    for field in ('base_url','deployment'):
        if not isinstance(config.get(field),str) or not config[field].strip():
            raise ValueError('Missing '+field)
    url=urlsplit(config['base_url'])
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use a plain base URL without credentials/query/fragment')
    if url.scheme=='http' and url.hostname not in ('localhost','127.0.0.1','::1'):
        raise ValueError('Non-local endpoints require HTTPS')
    if url.path.rstrip('/').endswith('/chat/completions'):
        raise ValueError('Provide a base URL without /chat/completions')
    if config['auth_header'] not in ('bearer','api-key') or config['token_parameter'] not in ('max_tokens','max_completion_tokens'):
        raise ValueError('Invalid authentication or token parameter')
    if config['api_version'] is not None and (not isinstance(config['api_version'],str) or not config['api_version']):
        raise ValueError('Invalid api_version')
    if type(config['max_output_tokens']) is not int or not 100<=config['max_output_tokens']<=4096:
        raise ValueError('Output cap must be 100..4096')
    spacing=config['min_interval_seconds']
    if type(spacing) not in (int,float) or not math.isfinite(spacing) or not 0<=spacing<=60:
        raise ValueError('Request spacing must be 0..60 seconds')
    if type(config['turn_timeout_seconds']) is not int or not 30<=config['turn_timeout_seconds']<=600:
        raise ValueError('Turn timeout must be 30..600 seconds')
    return config
