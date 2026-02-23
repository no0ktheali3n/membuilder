# scripts/patch_titles.py
# Quick script to patch titles in already scraped checkpoint files where title extraction failed and defaulted to URL.
import json, re
from pathlib import Path

def extract_title(markdown: str, url: str) -> str:
    match = re.search(r"^#{1,2}\s+(.+?)(?:\s*\[[\s\S]*)?$", markdown, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return url

checkpoint_dir = Path("data/checkpoints")
path = sorted(checkpoint_dir.glob("*.jsonl"))[-1]

def patch_needed(p: dict) -> bool:
    title = p.get("title", "")
    url = p.get("url", "")
    # Needs patch if still a URL fallback OR contains anchor junk
    return title == url or "[ ](" in title

# then in the loop:


patched = []
fixed = 0
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        p = json.loads(line)
        if patch_needed(p):
            new_title = extract_title(p.get("markdown", ""), p["url"])
            p["title"] = new_title
            if new_title != p["url"]:
                fixed += 1
        patched.append(p)

with open(path, "w", encoding="utf-8") as f:
    for p in patched:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"Patched {fixed}/{len(patched)} titles.")