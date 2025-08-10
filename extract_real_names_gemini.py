#!/usr/bin/env python3
import argparse
import csv
import os
import re
from typing import Iterable, List, Optional

from dotenv import load_dotenv, find_dotenv
import google.generativeai as genai
from unidecode import unidecode


def read_names(path: str) -> List[str]:
    names: List[str] = []
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
            raw = (row.get(name_key, "") or "").strip()
            if raw:
                names.append(raw)
    return names


def chunk(lst: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


SYSTEM_RULES = (
    "Task: From a list of Instagram display names, keep only those that look like real person names.\n"
    "Keep only:\n"
    "- Two-part names that look like First Last (alphabetic words).\n"
    "- Three-part where middle is an initial/very short (return as First Last).\n"
    "- Single-token names ONLY if they look like a plausible legal given name or surname and not a common nickname or ultra-common given name.\n"
    "Discard names with emojis, brands/teams/phrases, or mostly non-letters.\n"
    "Return: a JSON array (and nothing else) of kept names as plain strings (no objects)."
)

EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U0001F900-\U0001F9FF\U0001FA70-\U0001FAFF]",
    flags=re.UNICODE,
)


def normalize_display_name(name: str) -> str:
    s = unidecode(name or "").strip()
    s = EMOJI_PATTERN.sub(" ", s)
    s = re.sub(r"[^A-Za-z\s\-'\.]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Title-case words; keep "Mc"/"O'" forms simple
    s = " ".join(w.capitalize() for w in s.split())
    return s


def extract_string_from_item(item) -> Optional[str]:
    if isinstance(item, str):
        return normalize_display_name(item)
    if isinstance(item, dict):
        # Prefer 'name' key; else first string value
        if isinstance(item.get("name"), str):
            return normalize_display_name(item["name"]) 
        for v in item.values():
            if isinstance(v, str) and v.strip():
                return normalize_display_name(v)
        return None
    return None


def parse_json_array_to_strings(text: str) -> List[str]:
    import json
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            out: List[str] = []
            for it in arr:
                s = extract_string_from_item(it)
                if s:
                    out.append(s)
            return out
    except Exception:
        pass
    # Strip code fences and try to locate first JSON array
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            arr = json.loads(cleaned[start : end + 1])
            if isinstance(arr, list):
                out: List[str] = []
                for it in arr:
                    s = extract_string_from_item(it)
                    if s:
                        out.append(s)
                return out
        except Exception:
            pass
    # Fallback: each non-empty line
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    return [normalize_display_name(ln) for ln in lines]


def classify_names_gemini(names: List[str], model_name: str = "gemini-1.5-flash") -> List[str]:
    inputs = [unidecode(n) for n in names]
    prompt = (
        SYSTEM_RULES + "\nInput (JSON array):\n" + str(inputs)
    )
    model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
    resp = model.generate_content(prompt)
    text = resp.text or "[]"
    kept = parse_json_array_to_strings(text)
    # Deduplicate within batch while preserving order
    seen = set()
    out: List[str] = []
    for k in kept:
        key = k.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(k)
    return out


def main():
    parser = argparse.ArgumentParser(description="Extract likely real names using Google Gemini")
    parser.add_argument("input_csv", nargs="?", default="pepperdineCO2029.csv", help="Input CSV path")
    parser.add_argument("--output", "-o", default="real_names_llm.csv", help="Output CSV path")
    parser.add_argument("--batch", type=int, default=60, help="Batch size for LLM calls")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Gemini model name")
    parser.add_argument("--env", dest="env_path", default=None, help="Path to a .env file containing GEMINI_API_KEY")
    parser.add_argument("--api-key", dest="api_key", default=None, help="Explicit Gemini API key (overrides env)")
    args = parser.parse_args()

    if args.env_path and os.path.exists(args.env_path):
        load_dotenv(dotenv_path=args.env_path, override=True)
    else:
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path=dotenv_path, override=True)
        else:
            load_dotenv()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set (use --api-key or create .env with GEMINI_API_KEY=<key>)")
    genai.configure(api_key=api_key)

    all_names = read_names(args.input_csv)

    kept_total: List[str] = []
    seen = set()

    for batch_names in chunk(all_names, args.batch):
        outputs = classify_names_gemini(batch_names, model_name=args.model)
        for out in outputs:
            key = out.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            kept_total.append(out)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["full_name"])  # single column
        for nm in kept_total:
            writer.writerow([nm])

    print(f"Wrote {len(kept_total)} names to {args.output}")


if __name__ == "__main__":
    main()
