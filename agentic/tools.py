"""Fire verktøy, alle lesende bortsett fra `propose`, som bare lagrer agentens forslag i minnet.

Verktøyene bindes til én tråd og én BRP-klient via `Toolbox`. Hvert kall logges med argumenter og
svarstørrelse, så forslaget kan revideres i ettertid.
"""
import json
import re

from anthropic import beta_tool

KINDS = ('invoice_question', 'termination', 'freeze', 'withdrawal', 'refund', 'info_request', 'complaint', 'other')

# Helse, bank og fødselsnummer sendes aldri til modellen (dataminimering). Heuristisk og konservativ.
SENSITIVE = re.compile(
    r"\b(?:syk\w*|lege\w*|diagnos\w*|operasjon\w*|gravid\w*|kreft|depresjon|angst|psyk\w*|behandling\w*|"
    r"medisin\w*|uføre\w*|iban|kontonummer|bankkonto)\b|(?<!\d)\d{4}[ .]?\d{2}[ .]?\d{5}(?!\d)|(?<!\d)\d{6}\s?\d{5}(?!\d)",
    re.I)


def is_sensitive(text):
    return bool(SENSITIVE.search(text or ''))


class Toolbox:
    def __init__(self, brp):
        self.brp = brp
        self.calls = []
        self.proposal = None

    def _log(self, name, args, result):
        self.calls.append({'tool': name, 'args': args, 'chars': len(result)})
        return result

    def tools(self):
        box = self

        @beta_tool
        def lookup_member(email: str) -> str:
            """Finn medlemmer i BRP med nøyaktig denne e-postadressen.

            Args:
                email: Avsenderens e-postadresse slik den står i tråden.
            """
            return box._log('lookup_member', {'email': email}, json.dumps(box.brp.find_member(email), ensure_ascii=False))

        @beta_tool
        def get_subscriptions(customer_id: int) -> str:
            """Hent medlemmets avtaler fra BRP, også avsluttede. Felt: start, boundUntil (bindingstid),
            debitedUntil (betalt til og med), expirationDay (sluttdato ved oppsigelse), statuses, product, users, payer.

            Args:
                customer_id: BRP-kundens id fra lookup_member.
            """
            return box._log('get_subscriptions', {'customer_id': customer_id},
                            json.dumps(box.brp.subscriptions(customer_id), ensure_ascii=False, default=str))

        @beta_tool
        def get_invoices(customer_id: int) -> str:
            """Hent medlemmets fakturaer fra BRP. Felt: number, state, totalAmount (øre), rest (ubetalt, øre),
            dueDate, isCredited, rows/period når BRP oppgir perioden.

            Args:
                customer_id: BRP-kundens id fra lookup_member.
            """
            return box._log('get_invoices', {'customer_id': customer_id},
                            json.dumps(box.brp.invoices(customer_id), ensure_ascii=False, default=str))

        @beta_tool
        def propose(kind: str, summary: str, backoffice_action: str, reply_draft: str, needs_human: bool,
                    confidence: float) -> str:
            """Lever forslaget. Kalles nøyaktig én gang, til slutt. Ingenting utføres; et menneske leser forslaget.

            Args:
                kind: En av invoice_question, termination, freeze, withdrawal, refund, info_request, complaint, other.
                summary: Én til to setninger om hva medlemmet trenger og hva du fant i BRP. Ingen personnavn.
                backoffice_action: Hva som bør gjøres i Back Office, presist med avtale-/fakturanummer og datoer, eller "ingen".
                reply_draft: Utkast til svar til medlemmet, klart til å sendes etter kontroll.
                needs_human: true hvis et menneske må vurdere før svar sendes.
                confidence: Samlet sikkerhet i forslaget, 0 til 1.
            """
            if kind not in KINDS:
                return f'Ugyldig kind. Bruk en av: {", ".join(KINDS)}'
            box.proposal = {'kind': kind, 'summary': summary, 'backoffice_action': backoffice_action,
                            'reply_draft': reply_draft, 'needs_human': bool(needs_human),
                            'confidence': max(0.0, min(1.0, float(confidence)))}
            return box._log('propose', {'kind': kind}, 'Forslag lagret.')

        return [lookup_member, get_subscriptions, get_invoices, propose]
