"""Gmail, bare lesing. OAuth-refresh for den tekniske kontoen; henter tråder til kanaladressen."""
import base64
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from html.parser import HTMLParser
from time import time

import httpx

TOKEN_URL = 'https://oauth2.googleapis.com/token'


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        self.hidden += tag in ('script', 'style')
        if tag in ('br', 'p', 'div', 'li', 'tr'):
            self.out.append('\n')

    def handle_endtag(self, tag):
        self.hidden -= tag in ('script', 'style')

    def handle_data(self, data):
        if not self.hidden:
            self.out.append(data)


def body_text(payload):
    parts = []

    def walk(part):
        if part.get('filename'):
            return
        data = part.get('body', {}).get('data')
        if part.get('mimeType') in ('text/plain', 'text/html') and data:
            parts.append((part['mimeType'], base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', 'replace')))
        for child in part.get('parts', []):
            walk(child)

    walk(payload)
    plain = [v for m, v in parts if m == 'text/plain']
    if plain:
        return '\n'.join(plain).strip()
    parser = _Text()
    parser.feed('\n'.join(v for _, v in parts))
    return re.sub(r'\n{3,}', '\n\n', ''.join(parser.out)).strip()


class Gmail:
    def __init__(self, account, channel, client_id, client_secret, refresh_token, *, transport=None, timeout=20):
        self.account, self.channel = account, channel
        self._oauth = {'grant_type': 'refresh_token', 'client_id': client_id, 'client_secret': client_secret,
                       'refresh_token': refresh_token}
        self._client = httpx.Client(base_url=f'https://gmail.googleapis.com/gmail/v1/users/{account}/',
                                    transport=transport, timeout=timeout, trust_env=False)
        self._token, self._until = None, 0.0

    def close(self):
        self._client.close()

    def _headers(self):
        if self._token is None or time() >= self._until:
            response = httpx.post(TOKEN_URL, data=self._oauth, timeout=20)
            response.raise_for_status()
            data = response.json()
            self._token, self._until = data['access_token'], time() + data['expires_in'] - 60
        return {'Authorization': 'Bearer ' + self._token}

    def _get(self, path, **params):
        response = self._client.get(path, headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()

    def thread_ids(self, days):
        """Tråder til kanaladressen de siste dagene, eldste først."""
        ids, token = [], None
        while True:
            data = self._get('threads', q=f'to:{self.channel} newer_than:{days}d', maxResults=100,
                             **({'pageToken': token} if token else {}))
            ids += [t['id'] for t in data.get('threads', [])]
            token = data.get('nextPageToken')
            if not token:
                return list(reversed(ids))

    def thread(self, thread_id):
        data = self._get(f'threads/{thread_id}', format='full')
        return [parse_message(m) for m in data.get('messages', [])]


def parse_message(data):
    raw = '\r\n'.join(h['name'] + ': ' + h['value'] for h in data['payload'].get('headers', []))
    headers = BytesParser(policy=policy.default).parsebytes((raw + '\r\n\r\n').encode('utf-8'))
    sender = [a for _, a in getaddresses(headers.get_all('From', []))]
    return {'id': data['id'], 'from': sender[0].lower() if sender else '',
            'to': [a.lower() for _, a in getaddresses(headers.get_all('To', []) + headers.get_all('Cc', []))],
            'subject': str(headers.get('Subject', '')),
            'date': datetime.fromtimestamp(int(data['internalDate']) / 1000, timezone.utc).isoformat(),
            'body': body_text(data['payload'])}
