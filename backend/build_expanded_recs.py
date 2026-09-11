# -*- coding: utf-8 -*-
"""
build_expanded_recs.py —— 已购过滤 + Item-CF 候选扩展（解决"猜你喜欢推的都是买过的"）

思路：
  1. 种子：每个用户在 user_recs_clean.csv 里的 Top50 已购商品（RFM 式打分降序）；
  2. 扩展：对每个种子 s，查 item_similar_full.csv 取其相似商品 j，
     候选分 = Σ sim(s, j) × (种子分 / 最高种子分)   —— 分数越高的种子话语权越大；
  3. 过滤：剔除该用户在 train.csv 中购买过的【全部】商品（不止 Top50），
     保证输出候选全是"没买过但可能喜欢"的商品；
  4. 只保留商品目录(products_full.csv)内有名称的商品，保证前端可展示。

输入:
  data/user_recs_clean.csv     每用户 Top50 已购种子（clean.py 产物）
  data/train.csv               完整购买历史（用于全量已购过滤）
  data/item_similar_full.csv   全量 ItemCF 相似度（build_itemcf.py 产物）
  data/products_full.csv       全量商品目录（名称/类目/价格）
输出:
  data/user_recs_expanded.csv  user_id, rank, item_id, score, seed_cnt, seed_code, en_name, cn_name, category, price
                               （seed_code = 贡献最大的种子商品，在线层生成"因为你买过 ×××"推荐理由）
  data/user_purchased.csv      user_id, item_id（全量已购表，供在线召回层统一过滤已购）
"""
import csv, os, collections

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
SEEDS = os.path.join(DATA, "user_recs_clean.csv")
TRAIN = os.path.join(DATA, "train.csv")
SIM = os.path.join(DATA, "item_similar_full.csv")
CATALOG = os.path.join(DATA, "products_full.csv")
OUT = os.path.join(DATA, "user_recs_expanded.csv")

TOP_EXPAND = 40      # 每用户扩展出的未购候选数量
SEED_LIMIT = 50      # 参与扩展的种子数（与 clean.py Top50 对齐）
MIN_SCORE = 1e-4     # 候选分门槛（过低说明只被冷门种子带出来）


def is_product_code(code: str) -> bool:
    return code[:1].isdigit() and len(code) <= 12


def main() -> None:
    # 1. 种子（已购 Top50 + 打分）
    seeds: dict[str, list] = collections.defaultdict(list)
    with open(SEEDS, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            seeds[r["user_id"]].append((r["item_id"].strip(), float(r["score"])))
    for uid in seeds:
        seeds[uid] = sorted(seeds[uid], key=lambda x: -x[1])[:SEED_LIMIT]
    print("users with seeds:", len(seeds))

    # 2. 全量已购集合（一次扫描 train.csv；剔脏口径与 clean.py 一致）
    purchased: dict[str, set] = collections.defaultdict(set)
    with open(TRAIN, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cust = (r["CustomerID"] or "").strip()
            code = (r["StockCode"] or "").strip()
            if cust and is_product_code(code):
                purchased[cust].add(code)

    # 3. 相似度表 + 目录
    sim: dict[str, list] = collections.defaultdict(list)
    with open(SIM, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            sim[r["item_id"]].append((r["similar_id"], float(r["score"])))
    catalog = {}
    with open(CATALOG, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            catalog[r["code"].strip()] = r

    # 4. 逐用户扩展
    rows = []
    users_done = 0
    for uid, seed_list in seeds.items():
        bought = purchased.get(uid, set())
        top_score = seed_list[0][1] or 1.0
        cand: collections.Counter = collections.Counter()   # item -> 扩展分
        seed_hit: collections.Counter = collections.Counter()  # item -> 命中种子数
        top_seed: dict[str, tuple] = {}                     # item -> (贡献分, 种子code)，取贡献最大者
        for s_code, s_score in seed_list:
            w = s_score / top_score
            for j, s in sim.get(s_code, ()):
                if j in bought or j == s_code:
                    continue
                contrib = s * w
                cand[j] += contrib
                seed_hit[j] += 1
                if j not in top_seed or contrib > top_seed[j][0]:
                    top_seed[j] = (contrib, s_code)
        ranked = [(c, sc) for c, sc in cand.items()
                  if sc >= MIN_SCORE and c in catalog]
        ranked.sort(key=lambda x: -x[1])
        info = catalog.get  # 局部变量提速
        rank = 0
        for c, sc in ranked:
            p = info(c)
            if not (p["cn_name"] or p["en_name"]):
                continue  # 无名商品不参与
            rank += 1
            rows.append([uid, rank, c, round(sc, 4), seed_hit[c], top_seed[c][1],
                         p["en_name"], p["cn_name"], p["category"], p["price"]])
            if rank >= TOP_EXPAND:
                break
        users_done += 1
        if users_done % 1000 == 0:
            print("  expanded", users_done, "users...")

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "rank", "item_id", "score", "seed_cnt", "seed_code",
                    "Description", "Chinese_Description", "Product_Category", "price"])
        w.writerows(rows)

    # 全量已购表（在线召回层用它把已购商品从整个候选池里滤掉，含热门兜底层）
    with open(os.path.join(DATA, "user_purchased.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "item_id"])
        for uid, items in purchased.items():
            for c in items:
                w.writerow([uid, c])

    print("expanded rows:", len(rows), "for", users_done, "users ->", OUT)
    avg = len(rows) / max(1, users_done)
    print("avg candidates/user: %.1f" % avg)
    # 抽样演示账号
    for uid in ("14911", "17841", "14606"):
        demo = [r for r in rows if r[0] == uid][:5]
        print("demo", uid, "->", [(r[2], r[3], r[6][:18]) for r in demo])


if __name__ == "__main__":
    main()
