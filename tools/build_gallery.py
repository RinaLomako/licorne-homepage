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

GALLERIES = {
    "black-and-white": "Black & White",
    "colours-street": "Colours / Street",
    "portraits": "Portraits",
}

SOURCE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


# --- image processing --------------------------------------------------------

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

def manifest_path(gallery: str) -> Path:
    return REPO / "galleries" / gallery / "manifest.json"


def read_manifest(gallery: str) -> list[dict]:
    p = manifest_path(gallery)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def write_manifest(gallery: str, entries: list[dict]) -> None:
    p = manifest_path(gallery)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, indent=2) + "\n")


def next_id(entries: list[dict]) -> int:
    used = [int(e["id"]) for e in entries if e["id"].isdigit()]
    return max(used, default=0) + 1


# --- page generation ---------------------------------------------------------

def nav_html(active: str) -> str:
    items = [
        ("/galleries/black-and-white/", "Black &amp; White", "black-and-white"),
        ("/galleries/colours-street/", "Colours / Street", "colours-street"),
        ("/galleries/portraits/", "Portraits", "portraits"),
        ("/about/", "About", "about"),
        ("/contact/", "Contact", "contact"),
    ]
    return "\n".join(
        f'      <a href="{href}"{" class=\"active\"" if key == active else ""}>{label}</a>'
        for href, label, key in items
    )


def figure_html(gallery: str, entry: dict) -> str:
    base = f"/galleries/{gallery}/images"
    stem = entry["id"]
    grid = [w for w in entry["widths"] if w in GRID_WIDTHS]
    largest = max(entry["widths"])

    srcset = ", ".join(f"{base}/{derivative_name(stem, w)} {w}w" for w in grid)
    fallback = derivative_name(stem, grid[-1] if grid else largest)
    alt = entry.get("alt") or f"{GALLERIES[gallery]} — {stem}"
    caption = entry.get("caption", "")

    return f"""      <figure class="shot">
        <button class="shot-open" type="button"
                data-full="{base}/{derivative_name(stem, largest)}"
                data-caption="{caption}"
                aria-label="View at full quality">
          <img src="{base}/{fallback}"
               srcset="{srcset}"
               sizes="(min-width: 900px) 900px, 100vw"
               width="{entry['width']}" height="{entry['height']}"
               loading="lazy" decoding="async"
               alt="{alt}" />
        </button>
{f'        <figcaption>{caption}</figcaption>' if caption else ''}
      </figure>"""


def render_gallery(gallery: str) -> str:
    title = GALLERIES[gallery]
    entries = read_manifest(gallery)
    figures = "\n".join(figure_html(gallery, e) for e in entries)
    count = len(entries)

    return f"""<!doctype html>
<!-- GENERATED by tools/build_gallery.py — do not edit by hand. -->
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{title} — Yekaterina Lomako</title>
  <meta name="description" content="{title} photographs by Yekaterina Lomako." />
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="/assets/css/styles.css" />
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">Yekaterina Lomako</a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav"
            aria-label="Menu"><span></span><span></span><span></span></button>
    <nav class="nav" id="nav">
{nav_html(gallery)}
    </nav>
  </header>

  <main class="container">
    <h1 class="page-title">{title}</h1>
    <p class="muted small">{count} photograph{'s' if count != 1 else ''}</p>

    <section class="shots">
{figures}
    </section>
  </main>

  <div class="lightbox" id="lightbox" aria-hidden="true" role="dialog" aria-modal="true">
    <button class="lb-btn lb-close" id="lbClose" type="button" aria-label="Close">&times;</button>
    <button class="lb-btn lb-prev" id="lbPrev" type="button" aria-label="Previous">&#8249;</button>
    <button class="lb-btn lb-next" id="lbNext" type="button" aria-label="Next">&#8250;</button>
    <figure class="lb-stage">
      <img id="lbImg" alt="" />
      <figcaption class="lb-caption" id="lbCaption"></figcaption>
    </figure>
  </div>

  <footer class="site-footer">
    <span class="muted small">&copy; Yekaterina Lomako <span data-year></span></span>
  </footer>

  <script src="/assets/js/site.js" defer></script>
  <script src="/assets/js/gallery.js" defer></script>
</body>
</html>
"""


def write_gallery_page(gallery: str) -> None:
    out = REPO / "galleries" / gallery / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_gallery(gallery))


# --- commands ----------------------------------------------------------------

def cmd_ingest(args) -> int:
    incoming = REPO / "incoming"
    total = 0

    for gallery in GALLERIES:
        src_dir = incoming / gallery
        if not src_dir.is_dir():
            continue

        photos = sorted(
            p for p in src_dir.iterdir()
            if p.suffix.lower() in SOURCE_EXTS and not p.name.startswith(".")
        )
        if not photos:
            continue

        entries = read_manifest(gallery)
        out_dir = REPO / "galleries" / gallery / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        n = next_id(entries)

        for photo in photos:
            stem = f"{n:03d}"
            try:
                entry = write_derivatives(photo, out_dir, stem, force=args.force)
            except Exception as exc:                      # noqa: BLE001
                print(f"  SKIPPED {photo.name}: {exc}", file=sys.stderr)
                continue
            entry["alt"] = f"{GALLERIES[gallery]} — {photo.stem}"
            entries.append(entry)
            print(f"  {gallery}/{stem}  <- {photo.name}  ({entry['width']}x{entry['height']})")
            if not args.keep:
                photo.unlink()
            n += 1
            total += 1

        write_manifest(gallery, entries)
        write_gallery_page(gallery)

    print(f"ingested {total} photo(s)")
    return 0


def cmd_rebuild(args) -> int:
    for gallery in GALLERIES:
        entries = read_manifest(gallery)
        write_gallery_page(gallery)

        # Drop derivatives no longer referenced by the manifest. This is what
        # makes removing a photo work: delete its entry from manifest.json and
        # its image files go with it on the next rebuild.
        wanted = {
            derivative_name(e["id"], w)
            for e in entries
            for w in e["widths"]
        }
        images = REPO / "galleries" / gallery / "images"
        removed = 0
        if images.is_dir():
            for f in images.iterdir():
                if f.is_file() and f.suffix == ".webp" and f.name not in wanted:
                    f.unlink()
                    removed += 1

        note = f", pruned {removed} orphaned file(s)" if removed else ""
        print(f"  rebuilt galleries/{gallery}/index.html ({len(entries)} photos{note})")
    return 0


def cmd_import_legacy(args) -> int:
    """Build the three new galleries from the old six, using a mapping file."""
    rows = json.loads(Path(args.mapping).read_text())
    base = REPO.parent          # website_licorne/, where data/ lives

    buckets: dict[str, list[dict]] = {g: [] for g in GALLERIES}
    for row in rows:
        if row["gallery_old"] == "people":
            buckets["portraits"].append(row)
        elif row["is_bw"]:
            buckets["black-and-white"].append(row)
        else:
            buckets["colours-street"].append(row)

    for gallery, rows_for in buckets.items():
        out_dir = REPO / "galleries" / gallery / "images"
        if out_dir.exists() and args.force:
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        entries = []
        for i, row in enumerate(rows_for, start=1):
            src = base / row["source"]
            stem = f"{i:03d}"
            entry = write_derivatives(src, out_dir, stem, force=args.force)
            entry["alt"] = f"{GALLERIES[gallery]} — {stem}"
            entries.append(entry)
            print(f"  {gallery}/{stem}  <- {row['source']}")

        write_manifest(gallery, entries)
        write_gallery_page(gallery)
        print(f"{gallery}: {len(entries)} photos\n")

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

    p = sub.add_parser("import-legacy", help="one-off import from the old gallery layout")
    p.add_argument("--mapping", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_import_legacy)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
