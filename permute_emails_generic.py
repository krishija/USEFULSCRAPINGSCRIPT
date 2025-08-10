#!/usr/bin/env python3
import argparse
import csv
import re
from typing import Iterable, List, Optional, Set, Tuple

from unidecode import unidecode


def normalize_token(token: str) -> str:
    token = unidecode(token)
    token = token.lower()
    token = re.sub(r"[^a-z]", "", token)
    return token


def split_name(full_name_raw: str) -> Tuple[Optional[str], Optional[str]]:
    if not full_name_raw:
        return None, None
    ascii_name = unidecode(full_name_raw)
    ascii_name = re.sub(r"[\-\._]+", " ", ascii_name)
    ascii_name = re.sub(r"[^A-Za-z\s]", " ", ascii_name)
    parts = [p for p in ascii_name.strip().split() if p]
    if len(parts) == 0:
        return None, None
    if len(parts) == 1:
        only = normalize_token(parts[0])
        return (only if only else None), None
    first = normalize_token(parts[0])
    last = normalize_token(parts[-1])
    return (first if first else None), (last if last else None)


def generate_permutations(first: Optional[str], last: Optional[str], domain: str) -> Set[str]:
    candidates: Set[str] = set()
    if not first and not last:
        return candidates
    f = (first or "")
    l = (last or "")
    fi = f[:1] if f else ""
    li = l[:1] if l else ""
    variants = []
    if f and l:
        variants.extend([
            f"{f}.{l}",
            f"{fi}{l}",
            f"{f}{li}",
            f"{f}{l}",
        ])
    elif f:
        variants.append(f)
    for local_part in variants:
        lp = re.sub(r"[^a-z0-9\._-]", "", local_part)
        lp = re.sub(r"[\._-]+", lambda m: m.group(0)[0], lp).strip("._-")
        if lp:
            candidates.add(f"{lp}@{domain}")
    return candidates


def read_rows(input_csv: str) -> Iterable[Tuple[str, str]]:
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        full_name_key = None
        username_key = None
        first_key = None
        last_key = None
        header = reader.fieldnames or []
        for k in header:
            lk = k.lower()
            if lk in ("fullname", "full_name", "name"):
                full_name_key = k
            if lk in ("username", "user_name", "handle"):
                username_key = k
            if lk in ("first_name", "firstname", "first"):
                first_key = k
            if lk in ("last_name", "lastname", "last"):
                last_key = k
        if full_name_key is None and first_key and last_key:
            for row in reader:
                first = (row.get(first_key, "") or "").strip()
                last = (row.get(last_key, "") or "").strip()
                if not first or not last:
                    yield "", ""
                    continue
                yield f"{first} {last}", ""
            return
        if full_name_key is None and "fullName" in (reader.fieldnames or []):
            full_name_key = "fullName"
        if username_key is None:
            username_key = "username" if "username" in (reader.fieldnames or []) else None
        if full_name_key is None and (first_key is None or last_key is None):
            raise ValueError("CSV must include either (full name + username) or (first_name & last_name)")
        for row in reader:
            yield (row.get(full_name_key, "") or "").strip(), (row.get(username_key, "") or "").strip()


def main():
    parser = argparse.ArgumentParser(description="Generate email permutations from names for a given domain")
    parser.add_argument("input_csv", help="Input CSV with full_name or first/last columns")
    parser.add_argument("--output", "-o", default="permuted_emails_generic.csv", help="Output CSV path")
    parser.add_argument("--domain", required=True, help="Email domain, e.g., colgate.edu")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N people (0 = all)")
    args = parser.parse_args()

    unique_emails: Set[str] = set()
    output_rows: List[Tuple[str, str, str]] = []

    processed_people = 0
    for full_name, username in read_rows(args.input_csv):
        if args.limit and processed_people >= args.limit:
            break
        if not full_name and not username:
            continue
        first, last = split_name(full_name)
        if not first and not last:
            continue
        emails = generate_permutations(first, last, domain=args.domain)
        person_had_any = False
        for email in emails:
            if email in unique_emails:
                continue
            unique_emails.add(email)
            output_rows.append((full_name, username, email))
            person_had_any = True
        if person_had_any:
            processed_people += 1

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["full_name", "username", "email"]) 
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} permuted emails to {args.output} (people={processed_people}, domain={args.domain})")


if __name__ == "__main__":
    main()
