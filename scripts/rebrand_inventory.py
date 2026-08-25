"""Inventory of brand terms across git-tracked files."""
import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]

PATTERNS = {
    "hermes_lower": re.compile(r"hermes"),
    "Hermes_Cap": re.compile(r"Hermes"),
    "HERMES_UP": re.compile(r"HERMES"),
    "nous_lower": re.compile(r"nous"),
    "Nous_Cap": re.compile(r"Nous"),
    "NOUS_UP": re.compile(r"NOUS"),
}

def is_probably_text(path, data):
    if b"\0" in data[:8192]:
        return False
    return True

def main():
    files = tracked_files()
    by_dir = collections.Counter()
    by_ext = collections.Counter()
    totals = collections.Counter()
    file_hits = collections.Counter()
    binary_skipped = []
    for rel in files:
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            continue
        if not is_probably_text(rel, data):
            binary_skipped.append(rel)
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        counts = {k: len(p.findall(text)) for k, p in PATTERNS.items()}
        total = sum(counts.values())
        if total:
            ext = os.path.splitext(rel)[1].lower() or "<none>"
            top = os.path.relpath(rel.replace("/", os.sep), ROOT).split(os.sep)[0]
            by_dir[top] += total
            by_ext[ext] += total
            for k, v in counts.items():
                totals[k] += v
            file_hits[rel] = total

    print("=== TOTALS BY VARIANT ===")
    for k, v in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"{k:14} {v}")
    print(f"\n=== FILES WITH HITS: {len(file_hits)} ===")
    print("\n=== BY TOP-LEVEL DIR ===")
    for k, v in sorted(by_dir.items(), key=lambda x: -x[1]):
        print(f"{k:30} {v}")
    print("\n=== BY EXTENSION (top 30) ===")
    for k, v in sorted(by_ext.items(), key=lambda x: -x[1])[:30]:
        print(f"{k:20} {v}")
    print(f"\n=== BINARY/NULL-BYTE FILES SKIPPED ({len(binary_skipped)}) ===")
    for p in binary_skipped[:50]:
        print(p)

if __name__ == "__main__":
    main()
