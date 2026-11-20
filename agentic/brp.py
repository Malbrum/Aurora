"""BRP API3, bare lesing. Integratortoken for kundesøk, kundetoken for kundens egne data."""
from time import monotonic

import httpx

SUBSCRIPTION_KEYS = ('id', 'start', 'boundUntil', 'debitedUntil', 'expirationDay', 'statuses', 'actions',
                     'product', 'users', 'payer', 'price', 'renewalActive', 'freezes', 'binding')
INVOICE_KEYS = ('id', 'number', 'state', 'totalAmount', 'rest', 'dueDate', 'isCredited', 'rows', 'created',
                'period', 'paymentMethod')


class BRP:
    def __init__(self, base_url, username, password, *, transport=None, timeout=20):
        self._client = httpx.Client(base_url=base_url.rstrip('/') + '/api/ver3/', transport=transport,
                                    timeout=timeout, trust_env=False)
        self._login = {'username': username, 'password': password}
        self._token, self._until = None, 0.0
        self._customer_tokens = {}

    def close(self):
        self._client.close()

    def _get(self, path, token, **params):
        response = self._client.get(path, headers={'Authorization': 'Bearer ' + token}, params=params)
        response.raise_for_status()
        return response.json()

    def _integrator(self):
        if self._token is None or monotonic() >= self._until:
            data = self._client.post('auth/login', json=self._login)
            data.raise_for_status()
            data = data.json()
            self._token, self._until = data['access_token'], monotonic() + data['expires_in'] / 1000 - 30
        return self._token

    def _customer(self, customer_id):
        token, until = self._customer_tokens.get(customer_id, (None, 0.0))
        if token is None or monotonic() >= until:
            response = self._client.post('auth/token', json={'customer': customer_id},
                                         headers={'Authorization': 'Bearer ' + self._integrator()})
            response.raise_for_status()
            data = response.json()
            token, until = data['accessToken'], monotonic() + data['expiresIn'] / 1000 - 30
            self._customer_tokens[customer_id] = (token, until)
        return token

    def find_member(self, email):
        """Kunder med nøyaktig denne e-postadressen. Tomt svar betyr ukjent avsender."""
        rows = self._get('customers', self._integrator(), email=email)
        return [{'id': r['id'], 'customerNumber': r.get('customerNumber'), 'firstName': r.get('firstName'),
                 'lastName': r.get('lastName'), 'email': r.get('email'),
                 'familyMembers': [{'id': m.get('id'), 'firstName': m.get('firstName'), 'lastName': m.get('lastName')}
                                   for m in (r.get('familyMembers') or [])]}
                for r in rows if (r.get('email') or '').casefold() == email.casefold()]

    def subscriptions(self, customer_id):
        rows = self._get(f'customers/{customer_id}/subscriptions', self._customer(customer_id), includeInactive='true')
        return [{k: r[k] for k in SUBSCRIPTION_KEYS if k in r} for r in rows]

    def invoices(self, customer_id):
        rows = self._get(f'customers/{customer_id}/invoices', self._customer(customer_id))
        return [{k: r[k] for k in INVOICE_KEYS if k in r} for r in rows]


class FixtureBRP:
    """Syntetiske data fra en JSON-fil, samme grensesnitt. Brukes av replay og tester."""

    def __init__(self, data):
        self.data = data

    def close(self):
        pass

    def find_member(self, email):
        return [m for m in self.data.get('members', []) if m.get('email', '').casefold() == email.casefold()]

    def subscriptions(self, customer_id):
        return [s for s in self.data.get('subscriptions', []) if customer_id in s.get('customers', [customer_id])]

    def invoices(self, customer_id):
        return [i for i in self.data.get('invoices', []) if i.get('customer', customer_id) == customer_id]
