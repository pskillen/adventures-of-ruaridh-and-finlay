#!/usr/bin/env python3
"""
Generate book illustrations via the Gemini API (Nano Banana / image-capable models).

Reads each book's images/image-context.md (YAML front matter + body) and *-image.md prompt files,
sends context + scene prompt (+ optional reference PNGs) per request, and writes PNGs next to prompts.
"""

from __future__ import annotations

import argparse
import base64
import fnmatch
import io
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from PIL import Image
from tqdm import tqdm

DEFAULT_MODEL = "gemini-3-pro-image-preview"

PROMPT_FENCE_RE = re.compile(r"```prompt\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_images_dir(book_or_images: Path) -> Path:
    p = book_or_images.resolve()
    if p.is_file():
        p = p.parent
    if p.name == "images" and p.is_dir():
        return p
    cand = p / "images"
    if cand.is_dir():
        return cand
    raise FileNotFoundError(
        f"Could not find an images/ directory from {book_or_images}. "
        "Pass the book folder (e.g. books/my-book) or books/my-book/images."
    )


def split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    raw = raw.lstrip("\ufeff")
    if not raw.startswith("---"):
        return {}, raw
    lines = raw.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return {}, raw
    end = None
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
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML front matter: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Front matter must parse to a mapping (YAML object).")
    return data, body


def extract_prompt_from_body(body: str) -> str:
    m = PROMPT_FENCE_RE.search(body)
    if m:
        return m.group(1).strip()
    bq = extract_first_blockquote(body)
    if bq:
        return bq.strip()
    raise ValueError(
        "No ```prompt ... ``` fenced block and no blockquote (lines starting with '>') found."
    )


def extract_first_blockquote(text: str) -> str | None:
    """First run of consecutive lines starting with '>', stripped of the marker."""
    lines = text.splitlines()
    collected: list[str] = []
    started = False
    for line in lines:
        if line.startswith(">"):
            collected.append(line[1:].lstrip())
            started = True
        elif started:
            break
    if not collected:
        return None
    return "\n".join(collected).strip()


def discover_prompt_files(images_dir: Path) -> list[Path]:
    return sorted(p for p in images_dir.glob("*-image.md") if p.is_file())


def output_path_for_prompt(
    prompt_file: Path,
    fm: dict[str, Any],
    images_dir: Path,
    out_dir: Path | None,
) -> Path:
    base = out_dir if out_dir is not None else images_dir
    out = fm.get("output")
    if isinstance(out, str) and out.strip():
        name = out.strip()
    else:
        stem = prompt_file.stem
        if stem.endswith("-image"):
            stem = stem[: -len("-image")]
        else:
            stem = prompt_file.stem
        name = f"{stem}.png"
    return (base / name).resolve()


def reference_paths_for_auto(
    sorted_prompts: list[Path],
    current_index: int,
    images_dir: Path,
    out_dir: Path | None,
) -> list[Path]:
    """Earlier prompt files' output PNGs if those files exist on disk."""
    base = out_dir if out_dir is not None else images_dir
    refs: list[Path] = []
    for prev in sorted_prompts[:current_index]:
        prev_fm, _ = split_front_matter(prev.read_text(encoding="utf-8"))
        p = output_path_for_prompt(prev, prev_fm, images_dir, out_dir)
        if p.exists() and p.is_file():
            refs.append(p)
    return refs


def resolve_reference_list(
    fm: dict[str, Any],
    images_dir: Path,
    out_dir: Path | None,
) -> list[Path]:
    raw = fm.get("reference_images")
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("reference_images must be a list of strings or a single string.")
    base = out_dir if out_dir is not None else images_dir
    out: list[Path] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("reference_images entries must be non-empty strings.")
        p = (images_dir / item.strip()).resolve()
        if not p.exists():
            p = (base / item.strip()).resolve()
        out.append(p)
    return out


def build_contents(
    context_body: str,
    scene_prompt: str,
    reference_paths: list[Path],
) -> list[Any]:
    parts: list[Any] = [
        "The following is shared art direction and character consistency context for this book. "
        "Apply it to every image.\n\n"
        + context_body.strip(),
        "\n\n---\n\nNow generate the scene described below as a single illustration.\n\n"
        + scene_prompt.strip(),
    ]
    for path in reference_paths:
        img = Image.open(path)
        parts.append(img)
        parts.append(
            f"(Reference image from earlier in this book: {path.name}. Match characters, style, and proportions.)"
        )
    return parts


def _coerce_genai_image_to_png(image_obj: Any) -> tuple[bytes, str]:
    """Turn google.genai.types.Image (or raw inline blob bytes) into PNG bytes."""
    ib = getattr(image_obj, "image_bytes", None)
    if ib is None:
        raise RuntimeError("Image response has no image_bytes.")
    if isinstance(ib, str):
        ib = base64.b64decode(ib)
    raw = bytes(ib)
    mime = getattr(image_obj, "mime_type", None) or "image/png"
    if mime == "image/png":
        return raw, mime
    pil = Image.open(io.BytesIO(raw))
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def extract_image_bytes(response: Any) -> tuple[bytes, str]:
    """Return first image part as PNG-friendly bytes and mime type."""
    if not response.candidates:
        raise RuntimeError("No candidates in response.")
    cand = response.candidates[0]
    content = getattr(cand, "content", None)
    if content is None:
        raise RuntimeError("Candidate has no content.")
    parts = getattr(content, "parts", None) or []
    for part in parts:
        # SDK returns google.genai.types.Image here — its save() is path-only, not PIL-compatible.
        genai_img = part.as_image()
        if genai_img is not None:
            return _coerce_genai_image_to_png(genai_img)
        inline = getattr(part, "inline_data", None)
        if inline is not None and getattr(inline, "data", None):
            mime = getattr(inline, "mime_type", None) or "image/png"
            data = inline.data
            if isinstance(data, str):
                data = base64.b64decode(data)
            raw = bytes(data)
            if mime == "image/png":
                return raw, mime
            pil = Image.open(io.BytesIO(raw))
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    raise RuntimeError("No image part found in model response (expected inline image data).")


TRANSPARENT_PROMPT_SUFFIX = (
    "\n\nRender the subject isolated on a pure white (#FFFFFF) background only, "
    "with no shadow, frame, border, or ground plane. Center the subject."
)


def post_process_transparent_white(
    png_bytes: bytes,
    *,
    white_threshold: int = 245,
    chroma_max: int = 10,
) -> bytes:
    """
    Convert near-white pixels to transparent alpha (for spot / cut-out illustrations).

    Assumes the model placed the subject on a flat white backdrop.
    """
    pil = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    out = Image.new("RGBA", pil.size)
    px_in = pil.load()
    px_out = out.load()
    w, h = pil.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px_in[x, y]
            if (
                r >= white_threshold
                and g >= white_threshold
                and b >= white_threshold
                and abs(r - g) <= chroma_max
                and abs(g - b) <= chroma_max
            ):
                px_out[x, y] = (255, 255, 255, 0)
            else:
                px_out[x, y] = (r, g, b, a)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def generate_one(
    client: Any,
    model: str,
    contents: list[Any],
    aspect_ratio: str,
    verbose: bool,
    verbose_print: Callable[[str], None],
) -> bytes:
    from google.genai import types

    config = types.GenerateContentConfig(
        response_modalities=[types.Modality.IMAGE],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    if verbose:
        verbose_print(
            f"    [verbose] model={model!r} aspect_ratio={aspect_ratio!r} "
            f"content_parts={len(contents)}",
        )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    if verbose:
        um = getattr(response, "usage_metadata", None)
        verbose_print(f"    [verbose] usage_metadata={um!r}")
    data, _mime = extract_image_bytes(response)
    return data


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Generate PNG illustrations from image-context.md and *-image.md prompts via Gemini."
    )
    ap.add_argument(
        "book_or_images",
        type=Path,
        help="Book directory (e.g. books/my-book) or its images/ folder",
    )
    ap.add_argument("--only", metavar="GLOB", help="Only process prompt files matching this glob (e.g. spread-2*)")
    ap.add_argument("--force", action="store_true", help="Regenerate even if output PNG exists")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without calling the API")
    ap.add_argument(
        "--auto-reference",
        action="store_true",
        help="Attach PNGs from earlier *-image.md files (lexical order) if they exist",
    )
    ap.add_argument("--model", metavar="ID", help="Override model from image-context.md front matter")
    ap.add_argument("--aspect", metavar="RATIO", help='Override aspect ratio (e.g. "4:3", "16:9")')
    ap.add_argument(
        "--out-dir",
        type=Path,
        help="Write PNGs here instead of the book images/ directory",
    )
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose API / payload logging")
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Per-image debug: payload sizes, reference file sizes, elapsed API time (stderr)",
    )
    ap.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable tqdm progress bar (e.g. for CI or log files)",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    env_path = repo_root() / ".env"
    try:
        load_dotenv(env_path)
    except OSError as e:
        if args.verbose or args.debug:
            print(f"warning: could not read {env_path} ({e!r}); relying on existing env vars.", file=sys.stderr)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        print(
            "error: GEMINI_API_KEY is not set. Add it to .env (see .env.example) or export it.",
            file=sys.stderr,
        )
        return 2

    try:
        images_dir = resolve_images_dir(args.book_or_images)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    ctx_path = images_dir / "image-context.md"
    if not ctx_path.is_file():
        print(f"error: Missing {ctx_path}", file=sys.stderr)
        return 2

    ctx_fm, ctx_body = split_front_matter(ctx_path.read_text(encoding="utf-8"))
    default_aspect = str(ctx_fm.get("aspect_ratio") or "4:3")
    default_model = str(ctx_fm.get("model") or DEFAULT_MODEL)

    model = args.model or default_model
    aspect_default = args.aspect or default_aspect

    out_dir = args.out_dir.resolve() if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    prompt_files = discover_prompt_files(images_dir)
    if args.only:
        prompt_files = [p for p in prompt_files if fnmatch.fnmatch(p.name, args.only)]

    if not prompt_files:
        print("No *-image.md files found (after --only filter).", file=sys.stderr)
        return 1

    show_progress = not args.no_progress and sys.stderr.isatty()

    def emit(msg: str) -> None:
        """Print without breaking tqdm when the progress bar is active."""
        tqdm.write(msg) if show_progress else print(msg)

    def stderr_line(msg: str) -> None:
        print(msg, file=sys.stderr)

    verbose_print: Callable[[str], None] = tqdm.write if show_progress else stderr_line

    if args.dry_run:
        print(f"images_dir: {images_dir}")
        print(f"model: {model}")
        print(f"aspect_ratio (default): {aspect_default}")
        print(f"context body chars: {len(ctx_body)}")
        if args.verbose:
            print("--- context body (preview 800 chars) ---")
            print(ctx_body[:800] + ("..." if len(ctx_body) > 800 else ""))

    generated = skipped = failed = 0

    client = None
    if not args.dry_run:
        from google import genai

        client = genai.Client(api_key=api_key)

    bar_kw: dict[str, Any] = {
        "desc": "Illustrations",
        "unit": "img",
        "file": sys.stderr,
        "disable": not show_progress,
    }

    with tqdm(prompt_files, **bar_kw) as pbar:
        for idx, pf in enumerate(pbar):
            fm, body = split_front_matter(pf.read_text(encoding="utf-8"))
            try:
                scene = extract_prompt_from_body(body)
            except ValueError as e:
                emit(f"✗ {pf.name}: {e}")
                failed += 1
                continue

            out_path = output_path_for_prompt(pf, fm, images_dir, out_dir)
            per_aspect = str(fm.get("aspect_ratio") or aspect_default)
            per_model = str(fm.get("model") or model)

            ref_explicit = resolve_reference_list(fm, images_dir, out_dir)
            if args.auto_reference:
                auto = reference_paths_for_auto(prompt_files, idx, images_dir, out_dir)
                # Explicit refs first, then auto (dedupe by resolved path)
                seen: set[Path] = set()
                merged: list[Path] = []
                for p in ref_explicit + auto:
                    rp = p.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        merged.append(rp)
                ref_paths = merged
            else:
                ref_paths = ref_explicit

            short_name = out_path.name[:36] + ("…" if len(out_path.name) > 36 else "")
            pbar.set_postfix_str(short_name, refresh=False)

            if args.dry_run:
                emit(f"  would write: {out_path.name} <- {pf.name}")
                emit(
                    f"    model={per_model} aspect={per_aspect} refs={len(ref_paths)} "
                    f"transparent={fm.get('transparent') is True}",
                )
                if args.verbose:
                    emit(f"    prompt chars: {len(scene)}")
                    for r in ref_paths:
                        emit(f"      ref: {r}")
                if args.debug:
                    emit(
                        f"    debug: context_chars={len(ctx_body)} prompt_chars={len(scene)} "
                        f"refs={len(ref_paths)}",
                    )
                    for r in ref_paths:
                        try:
                            sz = r.stat().st_size
                        except OSError:
                            sz = -1
                        emit(f"    debug:   ref {r.name} bytes={sz}")
                continue

            if out_path.exists() and out_path.is_file() and not args.force:
                emit(f"↷ {out_path.name} (exists)")
                skipped += 1
                continue

            if args.debug:
                emit(
                    f"    debug: → API {out_path.name} model={per_model!r} aspect={per_aspect!r} "
                    f"context_chars={len(ctx_body)} prompt_chars={len(scene)} refs={len(ref_paths)}",
                )
                for r in ref_paths:
                    try:
                        sz = r.stat().st_size
                    except OSError:
                        sz = -1
                    emit(f"    debug:   ref {r.name} bytes={sz}")

            try:
                assert client is not None
                transparent = fm.get("transparent") is True
                scene_for_api = scene
                if transparent:
                    scene_for_api = scene + TRANSPARENT_PROMPT_SUFFIX
                contents = build_contents(ctx_body, scene_for_api, ref_paths)
                t0 = time.monotonic()
                png_bytes = generate_one(
                    client,
                    per_model,
                    contents,
                    per_aspect,
                    args.verbose,
                    verbose_print,
                )
                if transparent:
                    png_bytes = post_process_transparent_white(png_bytes)
                elapsed = time.monotonic() - t0
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(png_bytes)
                extra = ""
                if args.debug:
                    extra = f" ({elapsed:.1f}s, {len(png_bytes)} bytes)"
                emit(f"✓ {out_path.name}" + extra)
                generated += 1
            except Exception as e:
                emit(f"✗ {out_path.name}: {e}")
                failed += 1

    if args.dry_run:
        emit(f"dry-run: {len(prompt_files)} prompt file(s); no API calls.")
        return 0

    emit(f"Done: generated={generated} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
