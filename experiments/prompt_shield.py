"""Optional Azure Prompt Shields adapter. Network errors fail closed."""
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class ShieldUnavailable(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AzurePromptShield:
    def __init__(self, endpoint, key, opener=None):
        parsed = urlsplit(endpoint)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)
                or not host.endswith('.cognitiveservices.azure.com') or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment or not key):
            raise ValueError('Invalid Content Safety endpoint or missing key')
        self.url = 'https://' + host + '/contentsafety/text:shieldPrompt?api-version=2024-09-01'
        self.key = key
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def inspect(self, question, hits, timeout=30):
        # Azure accepts at most five documents per request. Analyze every batch.
        batches = [hits[i:i+5] for i in range(0, len(hits), 5)] or [[]]
        flagged = []
        user_attack = False
        for batch in batches:
            docs = [str(h.get('title', '')) + '\n' + str(h.get('text', '')) for h in batch]
            request = urllib.request.Request(self.url, data=json.dumps({'userPrompt': question, 'documents': docs}, ensure_ascii=False).encode('utf-8'),
                headers={'Content-Type':'application/json', 'Ocp-Apim-Subscription-Key':self.key}, method='POST')
            try:
                with self.opener.open(request, timeout=timeout) as response:
                    obj = json.loads(response.read(1024 * 1024).decode('utf-8'))
                user = obj['userPromptAnalysis']['attackDetected']
                analysis = obj['documentsAnalysis']
                if type(user) is not bool or not isinstance(analysis, list) or len(analysis) != len(batch):
                    raise ValueError('Unexpected response')
                if any(not isinstance(item, dict) or type(item.get('attackDetected')) is not bool for item in analysis):
                    raise ValueError('Unexpected response')
            except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise ShieldUnavailable('Prompt Shields unavailable or invalid response') from None
            user_attack = user_attack or user
            flagged.extend(hit['id'] for hit, item in zip(batch, analysis) if item['attackDetected'])
        return {'user_attack':user_attack, 'flagged_source_ids':flagged}
