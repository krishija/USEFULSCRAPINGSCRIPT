#!/usr/bin/env python3
import argparse
import csv
from typing import List


def main():
    parser = argparse.ArgumentParser(description="Add a 'company name' column to a CSV, filled with a fixed value")
    parser.add_argument("--input", "-i", default="real_names_llm.csv", help="Input CSV path")
    parser.add_argument("--output", "-o", default="real_names_llm_with_company.csv", help="Output CSV path")
    parser.add_argument("--column", default="company name", help="Column name to add")
    parser.add_argument("--value", default="Pepperdine", help="Value to fill in the added column")
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        input_fieldnames: List[str] = reader.fieldnames or []
        # Ensure we include the added column once, at the end
        fieldnames = input_fieldnames.copy()
        if args.column not in fieldnames:
            fieldnames.append(args.column)

        with open(args.output, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                row[args.column] = args.value
                writer.writerow(row)

    print(f"Wrote {args.output} with column '{args.column}' set to '{args.value}'")


if __name__ == "__main__":
    main()
