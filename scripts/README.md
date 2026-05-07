# Gemini image generation (`generate_images.py`)

Generates PNG illustrations for each book using the Google Gemini API (image-capable models such as `gemini-3.1-flash-image-preview` / Nano Banana 2). It reads:

- `books/<slug>/images/image-context.md` — YAML front matter + shared art direction (sent with **every** request so style does not drift across spreads).
- `books/<slug>/images/*-image.md` — one prompt file per illustration; YAML front matter + a fenced ` ```prompt` block with the scene instructions.

Outputs PNGs next to the prompts (or under `--out-dir`).

## Setup

Use the project virtualenv at `venv/` (or create one):

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r scripts/requirements.txt
```

Copy [.env.example](../.env.example) to `.env` in the repo root and set:

```bash
GEMINI_API_KEY=your_key_here
```

## Usage

From the repository root:

```bash
source venv/bin/activate
python scripts/generate_images.py books/<book-slug>
```

Examples:

```bash
# Preview what would run (no API calls)
python scripts/generate_images.py books/ice-cream-on-the-moon --dry-run -v

# Only one spread
python scripts/generate_images.py books/ice-cream-on-the-moon --only 'spread-2*'

# Regenerate everything even if PNGs exist
python scripts/generate_images.py books/ice-cream-on-the-moon --force

# Attach earlier spreads as reference images for consistency (later spreads see earlier PNGs)
python scripts/generate_images.py books/ice-cream-on-the-moon --auto-reference -v
```

### Options

| Option | Meaning |
|--------|--------|
| `--only GLOB` | Only process prompt files whose name matches the glob (e.g. `spread-2*`). |
| `--force` | Regenerate even when the output PNG already exists. Default: skip existing files. |
| `--dry-run` | List targets; do not call the API. |
| `--auto-reference` | For each image, also send PNGs from *earlier* `*-image.md` files (in name order) if they exist. |
| `--model ID` | Override the model in `image-context.md` front matter. |
| `--aspect RATIO` | Override aspect ratio (e.g. `4:3`, `16:9`). |
| `--out-dir PATH` | Write PNGs here instead of the book’s `images/` folder. |
| `-v` / `--verbose` | More logging (routes via tqdm when the progress bar is on). |
| `--debug` | Per-image debug lines: context/prompt character counts, reference file sizes, API wall time, and written PNG byte size. |
| `--no-progress` | Disable the tqdm bar (non-TTY stderr disables automatically). |

### Progress bar

The script shows a **tqdm** progress bar on stderr while iterating prompt files (current output filename in the postfix). Status lines use `tqdm.write` so they do not corrupt the bar.

**Streaming:** Gemini image generation is effectively **one request → one finished image**. The API does not expose a fine-grained stream of rendering progress to plug into tqdm; the bar advances once per prompt file, and `--debug` adds wall-clock time for each blocking `generate_content` call.

Pipe-friendly: stderr may detect a non-interactive terminal and skip the bar; use `--no-progress` explicitly for logs or CI.

See [AGENTS.md](../AGENTS.md) and [.cursor/rules/image-generation.mdc](../.cursor/rules/image-generation.mdc). The script expects:

- **Context file:** `image-context.md` with optional front matter:
  - `model` (default: `gemini-3.1-flash-image-preview`)
  - `aspect_ratio` (e.g. `4:3`)
- **Per image:** `something-image.md` with optional front matter:
  - `output` — output filename (default: stem with `-image` removed + `.png`)
  - `aspect_ratio` — per-image override
  - `transparent` — if `true`, append a white-isolation instruction and post-process the PNG to alpha (for **spot** cut-outs; see the image-generation rule).
  - `layout` / `facing` — optional hints for [`build_booklet.py`](build_booklet.py) (`layout: stacked | image_only | text_only`, `facing: text_only` for a two-page spread).
  - `reference_images` — list of PNG paths relative to `images/` (optional)
- The **canonical prompt** must live in a fenced block tagged `prompt`:

````markdown
```prompt
Generate a picture-book illustration: ...
```
````

If that fence is missing, the script falls back to the first Markdown blockquote (`>` lines).

## Troubleshooting

- **`GEMINI_API_KEY is not set`** — Add the key to `.env` or export it in the shell.
- **Permission denied reading `.env`** — Ensure the file is readable; the script still runs if the key is exported in the environment.
- **No image in response / blocked** — Check API quota, model name, and safety filters; run with `-v` and inspect `usage_metadata` / errors.
- **`429 RESOURCE_EXHAUSTED` / quota errors** — Billing or free-tier limits for the chosen model; retry later, switch model in `image-context.md`, or upgrade the API plan (see Google’s Gemini rate-limit docs).
- **Wrong style on later spreads** — Use `--auto-reference` or merge key character details into `image-context.md` and each fenced `prompt` block so every request is self-contained.

## Print PDF booklet (`build_booklet.py`)

Builds a **16-page A5 saddle-stitched** booklet as **`output_booklet.pdf`** in the book folder (imposed two A5 pages per A4 landscape sheet, 15 mm safe margins, main art at **4:3**).

```bash
source venv/bin/activate
pip install -r scripts/requirements.txt   # includes reportlab
python scripts/build_booklet.py books/<book-slug>
```

- Reads `books/<slug>/BOOK.md`, splits on page-break lines (`---` or longer runs of dashes on their own line).
- Pulls the first `![...](...)` image per segment and plain text (headings / image lines stripped).
- Reads optional layout from `images/<stem>-image.md` YAML: `layout`, `facing` (see [.cursor/rules/image-generation.mdc](../.cursor/rules/image-generation.mdc)).
- Picks up transparent spot PNGs matching `images/<stem>-spot-*.png` (optional `placement` / `scale` in `images/<stem>-spot-N-image.md` front matter).
- Optional fonts: drop `Quicksand-Regular.ttf` (and optionally `Quicksand-Bold.ttf`) into [`scripts/assets/fonts/`](assets/fonts/README.md); otherwise Helvetica is used.

| Option | Meaning |
|--------|--------|
| `-o` / `--out PATH` | Output PDF (default: `<book>/output_booklet.pdf`). |
| `--font-dir PATH` | Directory with `Quicksand-Regular.ttf`. |
| `--allow-missing` | Draw grey placeholders for missing PNGs instead of exiting with an error. |
| `--font-size N` | Body text size (default `11`). |

Programmatic use: import `Page`, `Spot`, `build_booklet`, `pages_from_book_md` from `scripts/build_booklet.py` (run with repo root on `PYTHONPATH` or from the repo).

## Agent workflow

Do not add one-off image scripts in each book. Extend this tool or its options if you need new behaviour; keep prompts in `images/*.md` so runs stay reproducible.
