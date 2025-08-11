#!/usr/bin/env python3
import argparse
import csv
import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

EMAIL_RE = re.compile(r"^([^@]+)@([A-Za-z0-9\.-]+)$")


def split_name(full_name: str) -> Tuple[str, str]:
    parts = [p for p in re.split(r"\s+", full_name.strip()) if p]
    if not parts:
        return "", ""
    first = parts[0].lower()
    last = parts[-1].lower() if len(parts) > 1 else ""
    return first, last


def classify_local(local: str, first: str, last: str) -> int:
    l = local.lower()
    # exact first.last
    if first and last and l == f"{first}.{last}":
        return 3
    # exact firstlast
    if first and last and l == f"{first}{last}":
        return 2
    # flast
    if first and last and len(first) >= 1 and l == f"{first[0]}{last}":
        return 1
    # firstl
    if first and last and len(last) >= 1 and l == f"{first}{last[0]}":
        return 1
    # fallback: rank by presence of dot between alpha tokens
    if "." in l:
        return 2  # likely first.last-like
    return 0


def choose_best(existing_email: str, candidate_email: str, full_name: str) -> str:
    f, l = split_name(full_name)
    def score(email: str) -> Tuple[int, int]:
        m = EMAIL_RE.match(email)
        local = m.group(1) if m else email.split("@", 1)[0]
        pattern_rank = classify_local(local, f, l)
        return (pattern_rank, len(local))
    return max([existing_email, candidate_email], key=score)


def merge_verified(input_dir: str, output_csv: str) -> int:
    files = sorted(glob.glob(os.path.join(input_dir, "verified_colgate_*.csv")))
    best_by_name: Dict[str, str] = {}
    for fp in files:
        with open(fp, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                full = (row.get("full_name", "") or "").strip()
                email = (row.get("email", "") or "").strip().lower()
                if not full or not email:
                    continue
                if full not in best_by_name:
                    best_by_name[full] = email
                else:
                    best_by_name[full] = choose_best(best_by_name[full], email, full)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["full_name", "email"])
        writer.writeheader()
        for full, email in best_by_name.items():
            writer.writerow({"full_name": full, "email": email})
    return len(best_by_name)


def main():
    ap = argparse.ArgumentParser(description="Merge verified Colgate emails, dedupe by name choosing best email")
    ap.add_argument("--input-dir", default="colgate", help="Directory containing verified_colgate_*.csv")
    ap.add_argument("--output", default="colgate/verified_colgate_all.csv", help="Output CSV path")
    args = ap.parse_args()
    count = merge_verified(args.input_dir, args.output)
    print(f"Wrote {count} unique people to {args.output}")


if __name__ == "__main__":
    main()
