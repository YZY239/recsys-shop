# -*- coding: utf-8 -*-
"""
build_itemcf.py —— 全量商品 Item-CF 相似度预计算（供候选扩展 / 相似商品使用）

与 build_similar.py（仅演示候选 24 商品、订单内共现、Overlap 系数）的区别：
  1. 覆盖全量商品（3,542+），而非演示候选小圈子；
  2. 以"同一客户购买过的商品集合"为单位统计共现（客户级），泛化能力优于单订单共现；
  3. 归一化用余弦形式：sim = co(i,j) / sqrt(n_i * n_j)，缓解热门商品相似度虚高。

输入:
  data/train.csv           原始交易数据
  data/products_full.csv   全量商品目录（限制输出只含目录内商品）
输出:
  data/item_similar_full.csv   item_id, similar_id, score（每商品 Top K=20）
"""
import csv, os, math, collections

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRAIN = os.path.join(DATA, "train.csv")
CATALOG = os.path.join(DATA, "products_full.csv")
OUT = os.path.join(DATA, "item_similar_full.csv")

TOP_K = 20          # 每商品保留的相似商品数
BASKET_CAP = 120    # 单客户商品数上限（超出截断，防止机构大单撑爆内存/噪声）


def is_product_code(code: str) -> bool:
    """商品码必须以数字开头（排除 C2 / M / POST 等非商品特殊码）"""
    return code[:1].isdigit() and len(code) <= 12


def main() -> None:
    # 目录内商品（两边都需在目录内才输出，保证下游可查到商品详情）
    catalog = set()
    with open(CATALOG, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            catalog.add(r["code"].strip())
    print("catalog items:", len(catalog))

    # 客户 -> 购买商品集合（截断）
    baskets: dict[str, set] = collections.defaultdict(set)
    with open(TRAIN, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cust = (r["CustomerID"] or "").strip()
            code = (r["StockCode"] or "").strip()
            if not cust or not is_product_code(code):
                continue
            b = baskets[cust]
            if len(b) >= BASKET_CAP and code not in b:
                continue
            b.add(code)
    print("customers:", len(baskets))

    # 客户级共现：co[i][j] = 同时购买 i 和 j 的客户数
    appear: collections.Counter = collections.Counter()   # 商品 -> 购买客户数
    co: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for items in baskets.values():
        items = {c for c in items if c in catalog}  # 只统计目录内商品
        for c in items:
            appear[c] += 1
        items_l = list(items)
        for a in range(len(items_l)):
            ca = co[items_l[a]]
            for b in range(a + 1, len(items_l)):
                ca[items_l[b]] += 1
                co[items_l[b]][items_l[a]] += 1

    # 余弦归一化 + 每商品 Top K
    rows = []
    for a, sims in co.items():
        na = appear[a]
        best = []
        for b, cnt in sims.items():
            s = cnt / math.sqrt(na * appear[b])
            best.append((b, round(s, 4)))
        best.sort(key=lambda x: -x[1])
        for b, s in best[:TOP_K]:
            rows.append((a, b, s))

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "similar_id", "score"])
        w.writerows(rows)

    print("similar pairs:", len(rows), "->", OUT)
    print("covered items:", len({r[0] for r in rows}), "/", len(catalog))
    # 抽样展示
    sample = [r[0] for r in rows[:1]][:1]
    for a in sample:
        sims = [(b, s) for (x, b, s) in rows if x == a][:5]
        print("sample", a, sims)


if __name__ == "__main__":
    main()
