import json
import sys
from pathlib import Path

checkpoint_dir = Path("data/checkpoints")
files = list(checkpoint_dir.glob("*.jsonl"))

if not files:
    print("No checkpoint files found.")
    sys.exit(1)

path = sorted(files)[-1]
print(f"Reading: {path}\n")

pages = []
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            pages.append(json.loads(line))

ok     = [p for p in pages if p["status"] == "ok"]
failed = [p for p in pages if p["status"] == "failed"]

print(f"Total pages : {len(pages)}")
print(f"  OK        : {len(ok)}")
print(f"  Failed    : {len(failed)}")

# --- size distribution ---
sizes = [len(p.get("markdown", "")) for p in ok]
if sizes:
    print(f"\nMarkdown size distribution (ok pages):")
    print(f"  Min    : {min(sizes):,} chars")
    print(f"  Max    : {max(sizes):,} chars")
    print(f"  Avg    : {int(sum(sizes)/len(sizes)):,} chars")
    print(f"  Median : {sorted(sizes)[len(sizes)//2]:,} chars")

# ---------------------------------------------------------------------------
# Anomaly thresholds
# ---------------------------------------------------------------------------
EMPTY_THRESHOLD     = 500
THIN_THRESHOLD      = 2_000
LARGE_THRESHOLD     = 50_000
VERY_LARGE          = 150_000
NON_HTML_EXTENSIONS = (".json", ".xml", ".yaml", ".yml", ".csv")

truly_empty   = [p for p in ok if len(p.get("markdown", "")) < 2]
near_empty    = [p for p in ok if 2 <= len(p.get("markdown", "")) < EMPTY_THRESHOLD]
thin          = [p for p in ok if EMPTY_THRESHOLD <= len(p.get("markdown", "")) < THIN_THRESHOLD]

# Large but expected: dense reference/API pages
large_ref     = [p for p in ok
                 if LARGE_THRESHOLD <= len(p.get("markdown", "")) < VERY_LARGE
                 and any(seg in p["url"] for seg in ("/reference/", "/api/", "/config-api/"))]
# Large and NOT a known reference URL — more suspicious
large_suspect = [p for p in ok
                 if LARGE_THRESHOLD <= len(p.get("markdown", "")) < VERY_LARGE
                 and not any(seg in p["url"] for seg in ("/reference/", "/api/", "/config-api/"))]
# Anything over 150k flagged regardless of URL
very_large    = [p for p in ok if len(p.get("markdown", "")) >= VERY_LARGE]

non_html      = [p for p in ok if any(p["url"].endswith(ext) for ext in NON_HTML_EXTENSIONS)]
no_title      = [p for p in ok if p.get("title", "").strip() == p.get("url", "").strip()]

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
print(f"\n--- ANOMALY REPORT ---")

print(f"\n[1a] Truly empty pages (< 2 chars): {len(truly_empty)}")
for p in truly_empty:
    print(f"       {len(p.get('markdown','')):>7,} chars  {p['url']}")

print(f"\n[1b] Near-empty pages (2–{EMPTY_THRESHOLD} chars): {len(near_empty)}")
for p in near_empty:
    print(f"       {len(p.get('markdown','')):>7,} chars  {p['url']}")

print(f"\n[1c] Thin pages ({EMPTY_THRESHOLD}–{THIN_THRESHOLD:,} chars) — low value, not broken: {len(thin)}")
for p in thin:
    print(f"       {len(p.get('markdown','')):>7,} chars  {p['url']}")

print(f"\n[2a] Large reference pages ({LARGE_THRESHOLD//1000}k–{VERY_LARGE//1000}k chars) — expected, monitor: {len(large_ref)}")
for p in large_ref:
    print(f"     {len(p.get('markdown','')):>9,} chars  {p['url']}")

print(f"\n[2b] Large NON-reference pages ({LARGE_THRESHOLD//1000}k–{VERY_LARGE//1000}k chars) — investigate: {len(large_suspect)}")
for p in large_suspect:
    print(f"     {len(p.get('markdown','')):>9,} chars  {p['url']}")

print(f"\n[2c] Very large pages (> {VERY_LARGE//1000}k chars) — likely CSS selector miss: {len(very_large)}")
for p in very_large:
    print(f"     {len(p.get('markdown','')):>9,} chars  {p['url']}")

print(f"\n[3]  Non-HTML content that slipped through: {len(non_html)}")
for p in non_html:
    print(f"       {p['url']}")

print(f"\n[4]  Missing title (fell back to URL): {len(no_title)}")
if no_title:
    print(f"     (showing first 5)")
    for p in no_title[:5]:
        print(f"       {p['url']}")

if failed:
    print(f"\n[5]  Failed pages: {len(failed)}")
    for p in failed:
        print(f"       {p['url']}  —  {p.get('error', '')}")

# ---------------------------------------------------------------------------
# Title diagnostic
# ---------------------------------------------------------------------------
print(f"\n--- TITLE DIAGNOSTIC (first 3 ok pages) ---")
for p in ok[:3]:
    print(f"  stored title : {repr(p.get('title', 'MISSING'))}")
    print(f"  url          : {p['url']}")
    print()

# ---------------------------------------------------------------------------
# First page preview
# ---------------------------------------------------------------------------
print(f"--- FIRST OK PAGE PREVIEW ---")
if ok:
    first = ok[0]
    print(f"Title : {first['title']}")
    print(f"URL   : {first['url']}")
    print(f"Length: {len(first['markdown']):,} chars")
    print(f"\n{first['markdown'][:1000]}")

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
print(f"\n--- VERDICT ---")
# Non-HTML and very_large are the only genuinely actionable critical issues
# Truly empty pages are expected for JS-heavy or non-HTML URLs
critical = len(very_large) + len(non_html) + len(failed)
warnings = len(truly_empty) + len(near_empty) + len(large_suspect) + len(no_title)

if critical == 0 and warnings == 0:
    print("✓ No anomalies detected. Data looks clean — ready for parser.")
elif critical == 0:
    print(f"⚠  0 critical issues, {warnings} warnings. Likely safe to proceed — review warnings above.")
else:
    print(f"✗  {critical} critical issues, {warnings} warnings. Investigate critical issues before parser.")

pct = round((critical + warnings) / len(pages) * 100, 1)
print(f"   {pct}% of total pages flagged.")