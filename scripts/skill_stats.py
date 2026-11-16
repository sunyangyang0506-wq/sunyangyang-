#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = {".md",".json",".csv",".py",".yml",".yaml",".sh"}

def count(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return 0 if not text else len(text.splitlines())

files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and p.suffix.lower() in TEXT]
total = skill = size = 0
for path in sorted(files):
    lines = count(path)
    total += lines
    size += path.stat().st_size
    if path.relative_to(ROOT).parts[0] == "skills":
        skill += lines
    print(f"{lines:5d}  {path.relative_to(ROOT)}")
print(f"files={len(files)} total_lines={total} skill_lines={skill} bytes={size}")
