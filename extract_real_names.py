#!/usr/bin/env python3
import argparse
import csv
import re
from typing import Iterable, List, Optional, Set, Tuple

from unidecode import unidecode


EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF]",
    flags=re.UNICODE,
)

FORBIDDEN_WORDS = {
    "class", "official", "account", "fan", "page", "love", "life", "shop", "store", "team",
    "alset", "exchange", "goods", "services", "club", "coach", "media", "music", "studio",
}

# Common US first names (expanded, used only for single-token filtering)
COMMON_FIRST_NAMES = {
    # Female
    "emma","olivia","sophia","ava","isabella","mia","charlotte","amelia","harper","evelyn","abigail",
    "emily","ella","scarlett","aria","lily","hannah","grace","victoria","natalie","zoe","zoey","madison",
    "anna","jade","sarah","jessica","karen","ashley","megan","meghan","maria","claire","katherine","katelyn",
    "kate","katie","julia","jordan","rachel","olivia","aubrey","avery","zoe","zoey","savanna","savannah",
    "jada","hayley","hailey","hailee","kayla","kaylee","ella","ellie","lydia","lillian","liliana","natalie",
    # Male
    "john","michael","david","james","robert","william","joseph","thomas","charles","christopher","daniel",
    "matthew","anthony","mark","paul","steven","andrew","joshua","kevin","brian","tyler","liam","noah",
    "oliver","benjamin","samuel","jacob","logan","jackson","jayden","ethan","alexander","nathan","nate",
    "nick","nicholas","mike","michael","alex","will","chris","dan","dylan","hayden","jack","henry","owen",
    # Unisex/common
    "taylor","hayden","jordan","cameron","parker","riley","reese","morgan","casey","bailey","peyton",
}

# Nickname-like tokens to exclude (single-token outputs)
NICKNAME_TOKENS = {
    "maddy","maddie","madi","mads","jo","sammy","sam","sophie","soph","lexi","lex","liz","lizzy",
    "ally","allye","allya","lilly","lil","mike","chris","tony","drew","andy","nate","nick","nik",
    "mel","ness","nat","ben","eli","beth","kat","katie","kylee","ellie","maggie","abby","allyson",
    "sav","savvy","allyssa","allysa","allyse","allyson","allysonn",
}

# Nickname-like suffixes (if short names end with these, likely a nickname)
NICKNAME_SUFFIXES = ("y", "ie", "i", "ee")

VOWELS = set("aeiouy")


def normalize_name(raw: str) -> str:
    s = unidecode(raw or "")
    s = EMOJI_PATTERN.sub(" ", s)
    s = re.sub(r"[\-_.]+", " ", s)
    s = re.sub(r"[^A-Za-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def has_vowel(token: str) -> bool:
    return any(ch in VOWELS for ch in token.lower())


def looks_like_name_token(token: str) -> bool:
    if len(token) < 2:
        return False
    if token.lower() in FORBIDDEN_WORDS:
        return False
    if not token.isalpha():
        return False
    if not has_vowel(token):
        return False
    return True


def is_nicknamey(token: str) -> bool:
    t = token.lower()
    if t in NICKNAME_TOKENS:
        return True
    # Very short or diminutive-style endings often indicate nicknames
    if (len(t) <= 4 and any(t.endswith(suf) for suf in NICKNAME_SUFFIXES)):
        return True
    return False


def is_likely_real_name(clean: str) -> Optional[str]:
    if not clean:
        return None
    parts: List[str] = clean.split()

    # Two-part names
    if len(parts) == 2:
        first, last = parts
        if looks_like_name_token(first) and looks_like_name_token(last) and len(last) >= 2:
            return f"{first.capitalize()} {last.capitalize()}"
        return None

    # Three-part names with short middle initial
    if len(parts) == 3 and len(parts[1]) <= 2:
        first, _, last = parts
        if looks_like_name_token(first) and looks_like_name_token(last) and len(last) >= 2:
            return f"{first.capitalize()} {last.capitalize()}"
        return None

    # Single-token names: allow uncommon, non-nicknamey tokens
    if len(parts) == 1:
        token = parts[0].lower()
        if not looks_like_name_token(token):
            return None
        if token in COMMON_FIRST_NAMES:
            return None
        if is_nicknamey(token):
            return None
        if len(token) < 4:
            return None
        return token.capitalize()

    return None


def read_rows(path: str) -> Iterable[str]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        name_key = None
        header = reader.fieldnames or []
        for k in header:
            lk = k.lower()
            if lk in ("fullname", "full_name", "name"):
                name_key = k
                break
        if name_key is None and "fullName" in header:
            name_key = "fullName"
        if name_key is None:
            raise ValueError("Input CSV must contain a full name column (e.g., fullName)")

        for row in reader:
            yield (row.get(name_key, "") or "").strip()


def main():
    parser = argparse.ArgumentParser(description="Extract likely real names (looser filter incl. uncommon single tokens)")
    parser.add_argument("input_csv", nargs="?", default="pepperdineCO2029.csv", help="Input CSV path")
    parser.add_argument("--output", "-o", default="real_names.csv", help="Output CSV path")
    args = parser.parse_args()

    seen: Set[str] = set()
    output: List[Tuple[str]] = []

    for raw_name in read_rows(args.input_csv):
        clean = normalize_name(raw_name)
        candidate = is_likely_real_name(clean)
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append((candidate,))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["full_name"])  # single column
        for (full,) in output:
            writer.writerow([full])

    print(f"Wrote {len(output)} names to {args.output}")


if __name__ == "__main__":
    main()
