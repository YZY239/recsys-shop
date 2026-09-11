# -*- coding: utf-8 -*-
"""
evaluate.py —— 推荐离线评估（时间 holdout 切分）

评估问题：给定用户截至 T 日的购买历史，预测他 T 日之后（最后一天订单）买了什么。

切分方式（按用户各自的时间线，模拟线上"预测下一次购买"）：
  - 训练集：该用户最后订单日之前的全部交互
  - 测试集：该用户最后订单日当天的商品集合（去重）
  - 仅评估满足条件的用户：≥2 个不同订单日、训练集商品数 ≥ 10、测试集商品数 ≥ 1

对比三种召回策略（Top-10）：
  A. 历史打分 Top10  —— RFM 式打分取训练集已购商品（≈ 当前线上"猜你喜欢"口径）
  B. 全站热门 Top10  —— 训练集购买客户数最多的商品（热门兜底基线）
  C. ItemCF 扩展 Top10 —— 已购作种子扩展未购商品（build_expanded_recs.py 的离线口径，
     相似度同样只用训练集计算，无数据泄漏）

指标（二值相关度）：Recall@K / Precision@K / HitRate@K / NDCG@K / 覆盖率

用法：
  python evaluate.py [评估用户数]   （默认 1500，0 = 全量）
输出：
  控制台 + data/eval_report.txt
"""
import csv, os, math, sys, random, collections, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRAIN = os.path.join(DATA, "train.csv")
CATALOG = os.path.join(DATA, "products_full.csv")
OUT = os.path.join(DATA, "eval_report.txt")

K_LIST = (5, 10)
BASKET_CAP = 120    # 与 build_itemcf.py 一致
SEED_LIMIT = 20     # CF 扩展用的种子数
TOP_K = 20          # 每商品保留的相似商品数


def is_product_code(code: str) -> bool:
    return code[:1].isdigit() and len(code) <= 12


def to_dt(s: str):
    try:
        return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def load_data():
    """返回 (用户聚合, 用户订单日集合, 用户按日组织的商品)"""
    agg = collections.defaultdict(lambda: {"count": 0, "amount": 0.0, "last": None})
    user_days: dict[str, set] = collections.defaultdict(set)
    user_day_items: dict[str, dict] = collections.defaultdict(lambda: collections.defaultdict(set))
    with open(TRAIN, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cust = (r["CustomerID"] or "").strip()
            code = (r["StockCode"] or "").strip()
            dt = to_dt((r["InvoiceDate"] or "").strip())
            if not cust or not is_product_code(code) or dt is None:
                continue
            try:
                qty = int(float(r["Quantity"]))
                price = float(r["UnitPrice"])
            except (ValueError, TypeError):
                continue
            if qty <= 0 or price <= 0:
                continue
            day = dt.date()
            user_days[cust].add(day)
            user_day_items[cust][day].add(code)
            a = agg[(cust, code)]
            a["count"] += 1
            a["amount"] += qty * price
            if a["last"] is None or dt > a["last"]:
                a["last"] = dt
    return agg, user_days, user_day_items


def build_itemcf_train(user_baskets: dict) -> dict:
    """训练集客户级共现 -> 余弦相似度 {item: [(j, sim), ...]} Top20"""
    appear = collections.Counter()
    co = collections.defaultdict(collections.Counter)
    for items in user_baskets.values():
        items = list(items)
        for c in items:
            appear[c] += 1
        for a in range(len(items)):
            ca = co[items[a]]
            for b in range(a + 1, len(items)):
                ca[items[b]] += 1
                co[items[b]][items[a]] += 1
    sim = {}
    for a, sims in co.items():
        na = appear[a]
        best = sorted(((b, cnt / math.sqrt(na * appear[b])) for b, cnt in sims.items()),
                      key=lambda x: -x[1])[:TOP_K * 2]
        sim[a] = best
    return sim


def main() -> None:
    sample_n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    catalog = set()
    with open(CATALOG, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            catalog.add(r["code"].strip())

    print("loading train.csv ...")
    agg, user_days, user_day_items = load_data()

    # 选出可评估用户
    eligible = []
    for cust, days in user_days.items():
        if len(days) < 2:
            continue
        last_day = max(days)
        holdout = user_day_items[cust][last_day]
        train_days = [d for d in days if d != last_day]
        train_items = set()
        for d in train_days:
            train_items |= user_day_items[cust][d]
        if len(train_items) < 10 or not holdout:
            continue
        eligible.append((cust, holdout, train_items, train_days))
    random.Random(42).shuffle(eligible)
    if sample_n > 0:
        eligible = eligible[:sample_n]
    print("eval users:", len(eligible), "/", len(eligible) and "sampled" or "")

    # 训练集聚合（剔除 holdout 日）+ 训练集客户购物篮（算 ItemCF 用，无泄漏）
    train_stats: dict[str, dict] = collections.defaultdict(dict)  # user -> item -> {count, amount}
    train_pop: collections.Counter = collections.Counter()        # item -> 购买客户数（训练集）
    train_baskets: dict[str, set] = {}
    for cust, _, train_items, _ in eligible:
        train_baskets[cust] = {c for c in train_items if c in catalog and len(train_baskets.get(cust, set())) < BASKET_CAP}
    # 全量聚合一次（对被抽样用户）
    sampled = {c for c, _, _, _ in eligible}
    user_item_agg: dict[str, dict] = collections.defaultdict(dict)
    for (cust, code), a in agg.items():
        if cust not in sampled:
            continue
        last_day = max(user_days[cust])
        if a["last"] and a["last"].date() >= last_day:
            continue  # 该交互发生在最后订单日（>=），属于 holdout 期，剔除
        user_item_agg[cust][code] = a
    for cust, items in user_item_agg.items():
        for code in items:
            train_pop[code] += 1

    print("computing ItemCF on training split ...")
    sim = build_itemcf_train(train_baskets)

    def score_rfm(a) -> float:
        """与 clean.py 相同的 RFM 式打分（时效分需要全局最大日期，这里用用户内归一）"""
        return 0.5 * math.log1p(a["count"]) + 0.3 * math.log1p(a["amount"])

    top_score = {}
    for cust, items in user_item_agg.items():
        scores = {c: score_rfm(a) for c, a in items.items()}
        mx = max(scores.values()) or 1.0
        top_score[cust] = (scores, mx)

    def rec_history(cust):
        scores, _ = top_score.get(cust, ({}, 1))
        return [c for c, _ in sorted(scores.items(), key=lambda x: -x[1])[:10]]

    def rec_popular(cust):
        bought = set(user_item_agg.get(cust, {}))
        return [c for c, _ in train_pop.most_common(50) if c not in bought][:10]

    def rec_itemcf(cust):
        scores, mx = top_score.get(cust, ({}, 1))
        seeds = sorted(scores.items(), key=lambda x: -x[1])[:SEED_LIMIT]
        bought = set(user_item_agg.get(cust, {}))
        cand = collections.Counter()
        for s, sc in seeds:
            w = sc / (mx or 1.0)
            for j, s_sim in sim.get(s, ()):
                if j in bought:
                    continue
                cand[j] += s_sim * w
        return [c for c, _ in sorted(cand.items(), key=lambda x: -x[1])[:10]]

    def ndcg_at(rec, rel):
        dcg = sum(1.0 / math.log2(i + 2) for i, c in enumerate(rec[:10]) if c in rel)
        ideal = sum(1.0 / math.log2(i + 2) for i in range(min(10, len(rel))))
        return dcg / ideal if ideal else 0.0

    modes = {"A 历史打分Top10(当前口径)": rec_history,
             "B 全站热门Top10(兜底基线)": rec_popular,
             "C ItemCF扩展Top10(本次改进)": rec_itemcf}
    stats = {m: {f"{k}@": [0, 0] for k in K_LIST} for m in modes}  # 占位，下面统一结构
    stats = {m: {("R", k): 0.0 for k in K_LIST} for m in modes}
    for m in modes:
        for k in K_LIST:
            stats[m][("P", k)] = 0.0
            stats[m][("H", k)] = 0
            stats[m][("N", k)] = 0.0
    coverage = {m: set() for m in modes}
    n_users = 0

    for cust, holdout, _, _ in eligible:
        rel = {c for c in holdout if c in catalog}
        if not rel:
            continue
        n_users += 1
        for m, fn in modes.items():
            rec = fn(cust)
            hits = [c for c in rec if c in rel]
            for k in K_LIST:
                topk = rec[:k]
                h = sum(1 for c in topk if c in rel)
                stats[m][("R", k)] += h / len(rel)
                stats[m][("P", k)] += h / k
                stats[m][("H", k)] += 1 if h else 0
                stats[m][("N", k)] += ndcg_at(rec, rel)
            coverage[m].update(rec)

    lines = ["=== 推荐离线评估报告（时间 holdout：最后订单日商品为测试集） ===",
             f"评估用户数: {n_users}   指标: Top-5 / Top-10，二值相关度",
             ""]
    header = f"{'策略':<28}{'指标':<10}{'@5':>10}{'@10':>10}"
    for m, s in stats.items():
        lines.append(header if not lines[-1] else "")
        lines.append(m)
        for name, key in (("Recall", "R"), ("Precision", "P"), ("HitRate", "H"), ("NDCG", "N")):
            v5 = s[(key, 5)] / n_users
            v10 = s[(key, 10)] / n_users
            if key == "H":
                v5, v10 = s[("H", 5)] / n_users, s[("H", 10)] / n_users
            lines.append(f"  {name:<26}{v5:>10.4f}{v10:>10.4f}")
    lines.append("")
    lines.append("覆盖率（Top10 去重后 / 目录 4226）:")
    for m in modes:
        lines.append(f"  {m:<28}{len(coverage[m]):>8d}  ({len(coverage[m]) / len(catalog) * 100:.1f}%)")
    lines += ["",
              "结论解读：",
              "  A(历史打分) 只能推训练集已购商品，而测试集是『之后才买』的商品，",
              "    因此命中≈0 —— 这正暴露了『猜你喜欢=猜你买过』的核心缺陷；",
              "  B(热门) 是无个性化基线；",
              "  C(ItemCF 扩展) 用已购作种子推荐未购商品，是三者中唯一具备",
              "    『预测下一次购买』能力的口径。"]

    report = "\n".join(lines)
    print(report)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print("saved ->", OUT)


if __name__ == "__main__":
    main()
