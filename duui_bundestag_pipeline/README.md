# DUUI Bundestag Video-Emotion CAS Parser

Parses UIMA CAS XMI output from the DUUI video-emotion pipeline into a
Postgres database.

## Project layout

```
.
├── main.py                # CLI entry point
├── duui_parser/           # the parser package
├── typesystems/           # UIMA typesystem XML files (see below)
└── cas/                   # input .xmi files to parse
```

## 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Get the typesystem files

`typesystems/` must contain the three type-system descriptor XML files
that the Java DUUI pipeline used to produce your CAS:

- `IdentityEmotionTypeSystem.xml`
- `MultimodalIdentityTypeSystem.xml`
- `EmotionTypeSystem.xml`

These come from the pipeline project itself, not from this repo --
usually under something like `src/main/resources/` or `desc/type/` in
the Java project, or exported by calling
`TypeSystemDescription.toXML()` in that codebase. Without the real
typesystem, cassis has no way to know what fields a type like
`identity.Person` has, and the parser can't run.

Drop the three files into `typesystems/`.

## 3. Add your CAS file

Put the `.xmi` file you want to parse into `cas/`.

## 4. Configure

```bash
cp .env.example .env
```

Edit `.env` with your real database credentials and confirm the file
paths match what you placed in steps 2-3. Everything in `.env` maps
directly to `duui_parser/config.py`, so if you'd rather not use a
`.env` file, exporting the same variables in your shell/CI works
identically.

## 5. Run

```bash
python main.py                    # uses DUUI_XMI_FILE from .env
python main.py cas/other_file.xmi # or pass a path explicitly
```

This loads and patches the typesystem, loads the CAS (lenient mode --
annotation types outside this parser's scope, e.g. linguistic
Token/POS/Dependency layers, are safely skipped), runs every parser
step in `duui_parser/parsers/PARSE_STEPS`, and commits the result in a
single transaction (rolled back automatically if any step raises).

## Processing multiple CAS files

For a batch of files, loop over `run()` rather than calling `main.py`
repeatedly -- this avoids reloading and re-patching the typesystem for
every file:

```python
from pathlib import Path
from duui_parser.pipeline import run

for xmi_path in Path("cas").glob("*.xmi"):
    run(str(xmi_path))
```

If this grows into a real batch job, it's worth having `run()` accept
an already-loaded typesystem instead of reloading it every call --
happy to add that if you get there.

## Database schema

This parser assumes the following tables already exist: `Video`,
`Model`, `Segment`, `LinguisticToken`, `GlobalPerson`, `Person`,
`FaceEmbedding`, `VoiceEmbedding`, `Presence`, `FaceDetection`,
`PersonDetection`, `BaseEmotion`, `EmotionScore`, `FusedEmotion`,
`EmotionFusionReference`. It does not create them -- run your schema
migration separately before the first import.
