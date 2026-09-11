# -*- coding: utf-8 -*-
"""
expand_candidates.py —— 扩展演示候选集：3 个演示账号 Top50 并集
- 输入：data/user_recs_clean.csv（已含中文名/类别/价格）
- 输出：data/demo_candidates.json（id/file/cn/en/cat/price）
- 已有图片 p01~p24 复用旧映射，新商品从 p25 起分配
"""
import csv, os, json, collections

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RECS = os.path.join(DATA, "user_recs_clean.csv")
OLD = os.path.join(DATA, "demo_candidates.json")
OUT = os.path.join(DATA, "demo_candidates.json")

DEMOS = ["14911", "17841", "14606"]
TOP_N = 50

# 旧 id -> 图片
old_map = {}
if os.path.exists(OLD):
    for c in json.load(open(OLD, encoding="utf-8")):
        old_map[c["id"]] = c["file"]

# 读取 3 个用户的 Top50
user_items = collections.defaultdict(list)
with open(RECS, encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        if r["user_id"] in DEMOS and len(user_items[r["user_id"]]) < TOP_N:
            user_items[r["user_id"]].append(r)

# 并集去重（保序：按用户出现顺序）
seen = set()
ordered = []
for uid in DEMOS:
    for r in user_items[uid]:
        if r["item_id"] not in seen:
            seen.add(r["item_id"])
            ordered.append(r)

# 分配图片
cands = []
next_no = 25
for r in ordered:
    fid = old_map.get(r["item_id"])
    if not fid:
        fid = "p%02d.jpg" % next_no
        next_no += 1
    cands.append({
        "id": r["item_id"],
        "file": fid,
        "cn": r["Chinese_Description"] or r["Description"],
        "en": r["Description"],
        "cat": r["Product_Category"] or "未分类",
        "price": r["price"],
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(cands, f, ensure_ascii=False, indent=1)

print("candidates:", len(cands), "->", OUT)
print("per user Top%d: %s" % (TOP_N, {u: len(user_items[u]) for u in DEMOS}))
print("new images needed: p%02d ~ p%02d" % (25, next_no - 1))
