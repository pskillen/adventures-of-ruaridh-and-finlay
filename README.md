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

Images are generated separately using **Gemini (Nano Banana 2)** via the web UI — the AI can't generate images directly
in Cursor. Each book's `images/` folder contains:

- `image-context.md` — a session seed prompt (art style, character descriptions, aspect ratio) to paste at the start of
  a Gemini chat
- `spread-N-image.md` — one file per illustration, ready to copy-paste into Gemini

Once generated, images are saved as `spread-N.png` in the same folder.

### Printing

`BOOK.md` in each book folder is the print-ready manuscript. Page breaks are marked with `<!-- pagebreak -->`. Layout is
manual.

---

## Repo structure

```
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
