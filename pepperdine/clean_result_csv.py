#!/usr/bin/env python3
import argparse
import csv
from typing import List, Set, Tuple


def has_linkedin(url: str) -> bool:
    if not url:
        return False
    u = url.strip().lower()
    return "linkedin.com" in u


def main():
    parser = argparse.ArgumentParser(description="Filter result CSV to rows with LinkedIn URL and specific columns")
    parser.add_argument("--input", "-i", default="result-3.csv", help="Input CSV path")
    parser.add_argument("--output", "-o", default="result_clean.csv", help="Output CSV path")
    args = parser.parse_args()

    kept_rows: List[Tuple[str, str, str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Identify columns (case-insensitive)
        fn_key = ln_key = url_key = None
        for k in (reader.fieldnames or []):
            lk = k.lower()
            if lk in ("firstname", "first_name", "first"):
                fn_key = k
            elif lk in ("lastname", "last_name", "last"):
                ln_key = k
            elif lk in ("url", "linkedin", "linkedin_url"):
                url_key = k
        if not fn_key or not ln_key or not url_key:
            raise ValueError("Input must include firstName/lastName/url columns")

        for row in reader:
            first = (row.get(fn_key, "") or "").strip()
            last = (row.get(ln_key, "") or "").strip()
            url = (row.get(url_key, "") or "").strip()
            if not first or not last:
                continue
            if not has_linkedin(url):
                continue
            key = (first.lower(), last.lower(), url.lower())
            if key in seen:
                continue
            seen.add(key)
            kept_rows.append((first, last, "Pepperdine", url))

    with open(args.output, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["First Name", "Last Name", "Pepperdine", "Linkedin URL"])  # as requested
        writer.writerows(kept_rows)

    print(f"Wrote {len(kept_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
