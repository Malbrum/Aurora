# agentic – medlemsservice som én agent med verktøy

Ny, minimal kodebase (gren `Agentic`). Bygget etter Anthropics *Building effective agents*:
én modell som bruker verktøy i en løkke, verktøy med presise svar, mennesket før hver endring,
og så lite kode som mulig. Den gamle appen i `app/` står urørt til deler av den er strømlinjeformet
og eventuelt flyttet hit.

## Hva den gjør

1. Leser nye tråder til medlemsservice-postkassen (Gmail, bare lesing).
2. Starter én agent per tråd. Agenten får hele tråden og fire verktøy:
   `lookup_member`, `get_subscriptions`, `get_invoices`, `propose`.
3. Agenten slår opp det den trenger i BRP (bare lesing) og avslutter med ett forslag:
   sakstype, hva som bør gjøres i Back Office, utkast til kundesvar, og om et menneske må inn.
4. Forslaget lagres i SQLite med alle verktøykall og tokenforbruk. Ingen e-post sendes og ingenting
   skrives til BRP. Bjørn leser forslagene (`show`) og handler selv.

«Løst» måles senere som: riktig registrering i BRP og et kundesvar som stemmer med BRP.

## Filer

| Fil | Linjer | Ansvar |
|---|---|---|
| `agent.py` | ~70 | løkken: tråd inn, forslag ut, forbruk registrert |
| `tools.py` | ~90 | de fire verktøyene og sensitivitetssperren |
| `prompt.md` | | systemprompten (lesbar for alle) |
| `brp.py` | ~90 | BRP API3, bare GET |
| `gmail.py` | ~80 | Gmail, bare GET |
| `store.py` | ~60 | SQLite: tråder, forslag |
| `config.py` | ~30 | innstillinger fra `.env.agentic` |
| `main.py` | ~60 | CLI: `poll`, `show`, `replay`, `outcome` |
| `eval.py` | ~40 | kjører alle fixtures, skriver TREFF/BOM per sak og treffprosent |

## Kjøre

```bash
.venv/Scripts/python.exe -m agentic.main replay agentic/fixtures/faktura-etter-oppsigelse.json
.venv/Scripts/python.exe -m agentic.main poll
.venv/Scripts/python.exe -m agentic.main show
.venv/Scripts/python.exe -m agentic.eval
```

`replay` kjører agenten på en syntetisk tråd med syntetiske BRP-data, uten Gmail. Det er også
evalueringsformen: en mappe med fixtures og forventet sakstype gir treffprosent.

Innstillinger ligger i `.env.agentic` (se `.env.agentic.example`). `ANTHROPIC_API_KEY` må finnes
før `poll`/`replay` kaller modellen. Uten nøkkel kjører testene med en innspilt agent.

## Grenser som ligger i koden

- Verktøyene kan bare lese. Det finnes ingen skrivefunksjon å kalle.
- Tekst med helse-, bank- eller fødselsnummeropplysninger sendes ikke til modellen; tråden merkes for manuell behandling.
- Agenten stopper etter `MAX_TURNS` verktøyrunder.
- Alt forbruk (`usage`) lagres per tråd, som grunnlag for pris per løst sak.
