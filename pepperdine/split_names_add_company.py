#!/usr/bin/env python3
import argparse
import csv
import re
from typing import Iterator, List, Optional, Tuple

from unidecode import unidecode

NAME_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")


def split_name(full_name: str) -> Optional[Tuple[str, str]]:
    if not full_name:
        return None
    s = unidecode(full_name).strip()
    # Keep letters, spaces, hyphens, and apostrophes
    s = re.sub(r"[^A-Za-z\s\-']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    tokens: List[str] = NAME_TOKEN_RE.findall(s)
    if len(tokens) < 2:
        return None

    first = tokens[0].capitalize()
    last = tokens[-1].capitalize()
    return first, last


def read_full_names(path: str) -> Iterator[str]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Accept common header names
        name_key = None
        headers = reader.fieldnames or []
        for k in headers:
            if k.lower() in ("full_name", "fullname", "name"):
                name_key = k
                break
        if name_key is None:
            raise ValueError("Input CSV must have a single column named full_name")
        for row in reader:
            yield (row.get(name_key, "") or "").strip()


def main():
    parser = argparse.ArgumentParser(description="Split names into first_name,last_name and add company")
    parser.add_argument("--input", "-i", default="real_names_llm.csv", help="Input CSV (with full_name column)")
    parser.add_argument("--output", "-o", default="real_names_for_apollo.csv", help="Output CSV path")
    parser.add_argument("--company", default="Pepperdine", help="Company value to set")
    args = parser.parse_args()

    rows: List[Tuple[str, str, str]] = []
    seen: set = set()

    for full_name in read_full_names(args.input):
        parts = split_name(full_name)
        if not parts:
            continue
        first, last = parts
        key = (first.lower(), last.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append((first, last, args.company))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["first_name", "last_name", "company"]) 
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()

