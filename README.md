# Aurora – medlemsservice som én agent med verktøy

Én modell med fire lesende verktøy mot BRP, forslag til et menneske, ingen skriving og ingen utsending.
Bygget etter Anthropics *Building effective agents*: minst mulig kode, verktøy med presise svar, menneske før hver endring.
Koden og designet står i [agentic/README.md](agentic/README.md).

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest -q agentic/tests
.venv/Scripts/python.exe -m agentic.main replay agentic/fixtures/faktura-etter-oppsigelse.json
```

Innstillinger i `.env.agentic` (se `.env.agentic.example`). Bjørn legger inn nøkler selv.
