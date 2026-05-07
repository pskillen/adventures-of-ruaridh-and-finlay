# Fonts for print PDFs

`scripts/build_booklet.py` looks here for optional TrueType fonts.

## Quicksand (recommended)

Place these files in this directory (download from [Google Fonts](https://fonts.google.com/specimen/Quicksand) or another licensed source):

- `Quicksand-Regular.ttf`
- `Quicksand-Bold.ttf` (optional; bold falls back to Regular if missing)

If no `.ttf` files are present, the booklet script uses **Helvetica** with a stderr warning.

Do not commit large binary font files unless your repo policy allows it; many teams keep fonts local-only and rely on the fallback in CI.
