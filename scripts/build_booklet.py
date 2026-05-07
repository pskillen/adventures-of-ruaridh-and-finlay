#!/usr/bin/env python3
"""
Build a print-ready 16-page A5 saddle-stitched booklet PDF from images + text.

Imposes two A5 pages per A4 landscape sheet with standard booklet pagination.
See scripts/README.md for usage.
"""

from __future__ import annotations

import argparse
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

# --- Physical layout (A4 landscape = two A5 portrait pages side by side) ---

A4_LANDSCAPE = landscape(A4)  # (width_pt, height_pt)
A5_W = 148 * mm
A5_H = 210 * mm
MARGIN = 15 * mm
PAGE_COUNT = 16
IMAGE_RATIO = 4 / 3  # main spreads only

IMAGE_LINK_RE = re.compile(r"!\[\[([^\]]*)\]\]\(([^)]+)\)|!\[([^\]]*)\]\(([^)]+)\)")


@dataclass
class Spot:
    """Transparent ancillary PNG placed on the text-bearing page."""

    image: Path
    placement: str = "auto"  # auto | top | bottom | left | right
    scale: float = 0.35  # max side as fraction of inner short side


@dataclass
class Page:
    """One A5 page in reader order (before imposition)."""

    image: Path | None = None
    text: str = ""
    spots: list[Spot] = field(default_factory=list)
    layout: str = "stacked"  # stacked | image_only | text_only


@dataclass
class FontPair:
    regular: str
    bold: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_font_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "fonts"


def split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    raw = raw.lstrip("\ufeff")
    if not raw.startswith("---"):
        return {}, raw
    lines = raw.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return {}, raw
    end: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, raw
    fm_text = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {}, raw
    if not isinstance(data, dict):
        return {}, raw
    return data, body


def register_fonts(font_dir: Path) -> FontPair:
    """Register Quicksand TTFs if present; otherwise Helvetica."""
    reg = font_dir / "Quicksand-Regular.ttf"
    bold = font_dir / "Quicksand-Bold.ttf"
    regular_name = "BookletQuicksand"
    bold_name = "BookletQuicksand-Bold"
    if reg.is_file():
        try:
            pdfmetrics.registerFont(TTFont(regular_name, str(reg)))
        except Exception as e:
            warnings.warn(f"Could not load {reg}: {e}", stacklevel=2)
            regular_name = "Helvetica"
    else:
        print(f"warning: missing {reg.name}; using Helvetica.", file=sys.stderr)
        regular_name = "Helvetica"
    if bold.is_file():
        try:
            pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
        except Exception as e:
            warnings.warn(f"Could not load {bold}: {e}", stacklevel=2)
            bold_name = regular_name
    else:
        bold_name = "Helvetica-Bold" if regular_name == "Helvetica" else regular_name
    return FontPair(regular=regular_name, bold=bold_name)


def _fit_43_box(max_w: float, max_h: float) -> tuple[float, float]:
    """Largest 4:3 rectangle inside max_w x max_h."""
    if max_w <= 0 or max_h <= 0:
        return 0.0, 0.0
    w_by_h = max_h * IMAGE_RATIO
    if w_by_h <= max_w:
        return w_by_h, max_h
    return max_w, max_w / IMAGE_RATIO


def draw_scaled_image(
    c: Canvas,
    image_path: Path,
    x: float,
    y: float,
    max_w: float,
    max_h: float,
    *,
    allow_missing: bool = False,
    label: str = "",
) -> None:
    """
    Scale a raster image to fit max_w x max_h while preserving 4:3 aspect,
    then center within the bounding box (x,y) = lower-left of the box.
    """
    tw, th = _fit_43_box(max_w, max_h)
    cx = x + (max_w - tw) / 2
    cy = y + (max_h - th) / 2
    if not image_path.is_file():
        if allow_missing:
            c.setFillGray(0.85)
            c.rect(x, y, max_w, max_h, stroke=1, fill=1)
            c.setFillColorRGB(0.6, 0, 0)
            msg = f"Missing\n{label or image_path.name}"
            c.setFont("Helvetica", 8)
            c.drawCentredString(x + max_w / 2, y + max_h / 2 - 4, msg[:80])
            return
        raise FileNotFoundError(f"Image not found: {image_path}")
    try:
        pil = PILImage.open(image_path)
        pil.load()
    except OSError as e:
        if allow_missing:
            c.setFillGray(0.85)
            c.rect(x, y, max_w, max_h, stroke=1, fill=1)
            c.setFont("Helvetica", 8)
            c.drawCentredString(x + max_w / 2, y + max_h / 2 - 4, str(e)[:60])
            return
        raise
    iw, ih = pil.size
    if iw <= 0 or ih <= 0:
        raise ValueError(f"Invalid image dimensions for {image_path}")
    reader = ImageReader(image_path)
    c.drawImage(
        reader,
        cx,
        cy,
        width=tw,
        height=th,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def draw_scaled_image_free(
    c: Canvas,
    image_path: Path,
    x: float,
    y: float,
    max_w: float,
    max_h: float,
    *,
    allow_missing: bool = False,
    label: str = "",
) -> None:
    """Fit image in max_w x max_h preserving native aspect ratio; center in box."""
    if not image_path.is_file():
        if allow_missing:
            c.setFillGray(0.9)
            c.rect(x, y, max_w, max_h, stroke=1, fill=1)
            c.setFont("Helvetica", 6)
            c.drawCentredString(x + max_w / 2, y + max_h / 2, f"Missing {label}")
            return
        raise FileNotFoundError(f"Image not found: {image_path}")
    try:
        pil = PILImage.open(image_path)
        pil.load()
        iw, ih = pil.size
    except OSError as e:
        if allow_missing:
            c.setFillGray(0.9)
            c.rect(x, y, max_w, max_h, stroke=1, fill=1)
            return
        raise
    if iw <= 0 or ih <= 0:
        raise ValueError(f"Invalid image dimensions for {image_path}")
    scale = min(max_w / iw, max_h / ih)
    tw, th = iw * scale, ih * scale
    cx = x + (max_w - tw) / 2
    cy = y + (max_h - th) / 2
    reader = ImageReader(image_path)
    c.drawImage(reader, cx, cy, width=tw, height=th, preserveAspectRatio=True, anchor="c", mask="auto")


def draw_centered_wrapped(
    c: Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_name: str,
    font_size: float,
    leading: float,
) -> tuple[float, float, float, float]:
    """
    Draw wrapped centred text in box (x,y) lower-left, size width x height.
    Returns (left, bottom, right, top) of the ink box actually used (approx).
    """
    text = (text or "").strip()
    if not text:
        return (x, y, x, y)
    lines: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        lines.extend(simpleSplit(para, font_name, font_size, width))
        lines.append("")  # paragraph gap
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return (x, y, x, y)
    n = len(lines)
    block_h = n * leading
    if block_h > height:
        # shrink leading slightly to fit
        leading = max(font_size * 1.1, height / max(n, 1))
        block_h = n * leading
    start_y = y + (height - block_h) / 2 + (n - 1) * leading
    c.setFont(font_name, font_size)
    c.setFillColorRGB(0, 0, 0)
    ink_bottom = start_y - (n - 1) * leading - font_size * 0.2
    ink_top = start_y + font_size * 0.85
    for i, line in enumerate(lines):
        yy = start_y - i * leading
        c.drawCentredString(x + width / 2, yy, line)
    return (x, ink_bottom, x + width, ink_top)


def imposition_order(n: int = 16) -> list[tuple[int, int]]:
    """Booklet sheet pairs: (left_reader_page, right_reader_page) 1-based indices."""
    pairs: list[tuple[int, int]] = []
    for k in range(n // 4):
        pairs.append((n - 2 * k, 2 * k + 1))
        pairs.append((2 * k + 2, n - 2 * k - 1))
    return pairs


def _place_spots_in_strip(
    c: Canvas,
    spots: list[Spot],
    x0: float,
    y0: float,
    sw: float,
    sh: float,
    inner_short: float,
    *,
    allow_missing: bool,
) -> None:
    """Place spots in a horizontal strip, each cell equal width."""
    if not spots or sh <= 1 or sw <= 1:
        return
    n = len(spots)
    cell_w = sw / n
    for i, spot in enumerate(spots):
        smax = inner_short * spot.scale
        sx = x0 + i * cell_w + (cell_w - smax) / 2
        sy = y0 + (sh - smax) / 2
        draw_scaled_image_free(
            c,
            spot.image,
            sx,
            sy,
            smax,
            smax,
            allow_missing=allow_missing,
            label=spot.image.name,
        )


def _place_spots_stacked(
    c: Canvas,
    spots: list[Spot],
    inner_x: float,
    inner_y: float,
    inner_w: float,
    lower_h: float,
    spot_y0: float,
    spot_h: float,
    *,
    allow_missing: bool,
) -> None:
    """Place spots in a strip above the text block within the lower panel."""
    if not spots or spot_h <= 1:
        return
    short_side = min(inner_w, lower_h)
    _place_spots_in_strip(
        c, spots, inner_x, spot_y0, inner_w, spot_h, short_side, allow_missing=allow_missing
    )


def _place_spots_text_only(
    c: Canvas,
    spots: list[Spot],
    inner_x: float,
    inner_y: float,
    inner_w: float,
    inner_h: float,
    text_bbox: tuple[float, float, float, float],
    *,
    allow_missing: bool,
) -> None:
    """Top and bottom bands around the text block."""
    if not spots:
        return
    _lx, tb_y0, _rx, tb_y1 = text_bbox
    short_side = min(inner_w, inner_h)
    top_strip_h = max(tb_y1 - inner_y - 2 * mm, 0)
    bot_strip_h = max(tb_y0 - inner_y - 2 * mm, 0)
    top_spots = [s for s in spots if s.placement == "top"]
    bot_spots = [s for s in spots if s.placement == "bottom"]
    auto_spots = [s for s in spots if s.placement not in ("top", "bottom")]
    mid = (len(auto_spots) + 1) // 2
    top_spots = top_spots + auto_spots[:mid]
    bot_spots = bot_spots + auto_spots[mid:]
    if top_spots and top_strip_h > 3 * mm:
        _place_spots_in_strip(
            c,
            top_spots,
            inner_x,
            tb_y1 + 1 * mm,
            inner_w,
            min(top_strip_h - 1 * mm, 28 * mm),
            short_side,
            allow_missing=allow_missing,
        )
    if bot_spots and bot_strip_h > 3 * mm:
        _place_spots_in_strip(
            c,
            bot_spots,
            inner_x,
            inner_y + 1 * mm,
            inner_w,
            min(bot_strip_h - 1 * mm, 28 * mm),
            short_side,
            allow_missing=allow_missing,
        )


def render_a5_page(
    c: Canvas,
    x_offset: float,
    y_offset: float,
    page: Page,
    fonts: FontPair,
    *,
    allow_missing: bool = False,
    body_font_size: float = 11,
    leading: float | None = None,
) -> None:
    """Draw one A5 page with lower-left of the A5 cell at (x_offset, y_offset)."""
    ld = leading if leading is not None else body_font_size * 1.25
    ix = x_offset + MARGIN
    iy = y_offset + MARGIN
    iw = A5_W - 2 * MARGIN
    ih = A5_H - 2 * MARGIN
    layout = (page.layout or "stacked").strip().lower()
    if layout not in ("stacked", "image_only", "text_only"):
        layout = "stacked"

    text_bbox: tuple[float, float, float, float] = (ix, iy, ix + iw, iy)

    if layout == "image_only":
        if page.image:
            draw_scaled_image(c, page.image, ix, iy, iw, ih, allow_missing=allow_missing, label=page.image.name)
        return

    if layout == "text_only":
        spots_h = min(ih * 0.28, 40 * mm) if page.spots else 0
        text_h = ih - (2 * spots_h if page.spots else 0) - (4 * mm if page.spots else 0)
        ty = iy + spots_h + 2 * mm if page.spots else iy
        text_bbox = draw_centered_wrapped(
            c, page.text, ix, ty, iw, text_h, fonts.regular, body_font_size, ld
        )
        if page.spots:
            _place_spots_text_only(c, page.spots, ix, iy, iw, ih, text_bbox, allow_missing=allow_missing)
        return

    # stacked
    img_frac = 0.58
    lower_frac = 1.0 - img_frac
    lower_h = ih * lower_frac
    img_h = ih * img_frac - 2 * mm
    img_y = iy + lower_h + 2 * mm
    if page.image:
        draw_scaled_image(c, page.image, ix, img_y, iw, img_h, allow_missing=allow_missing, label=page.image.name)

    spot_strip = min(lower_h * 0.32, 30 * mm) if page.spots else 0
    text_h = max(lower_h - spot_strip - 2 * mm, 10 * mm)
    text_y = iy
    _ = draw_centered_wrapped(
        c, page.text, ix, text_y, iw, text_h, fonts.regular, body_font_size, ld
    )
    if page.spots and spot_strip > 2 * mm:
        spot_y0 = text_y + text_h + 1 * mm
        spot_h = max(iy + lower_h - spot_y0 - 0.5 * mm, 0)
        _place_spots_stacked(
            c,
            page.spots,
            ix,
            iy,
            iw,
            lower_h,
            spot_y0,
            spot_h,
            allow_missing=allow_missing,
        )


def build_booklet(
    pages: list[Page],
    out_path: Path,
    *,
    font_dir: Path | None = None,
    allow_missing: bool = False,
    body_font_size: float = 11,
) -> None:
    """Write a saddle-stitched 16-page booklet to out_path."""
    pages = list(pages)
    if len(pages) > PAGE_COUNT:
        raise ValueError(f"Booklet expects at most {PAGE_COUNT} pages; got {len(pages)}.")
    while len(pages) < PAGE_COUNT:
        pages.append(Page())
    page_w, page_h = A4_LANDSCAPE
    pair_total_w = 2 * A5_W
    x0 = (page_w - pair_total_w) / 2
    y0 = (page_h - A5_H) / 2
    fd = font_dir if font_dir is not None else default_font_dir()
    fonts = register_fonts(fd)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(out_path), pagesize=A4_LANDSCAPE)
    order = imposition_order(PAGE_COUNT)
    for left_i, right_i in order:
        render_a5_page(
            c,
            x0,
            y0,
            pages[left_i - 1],
            fonts,
            allow_missing=allow_missing,
            body_font_size=body_font_size,
        )
        render_a5_page(
            c,
            x0 + A5_W,
            y0,
            pages[right_i - 1],
            fonts,
            allow_missing=allow_missing,
            body_font_size=body_font_size,
        )
        c.showPage()
    c.save()


# --- BOOK.md parsing ---


def split_book_segments(markdown: str) -> list[str]:
    """Split manuscript on page-break lines (--- or longer run of dashes)."""
    lines = markdown.splitlines()
    segments: list[list[str]] = []
    cur: list[str] = []
    br_re = re.compile(r"^-{3,}\s*$")
    for line in lines:
        if br_re.match(line):
            if cur:
                segments.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        segments.append(cur)
    return ["\n".join(s).strip() for s in segments if any(s.strip() for s in s)]


def extract_first_image_path(segment: str, book_dir: Path) -> Path | None:
    m = IMAGE_LINK_RE.search(segment)
    if not m:
        return None
    path_str = m.group(2) or m.group(4)
    if not path_str:
        return None
    p = (book_dir / path_str.strip()).resolve()
    return p


def strip_markdown_emphasis(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    return s


def segment_to_plain_text(segment: str) -> str:
    """Remove image lines, leading # heading line, collapse whitespace."""
    lines_out: list[str] = []
    for line in segment.splitlines():
        if IMAGE_LINK_RE.search(line):
            continue
        if re.match(r"^#+\s+", line):
            continue
        lines_out.append(line.rstrip())
    text = "\n".join(lines_out)
    text = strip_markdown_emphasis(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def stem_from_image_path(image_path: Path, book_dir: Path) -> str:
    images_root = (book_dir / "images").resolve()
    try:
        return image_path.resolve().relative_to(images_root).stem
    except ValueError:
        return image_path.stem


def load_image_prompt_meta(images_dir: Path, stem: str) -> dict[str, Any]:
    md = images_dir / f"{stem}-image.md"
    if not md.is_file():
        return {}
    fm, _ = split_front_matter(md.read_text(encoding="utf-8"))
    return fm if isinstance(fm, dict) else {}


def load_spot_meta(images_dir: Path, spot_png: Path) -> dict[str, Any]:
    stem = spot_png.stem  # e.g. spread-1-spot-2
    md = images_dir / f"{stem}-image.md"
    if not md.is_file():
        return {}
    fm, _ = split_front_matter(md.read_text(encoding="utf-8"))
    return fm if isinstance(fm, dict) else {}


def discover_spots(images_dir: Path, main_stem: str) -> list[Spot]:
    out: list[Spot] = []
    for png in sorted(images_dir.glob(f"{main_stem}-spot-*.png")):
        if not png.is_file():
            continue
        fm = load_spot_meta(images_dir, png)
        placement = str(fm.get("placement") or "auto")
        scale = float(fm.get("scale") or 0.35)
        out.append(Spot(image=png.resolve(), placement=placement, scale=scale))
    return out


def pages_from_book_md(book_dir: Path) -> list[Page]:
    book_md = book_dir / "BOOK.md"
    if not book_md.is_file():
        raise FileNotFoundError(f"Missing {book_md}")
    images_dir = book_dir / "images"
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Missing {images_dir}")
    raw = book_md.read_text(encoding="utf-8")
    segments = split_book_segments(raw)
    if not segments:
        raise ValueError(f"No segments found in {book_md} (add page breaks like ---).")
    pages: list[Page] = []
    first = True
    for seg in segments:
        img_path = extract_first_image_path(seg, book_dir)
        text = segment_to_plain_text(seg)
        if img_path is None:
            pages.append(Page(image=None, text=text, spots=[], layout="text_only"))
            first = False
            continue
        stem = stem_from_image_path(img_path, book_dir)
        fm = load_image_prompt_meta(images_dir, stem)
        layout = str(fm.get("layout") or "stacked").strip().lower()
        facing = str(fm.get("facing") or "").strip().lower()
        spots = discover_spots(images_dir, stem)

        if first and img_path.name.lower() == "cover.png":
            pages.append(
                Page(
                    image=img_path,
                    text="",
                    spots=[],
                    layout="image_only",
                )
            )
            first = False
            continue

        first = False

        if facing in ("text_only", "image_only"):
            # Plan: segment becomes image_only + facing text_only with text+spots
            if facing == "text_only":
                pages.append(
                    Page(
                        image=img_path,
                        text="",
                        spots=[],
                        layout="image_only",
                    )
                )
                pages.append(
                    Page(
                        image=None,
                        text=text,
                        spots=spots,
                        layout="text_only",
                    )
                )
            else:
                # facing image_only: text page first then image (unusual)
                pages.append(
                    Page(
                        image=None,
                        text=text,
                        spots=spots,
                        layout="text_only",
                    )
                )
                pages.append(
                    Page(
                        image=img_path,
                        text="",
                        spots=[],
                        layout="image_only",
                    )
                )
        else:
            if layout not in ("stacked", "image_only", "text_only"):
                layout = "stacked"
            pages.append(
                Page(
                    image=img_path,
                    text=text,
                    spots=spots,
                    layout=layout,
                )
            )

    if len(pages) > PAGE_COUNT:
        raise ValueError(
            f"Parsed {len(pages)} pages from {book_dir / 'BOOK.md'}; "
            f"booklet allows at most {PAGE_COUNT}. "
            "Reduce spreads or disable `facing` on some segments."
        )
    return pages


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a 16-page saddle-stitched A5 booklet PDF from BOOK.md.")
    ap.add_argument("book_dir", type=Path, help="Book directory containing BOOK.md and images/")
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=None,
        help="Output PDF path (default: <book_dir>/output_booklet.pdf)",
    )
    ap.add_argument(
        "--font-dir",
        type=Path,
        default=None,
        help="Directory containing Quicksand-Regular.ttf (default: scripts/assets/fonts)",
    )
    ap.add_argument(
        "--allow-missing",
        action="store_true",
        help="Draw placeholders for missing images instead of failing.",
    )
    ap.add_argument("--font-size", type=float, default=11.0, help="Body text size (default: 11)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    book_dir = args.book_dir.resolve()
    out = args.out or (book_dir / "output_booklet.pdf")
    try:
        pages = pages_from_book_md(book_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    try:
        build_booklet(
            pages,
            out.resolve(),
            font_dir=args.font_dir.resolve() if args.font_dir else None,
            allow_missing=args.allow_missing,
            body_font_size=args.font_size,
        )
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
