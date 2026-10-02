#!/usr/bin/env python3
"""Build the self-contained personal hearing-test page.

Embeds six trimmed clips as base64 data URIs into products/hearing-test.html.
Regenerate with:  python lab/scripts/build_hearing_test.py
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import html
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLIP_DIR = ROOT / "lab" / "audio"
TEMPLATE = ROOT / "lab" / "templates" / "hearing_test.tpl.html"
OUT = ROOT / "products" / "hearing-test.html"

# clip file -> manifest id
CLIPS = [
    ("du128.mp3", "du-128", "渡口 · 128 kbps MP3", "audio/mpeg"),
    ("du320.mp3", "du-320", "渡口 · 320 kbps MP3", "audio/mpeg"),
    ("duflac.flac", "du-flac", "渡口 · FLAC 无损", "audio/flac"),
    ("h128.mp3", "h-128", "加州旅馆 · 128 kbps MP3", "audio/mpeg"),
    ("h320.mp3", "h-320", "加州旅馆 · 320 kbps MP3", "audio/mpeg"),
    ("hflac.flac", "h-flac", "加州旅馆 · FLAC 无损", "audio/flac"),
]

SOURCE_FILES = [
    "渡口普.mp3", "渡口中.mp3", "渡口无损.flac",
    "加州旅馆普.mp3", "加州旅馆中.mp3", "加州旅馆无损.flac",
]


def probe(path: pathlib.Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name,sample_rate,channels,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    stream = info["streams"][0]
    return {
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate", 0)),
        "channels": int(stream.get("channels", 0)),
        "bit_rate": int(stream["bit_rate"]) if stream.get("bit_rate") else None,
        "duration": round(float(info["format"]["duration"]), 2),
    }


def main() -> int:
    if not TEMPLATE.exists():
        print(f"template missing: {TEMPLATE}", file=sys.stderr)
        return 1
    manifest = []
    placeholders = {}
    for fname, cid, label, mime in CLIPS:
        p = CLIP_DIR / fname
        if not p.exists():
            print(f"clip missing: {p}", file=sys.stderr)
            return 1
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        placeholders[f"__AUDIO_{cid.upper().replace('-', '_')}__"] = f"data:{mime};base64,{b64}"
        manifest.append({
            "id": cid,
            "label": label,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()[:16],
            **probe(p),
        })

    src_meta = {n: hashlib.sha256(
        next(pathlib.Path("/home/siri/.dsh/attachments/v1/files").glob(f"**/{n}")).read_bytes()
    ).hexdigest()[:16] for n in SOURCE_FILES}

    tpl = TEMPLATE.read_text(encoding="utf-8")
    for key, val in placeholders.items():
        if key not in tpl:
            print(f"placeholder missing in template: {key}", file=sys.stderr)
            return 1
        tpl = tpl.replace(key, val)

    meta = {
        "generated_at": datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "generator": "lab/scripts/build_hearing_test.py",
        "clips": manifest,
        "source_sha256_16": src_meta,
    }
    tpl = tpl.replace("__MANIFEST_JSON__", json.dumps(meta, ensure_ascii=False, indent=1))

    # 内嵌数据块(供 check_artifact.py 核验来历与素材指纹)
    artifact_data = {
        "provenance": {
            "generatedAt": meta["generated_at"],
            "generator": meta["generator"],
            "sources": SOURCE_FILES,
        },
        "clips": manifest,
    }
    tpl = tpl.replace(
        "</body>",
        '<script id="artifact-data" type="application/json">'
        + json.dumps(artifact_data, ensure_ascii=False).replace("<", "\\u003c")
        + "</script>\n</body>",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(tpl, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1e6:.1f} MB, {len(manifest)} clips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
