# Aurora

Medlemsservice-agent for badeanlegg og treningssentre. Svar til Bjørn på norsk.

- Én Claude Code-økt eier repoet. Ingen andre agenter skriver her.
- Hold koden minimal. Legg til et modellkall eller et verktøy bare når en målt sak krever det.
- Verktøyene leser bare. Ingen skriving til BRP, ingen e-post sendes, før Bjørn sier noe annet.
- Ingen persondata i filer git sporer. Fixtures er syntetiske og merket `"synthetic": true`.
- Ingen nøkler i repoet. Bjørn legger dem i `.env.agentic` selv.

Tester: `.venv/Scripts/python.exe -m pytest -q agentic/tests`
