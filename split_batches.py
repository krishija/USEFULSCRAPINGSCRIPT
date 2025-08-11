#!/usr/bin/env python3
import csv
from pathlib import Path

in_path = Path('colgate/permuted_colgate_all.csv')
rows = list(csv.DictReader(in_path.open()))
people = {}
for r in rows:
    people.setdefault(r['full_name'], []).append(r)
full_names = list(people.keys())

batches = [[] for _ in range(11)]
for idx, name in enumerate(full_names):
    batches[idx % 11].extend(people[name])

for i, batch in enumerate(batches):
    out = Path(f'colgate/colgate_batch_{i:02d}.csv')
    with out.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['full_name','username','email'])
        w.writeheader()
        w.writerows(batch)
    print(out, len(batch))
