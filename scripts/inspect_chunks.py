"""
CLI: inspect and validate chunk output before embedding.

Usage:
    uv run python scripts/inspect_chunks.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

chunk_dir = Path("data/chunks")
files = sorted(chunk_dir.glob("*.jsonl"))

if not files:
    print("No chunk files found in data/chunks/")
    sys.exit(1)

path = files[-1]
print(f"Reading: {path}\n")

chunks = []
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            chunks.append(json.loads(line))

print(f"Total chunks : {len(chunks)}")

# --- size distribution ---
sizes = [len(c["content"]) for c in chunks]
if sizes:
    print(f"\nChunk size distribution:")
    print(f"  Min    : {min(sizes):,} chars")
    print(f"  Max    : {max(sizes):,} chars")
    print(f"  Avg    : {int(sum(sizes)/len(sizes)):,} chars")
    print(f"  Median : {sorted(sizes)[len(sizes)//2]:,} chars")

# --- chunks per page ---
per_page = defaultdict(int)
for c in chunks:
    per_page[c["source_url"]] += 1

counts = list(per_page.values())
print(f"\nChunks per page:")
print(f"  Min    : {min(counts)}")
print(f"  Max    : {max(counts)}")
print(f"  Avg    : {int(sum(counts)/len(counts))}")

# --- top 5 pages by chunk count ---
print(f"\nTop 5 pages by chunk count:")
for url, count in sorted(per_page.items(), key=lambda x: -x[1])[:5]:
    print(f"  {count:>4} chunks  {url}")

# --- section distribution ---
section_counts = defaultdict(int)
for c in chunks:
    crumb = c.get("breadcrumb", [])
    section = crumb[0] if crumb else "unknown"
    section_counts[section] += 1

print(f"\nChunks by top-level section:")
for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
    bar = "█" * (count // 20)
    print(f"  {section:<30} {count:>5}  {bar}")

# --- anomaly detection ---
TINY_CHUNK    = 100     # probably a heading with no body
LARGE_CHUNK   = 8_000   # may need further splitting for embedding quality

tiny   = [c for c in chunks if len(c["content"]) < TINY_CHUNK]
large  = [c for c in chunks if len(c["content"]) > LARGE_CHUNK]
no_heading = [c for c in chunks if not c.get("heading") or c["heading"] == c.get("source_url")]

print(f"\n--- ANOMALY REPORT ---")

print(f"\n[1] Tiny chunks (< {TINY_CHUNK} chars) — heading stubs, likely noise: {len(tiny)}")
for c in tiny[:10]:
    print(f"    {len(c['content']):>5} chars  [{c['heading']}]  {c['source_url']}")
if len(tiny) > 10:
    print(f"    ... and {len(tiny) - 10} more")

print(f"\n[2] Large chunks (> {LARGE_CHUNK:,} chars) — may affect embedding quality: {len(large)}")
for c in large[:10]:
    print(f"    {len(c['content']):>6,} chars  [{c['heading']}]  {c['source_url']}")
if len(large) > 10:
    print(f"    ... and {len(large) - 10} more")

print(f"\n[3] Missing headings: {len(no_heading)}")
for c in no_heading[:5]:
    print(f"    {c['source_url']}")

# --- sample output ---
print(f"\n--- SAMPLE CHUNKS (first 3) ---")
for c in chunks[:3]:
    print(f"\n  Heading  : {c['heading']}")
    print(f"  Page     : {c['page_title']}")
    print(f"  URL      : {c['source_url']}")
    print(f"  Breadcrumb: {' > '.join(c['breadcrumb'])}")
    print(f"  Position : {c['chunk_index'] + 1}/{c['total_chunks']}")
    print(f"  Length   : {len(c['content']):,} chars")
    print(f"  Preview  : {c['content'][:300].strip()!r}")

# --- verdict ---
print(f"\n--- VERDICT ---")
critical = 0
warnings = len(tiny) + len(large)

if critical == 0 and warnings == 0:
    print("✓ Chunks look clean — ready for embedding.")
elif warnings > 0:
    pct = round(warnings / len(chunks) * 100, 1)
    print(f"⚠  {warnings} chunks flagged ({pct}% of total). Review above — likely acceptable.")