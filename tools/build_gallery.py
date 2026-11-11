#!/usr/bin/env python3
"""
Gallery builder for rinalomako.com

Turns full-size photographs into web-ready derivatives and regenerates the
gallery pages. This is the only thing that writes into galleries/ — never edit
the generated HTML or the images by hand, they will be overwritten.

Commands
--------
  ingest    Process any photos sitting in incoming/<gallery>/ , add them to that
            gallery, and delete the originals from incoming/. This is what the
            GitHub Action runs when someone uploads through the website.

  rebuild   Regenerate every gallery page from its manifest. Use after editing
            a manifest by hand (reordering photos, changing captions, deleting).

  import-legacy --mapping FILE
            One-off: build the initial galleries from the pre-2026 site layout.

Every command is safe to re-run; existing derivatives are skipped unless
--force is given.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

# --- configuration -----------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent

# Widths written for every photo. The first three feed the responsive grid via
# srcset; the largest is loaded only when a visitor opens the full-quality view.
GRID_WIDTHS = (400, 800, 1600)
FULL_WIDTH = 2560
QUALITY = 82

# One set. The website shows a single gallery, so asking which category a
# photograph belongs to was a choice with no consequence -- the three former
# sets appeared nowhere a visitor could see.
GALLERY = "photos"

# Files that are never photographs, whatever else turns up in an upload folder.
IGNORE_NAMES = {"readme.txt", ".gitkeep", ".ds_store", "thumbs.db", "unreadable.txt"}


# --- image processing --------------------------------------------------------

def is_photograph(path: Path) -> bool:
    """Decide by looking inside the file, not at its name.

    A photograph uploaded as "14.1" is still a photograph. Trusting the
    extension meant such a file was skipped in silence: it stayed in the upload
    folder, the run went green, and the photographer was never told her picture
    had not been published.
    """
    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:                                       # noqa: BLE001
        return False


def load_upright(path: Path) -> Image.Image:
    """Open an image with EXIF rotation already applied.

    Phone and mirrorless cameras record orientation as metadata rather than
    rotating the pixels. We strip metadata on export, so the rotation has to be
    baked in first or portrait shots come out sideways.
    """
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def derivative_name(stem: str, width: int) -> str:
    return f"{stem}-{width}.webp"


def write_derivatives(src: Path, out_dir: Path, stem: str, force: bool = False) -> dict:
    """Write every size tier for one photo. Returns its manifest entry."""
    im = load_upright(src)
    full_w, full_h = im.size

    # Grid tiers, but never upscale past the original. The full-quality tier is
    # capped at FULL_WIDTH — a 9000px original is downsized to 2560, not shipped
    # whole. For a photo narrower than FULL_WIDTH the cap becomes its own width,
    # so the full-quality view always has something to open.
    widths = sorted(
        {w for w in GRID_WIDTHS if w < full_w} | {min(FULL_WIDTH, full_w)}
    )

    written = []
    for w in widths:
        target = out_dir / derivative_name(stem, w)
        if target.exists() and not force:
            written.append(w)
            continue
        resized = im.copy()
        resized.thumbnail((w, w * 100), Image.LANCZOS)
        # No exif= argument means metadata is dropped, including GPS coordinates.
        resized.save(target, "WEBP", quality=QUALITY, method=6)
        written.append(w)

    return {
        "id": stem,
        "width": full_w,
        "height": full_h,
        "widths": sorted(written),
        "alt": "",
        "caption": "",
    }


# --- manifests ---------------------------------------------------------------

def manifest_path(gallery: str = GALLERY) -> Path:
    return REPO / "galleries" / gallery / "manifest.json"


def read_manifest(gallery: str = GALLERY) -> list[dict]:
    p = manifest_path(gallery)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def write_manifest(entries: list[dict], gallery: str = GALLERY) -> None:
    p = manifest_path(gallery)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=2) + "\n")


def next_id(entries: list[dict]) -> int:
    used = [int(e["id"]) for e in entries if e["id"].isdigit()]
    return max(used, default=0) + 1


# --- page generation ---------------------------------------------------------

ORDER_FILE = REPO / "order.txt"
CLOUD_COLUMNS = 2
ENTRY_RE = __import__("re").compile(r"^(\d+)$")


def read_order() -> tuple[list[str], set[str]]:
    """Return (wanted order, explicitly hidden).

    A line like `portraits/003` places that photograph. The same line commented
    out means "keep it on the site but off the page" -- which has to be told
    apart from an ordinary comment, and has to beat the rule below that shows
    anything the file forgot to mention. Without that distinction, commenting a
    photograph out silently did nothing.
    """
    wanted: list[str] = []
    hidden: set[str] = set()
    if not ORDER_FILE.exists():
        return wanted, hidden

    for raw in ORDER_FILE.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            maybe = line.lstrip("#").strip()
            if ENTRY_RE.match(maybe):
                hidden.add(maybe)
            continue
        if ENTRY_RE.match(line):
            wanted.append(line)
        else:
            print(f"  order.txt: ignoring unrecognised line {line!r}", file=sys.stderr)
    return wanted, hidden


def ordered_photos() -> list[dict]:
    """Every photograph on the site, in the order order.txt asks for."""
    by_id = {e["id"]: e for e in read_manifest()}
    wanted, hidden = read_order()

    out, seen = [], set()
    for k in wanted:
        if k in hidden or k in seen:
            continue
        if k in by_id:
            out.append(by_id[k]); seen.add(k)
        else:
            print(f"  order.txt: no such photograph {k!r}", file=sys.stderr)

    # A photograph the file never mentions is still shown, at the end, so a new
    # upload is never invisible. One deliberately hidden is not.
    for k, e in by_id.items():
        if k not in seen and k not in hidden:
            out.append(e)
    return out


def cloud_figure(e: dict) -> str:
    base = f"/galleries/{GALLERY}/images"
    stem = e["id"]
    grid = [w for w in e["widths"] if w <= 1600] or [max(e["widths"])]
    srcset = ", ".join(f"{base}/{derivative_name(stem, w)} {w}w" for w in grid)
    alt = e.get("alt") or ""
    return f"""        <figure>
          <img src="{base}/{derivative_name(stem, grid[-1])}"
               srcset="{srcset}"
               sizes="(min-width: 620px) 40vw, 44vw"
               width="{e['width']}" height="{e['height']}"
               loading="lazy" decoding="async"
               alt="{alt}" />
        </figure>"""


def render_cloud() -> str:
    """The gallery page, with the photographs written into the HTML.

    The columns are balanced here rather than in the browser: each photograph
    goes into whichever column is currently shortest, which keeps the order
    readable while packing tightly. Doing it at build time means the page
    carries real <img> tags, so it works without JavaScript and search engines
    can see the photographs.
    """
    photos = ordered_photos()
    columns: list[list[str]] = [[] for _ in range(CLOUD_COLUMNS)]
    heights = [0.0] * CLOUD_COLUMNS

    for e in photos:
        i = heights.index(min(heights))
        heights[i] += e["height"] / e["width"]      # relative height in one column
        columns[i].append(cloud_figure(e))

    cols = "\n".join(
        '      <div class="cloud-col">\n' + "\n".join(c) + "\n      </div>"
        for c in columns
    )

    return f"""<!doctype html>
<!-- GENERATED by tools/build_gallery.py from order.txt - do not edit by hand. -->
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Gallery &mdash; Ri Lomako</title>
  <meta name="description" content="Photographs by Ri Lomako." />
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="/assets/css/site-v2.css" />
</head>
<body>
  <header class="bar">
    <a class="brand" href="/">Ri Lomako</a>
    <nav>
      <a href="/gallery/" aria-current="page">gallery</a>
      <a href="/contact/">contact</a>
    </nav>
  </header>

  <main class="cloud" id="cloud">
{cols}
  </main>

  <footer class="foot">
    <span class="muted small">&copy; Ri Lomako <span data-year></span></span>
  </footer>

  <script>
    document.querySelectorAll("[data-year]").forEach(function (el) {{
      el.textContent = String(new Date().getFullYear());
    }});
  </script>
</body>
</html>
"""


def write_cloud_page() -> None:
    out = REPO / "gallery" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_cloud())


# --- commands ----------------------------------------------------------------

def cmd_ingest(args) -> int:
    """Process whatever is waiting in incoming/."""
    src_dir = REPO / "incoming"
    total = 0
    rejected: list[str] = []

    candidates = sorted(
        f for f in src_dir.iterdir()
        if f.is_file()
        and f.name.lower() not in IGNORE_NAMES
        and not f.name.startswith(".")
    ) if src_dir.is_dir() else []

    photos = [f for f in candidates if is_photograph(f)]

    # Anything left over is something this tool cannot read. It stays where it
    # is and gets named in the report, rather than being passed over in silence.
    rejected = [f"incoming/{f.name}" for f in candidates if f not in photos]

    if photos:
        entries = read_manifest()
        out_dir = REPO / "galleries" / GALLERY / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        n = next_id(entries)

        for photo in photos:
            stem = f"{n:03d}"
            try:
                entry = write_derivatives(photo, out_dir, stem, force=args.force)
            except Exception as exc:                        # noqa: BLE001
                print(f"  SKIPPED {photo.name}: {exc}", file=sys.stderr)
                rejected.append(f"incoming/{photo.name}")
                continue
            entry["alt"] = ""
            entries.append(entry)
            print(f"  {stem}  <- {photo.name}  ({entry['width']}x{entry['height']})")
            if not args.keep:
                photo.unlink()
            n += 1
            total += 1

        write_manifest(entries)

    write_cloud_page()

    report = REPO / "incoming" / "UNREADABLE.txt"
    if rejected:
        report.write_text(
            "These uploads could not be read as photographs, so they are NOT on\n"
            "the website. They are still in the incoming folder.\n\n"
            + "".join(f"  {r}\n" for r in rejected)
            + "\nUsually the file is damaged, or is not an image at all (a video,\n"
              "a PDF, a .zip). Re-export it from Photos or Lightroom and upload it\n"
              "again, then delete this file.\n"
        )
        print(f"\n!! {len(rejected)} upload(s) could not be read:", file=sys.stderr)
        for r in rejected:
            print(f"   {r}", file=sys.stderr)
    elif report.exists():
        report.unlink()

    print(f"ingested {total} photo(s)")
    # Exit 0 even when something was rejected, so the photographs that *did*
    # work still get committed. The workflow checks for the report afterwards.
    return 0


def cmd_rebuild(args) -> int:
    entries = read_manifest()

    # Drop derivatives no longer referenced by the manifest: deleting a
    # photograph's entry takes its image files with it.
    wanted = {derivative_name(e["id"], w) for e in entries for w in e["widths"]}
    images = REPO / "galleries" / GALLERY / "images"
    removed = 0
    if images.is_dir():
        for f in images.iterdir():
            if f.is_file() and f.suffix == ".webp" and f.name not in wanted:
                f.unlink(); removed += 1

    write_cloud_page()
    note = f", pruned {removed} orphaned file(s)" if removed else ""
    print(f"  rebuilt gallery/index.html ({len(ordered_photos())} photographs{note})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="process incoming/<gallery>/ uploads")
    p.add_argument("--force", action="store_true", help="re-encode existing derivatives")
    p.add_argument("--keep", action="store_true", help="do not delete originals from incoming/")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("rebuild", help="regenerate gallery pages from manifests")
    p.set_defaults(func=cmd_rebuild)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
