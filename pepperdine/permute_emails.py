#!/usr/bin/env python3
import argparse
import csv
import re
from typing import Iterable, List, Optional, Set, Tuple

from unidecode import unidecode

PEPPERDINE_DOMAIN = "pepperdine.edu"


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


def split_username(username: str) -> Tuple[Optional[str], Optional[str]]:
    if not username:
        return None, None
    pieces = re.split(r"[\._\-]+|\d+", username)
    pieces = [normalize_token(p) for p in pieces if p]
    if len(pieces) == 0:
        return None, None
    if len(pieces) == 1:
        token = pieces[0]
        return (token if token else None), None
    return (pieces[0] or None), (pieces[-1] or None)


def generate_permutations(first: Optional[str], last: Optional[str], mode: str = "strict") -> Set[str]:
    candidates: Set[str] = set()
    if not first and not last:
        return candidates

    f = (first or "")
    l = (last or "")
    fi = f[:1] if f else ""
    li = l[:1] if l else ""

    base_variants: List[str] = []

    if f and l:
        base_variants.extend([
            f"{f}.{l}",        # first.last
            f"{fi}{l}",        # flast
            f"{f}{li}",        # firstl
            f"{f}{l}",         # firstlast (added to strict)
        ])
        if mode == "broad":
            base_variants.extend([
                f"{l}{fi}",
                f"{f}_{l}",
                f"{fi}_{l}",
                f"{f}-{l}",
                f"{l}.{f}",
            ])
    else:
        if f:
            base_variants.append(f)
        if l and mode == "broad":
            base_variants.append(l)

    for local_part in base_variants:
        local_part = re.sub(r"[^a-z0-9\._-]", "", local_part)
        local_part = re.sub(r"[\._-]+", lambda m: m.group(0)[0], local_part)
        local_part = local_part.strip("._-")
        if not local_part:
            continue
        candidates.add(f"{local_part}@{PEPPERDINE_DOMAIN}")

    return candidates


def derive_name_from_row(full_name: str, username: str) -> Tuple[Optional[str], Optional[str]]:
    first, last = split_name(full_name)
    if first and last:
        return first, last
    u_first, u_last = split_username(username)
    return (first or u_first), (last or u_last)


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
    parser = argparse.ArgumentParser(description="Generate pepperdine.edu email permutations from names")
    parser.add_argument("input_csv", nargs="?", default="pepperdineCO2029.csv", help="Input CSV with full name or first/last columns")
    parser.add_argument("--output", "-o", default="permuted_emails.csv", help="Output CSV path")
    parser.add_argument("--mode", choices=["strict", "broad"], default="strict", help="Permutation breadth: strict=few high-probability formats; broad=more variants")
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N people (0 = no limit)")
    args = parser.parse_args()

    unique_emails: Set[str] = set()
    output_rows: List[Tuple[str, str, str]] = []

    processed_people = 0
    for full_name, username in read_rows(args.input_csv):
        if args.limit and processed_people >= args.limit:
            break
        if not full_name and not username:
            continue
        first, last = derive_name_from_row(full_name, username)
        if not first and not last:
            continue
        emails = generate_permutations(first, last, mode=args.mode)
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

    print(f"Wrote {len(output_rows)} permuted emails to {args.output} (mode={args.mode}, people={processed_people})")


if __name__ == "__main__":
    main()
