# -*- coding: utf-8 -*-
"""
相似商品预计算：基于 train.csv 中候选商品在同一订单（InvoiceNo）内的共现频率。
相似度 = 共现次数 / min(商品A出现订单数, 商品B出现订单数)（类 Jaccard 归一化）。
输出 data/item_similar.csv：item_id, similar_id, score
"""
import csv, os, json, collections

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRAIN = os.path.join(DATA, "train.csv")
CANDIDATES = os.path.join(DATA, "demo_candidates.json")
OUT = os.path.join(DATA, "item_similar.csv")

with open(CANDIDATES, encoding="utf-8") as f:
    candidates = [c["id"] for c in json.load(f)]
cand_set = set(candidates)

appear = collections.Counter()          # 商品 -> 出现订单数
co = collections.defaultdict(collections.Counter)  # (a,b) -> 共现订单数

with open(TRAIN, encoding="utf-8-sig", newline="") as f:
    rd = csv.DictReader(f)
    inv_items = collections.defaultdict(set)
    for r in rd:
        code = r["StockCode"].strip()
        if code in cand_set:
            inv_items[r["InvoiceNo"].strip()].add(code)

for items in inv_items.values():
    for it in items:
        appear[it] += 1
    items_l = list(items)
    for i in range(len(items_l)):
        for j in range(i + 1, len(items_l)):
            a, b = items_l[i], items_l[j]
            co[a][b] += 1
            co[b][a] += 1

rows = []
for a in candidates:
    sims = []
    for b, cnt in co[a].items():
        s = cnt / max(1, min(appear[a], appear[b]))
        sims.append((b, round(s, 4)))
    sims.sort(key=lambda x: -x[1])
    for b, s in sims[:5]:
        rows.append((a, b, s))

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["item_id", "similar_id", "score"])
    w.writerows(rows)

print("similar pairs:", len(rows), "->", OUT)
for a in candidates[:6]:
    sims = [(b, s) for (x, b, s) in rows if x == a][:3]
    print(a, sims)
