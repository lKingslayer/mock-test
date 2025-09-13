#!/usr/bin/env python3
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "fixtures"

# Deterministic 1x1 PNG (transparent) via base64, to avoid external deps
_PNG_1x1 = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6wZSYAAAAASUVORK5CYII="
)

# Minimal placeholder bytes for non-binary formats; service ignores content.
_CONTENT = {
    "pdf": b"%PDF-1.1\n% minimal placeholder\n%%EOF\n",
    "docx": b"DOCX placeholder (content ignored by stateless server)\n",
    "pptx": b"PPTX placeholder (content ignored by stateless server)\n",
    "xlsx": b"XLSX placeholder (content ignored by stateless server)\n",
    "txt": b"hello from txt\n",
    "md": b"# notes\n\n- tiny fixture file\n",
    "csv": b"id,value\n1,alpha\n",
    "html": b"<!doctype html><title>fixture</title><p>hi</p>",
    "json": b"{\n  \"ok\": true\n}\n",
}

FILES = [
    (FX / "doc" / "Report.DOCX", _CONTENT["docx"]),
    (FX / "ppt" / "Slides.PPTX", _CONTENT["pptx"]),
    (FX / "xlsx" / "Data.XLSX", _CONTENT["xlsx"]),
    (FX / "pdf" / "Spec.PDF", _CONTENT["pdf"]),
    (FX / "txt" / "readme.txt", _CONTENT["txt"]),
    (FX / "md" / "notes.MD", _CONTENT["md"]),
    (FX / "csv" / "table.CSV", _CONTENT["csv"]),
    (FX / "html" / "page.html", _CONTENT["html"]),
    (FX / "json" / "config.json", _CONTENT["json"]),
    (FX / "img" / "pixel.png", _PNG_1x1),
]


def main() -> None:
    FX.mkdir(parents=True, exist_ok=True)
    for path, data in FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # Simple sanity check
    created = [str(p.relative_to(ROOT)) for p, _ in FILES if p.exists()]
    print("Created fixtures:")
    for c in created:
        print(" -", c)
    if len(created) != 10:
        raise SystemExit(f"Expected 10 fixtures, found {len(created)}")


if __name__ == "__main__":
    main()