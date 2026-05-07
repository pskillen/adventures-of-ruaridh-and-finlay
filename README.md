# Adventures of Ruaridh and Finlay

A personal family project. We use an AI assistant (Cursor) to write and illustrate original children's books starring
our sons — Ruaridh and Finlay — along with their dog Max and the rest of the family.

The books are printed at home as a hobby.

---

## How it works

### Writing

Stories are written by an AI agent (Claude in Cursor) using context files in `authoring/` to stay consistent across
sessions:

- `authoring/characters/` — personality, appearance, and voice for each character
- `authoring/audience/` — age-appropriate guidelines for Ruaridh and Finlay
- `authoring/themes/` — story structure patterns (e.g. adventure journey)
- `authoring/settings/` — physical locations and world-building notes

The AI reads whichever files are relevant to the prompt before writing anything. `AGENTS.md` at the root tells it how to
do this.

### Images

Images are produced with **Gemini** (image-capable models such as Nano Banana 2). The AI in Cursor prepares prompts; **batch
generation** uses [`scripts/generate_images.py`](scripts/generate_images.py) (see [`scripts/README.md`](scripts/README.md)).

Use the project virtualenv at `venv/`:

```bash
source venv/bin/activate
pip install -r scripts/requirements.txt
# Copy .env.example to .env and set GEMINI_API_KEY
python scripts/generate_images.py books/<your-book-slug>
```

Each book's `images/` folder contains:

- `image-context.md` — shared art direction with YAML front matter (`model`, `aspect_ratio`) plus the session seed text
- `spread-N-image.md` (or `page-N-image.md`) — one file per illustration with optional front matter and a fenced code block tagged `prompt`

Generated PNGs are written next to the prompts (e.g. `spread-N.png`). You can still paste prompts into the Gemini web UI if
you prefer.

### Printing

`BOOK.md` in each book folder is the print-ready manuscript. Page breaks are marked with `-----------`. Layout is
manual.

---

## Repo structure

```text
authoring/          context files for the AI agent
  characters/       one file per character
  audience/         one file per reader (Ruaridh, Finlay)
  themes/           story structure templates
  settings/         locations and world-building

books/              one folder per completed or in-progress book
  <book-slug>/
    BOOK.md         the manuscript
    README.md       title, themes, characters, notes
    images/
      image-context.md    Gemini session seed
      spread-N-image.md   per-image prompts
      spread-N.png        final generated images

AGENTS.md           instructions for the AI agent
.cursor/rules/      Cursor-specific AI rules (e.g. image generation workflow)
```

## Books so far

| Title                                                 | Audience                   | Theme                              |
|-------------------------------------------------------|----------------------------|------------------------------------|
| [The Great Garden SOS](books/the-great-garden-sos/)   | Ruaridh + Finlay (daytime) | Dad's radio, hedgehog rescue       |
| [Ice Cream on the Moon](books/ice-cream-on-the-moon/) | Ruaridh + Finlay (daytime) | Space adventure, fixing the rocket |
