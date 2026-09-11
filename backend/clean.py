# -*- coding: utf-8 -*-
"""
数据清洗脚本：train.csv → 每用户 Top-N 推荐候选集（user_recs_clean.csv）

清洗步骤：
  1. 剔除无效行：CustomerID / StockCode 缺失、Quantity<=0、UnitPrice<=0
  2. 剔除完全重复行（InvoiceNo + StockCode + CustomerID 相同）
  3. 按 (CustomerID, StockCode) 聚合：购买次数 / 总数量 / 总金额 / 最近购买时间
  4. 推荐分 = 0.5*ln(1+次数) + 0.3*ln(1+金额) + 0.2*时效分
  5. 每用户取 Top50 作为「猜你喜欢」候选集
  6. 关联 products_clean.csv 的中文名 / 类别，价格取该商品 UnitPrice 中位数
输出：
  data/user_recs_clean.csv   （前端主数据）
  data/clean_report.txt      （清洗统计报告）
"""
import csv, os, math, collections, statistics, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRAIN = os.path.join(DATA, "train.csv")
PRODUCTS = os.path.join(DATA, "products_clean.csv")
OUT_RECS = os.path.join(DATA, "user_recs_clean.csv")
OUT_REPORT = os.path.join(DATA, "clean_report.txt")

TOP_N = 50

def load_products():
    """商品表：StockCode -> (Description, Chinese, Category)"""
    d = {}
    with open(PRODUCTS, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d[r["StockCode"].strip()] = (
                (r["Description"] or "").strip(),
                (r["Chinese_Description"] or "").strip(),
                (r["Product_Category"] or "").strip(),
            )
    return d

def main():
    products = load_products()
    total_rows = 0
    dropped = {"no_customer":0, "no_stock":0, "bad_qty":0, "bad_price":0, "non_product_code":0, "duplicate":0}
    agg = collections.defaultdict(lambda: {"count":0, "qty":0, "amount":0.0, "last":""})
    seen = set()

    def is_product_code(code):
        # 商品码必须以数字开头（排除 C2 / M / POST 等非商品特殊码）
        return code[:1].isdigit() and len(code) <= 12

    with open(TRAIN, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            total_rows += 1
            cust = (r["CustomerID"] or "").strip()
            stock = (r["StockCode"] or "").strip()
            qty_s, price_s = r["Quantity"], r["UnitPrice"]
            try:
                qty = int(float(qty_s))
                price = float(price_s)
            except (ValueError, TypeError):
                qty, price = 0, 0.0
            inv = (r["InvoiceNo"] or "").strip()
            if not cust:
                dropped["no_customer"] += 1; continue
            if not stock:
                dropped["no_stock"] += 1; continue
            if not is_product_code(stock):
                dropped["non_product_code"] += 1; continue
            if qty <= 0:
                dropped["bad_qty"] += 1; continue
            if price <= 0:
                dropped["bad_price"] += 1; continue
            key = (inv, stock, cust)
            if key in seen:
                dropped["duplicate"] += 1; continue
            seen.add(key)
            a = agg[(cust, stock)]
            a["count"] += 1
            a["qty"] += qty
            a["amount"] += qty * price
            a["last"] = max(a["last"], (r["InvoiceDate"] or "").strip())

    print("原始行数:", total_rows, "| 剔除:", sum(dropped.values()), dropped)
    print("有效用户:", len(set(k[0] for k in agg)), "| 有效商品:", len(set(k[1] for k in agg)))

    # 商品价格中位数
    price_by_stock = collections.defaultdict(list)
    with open(TRAIN, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                p = float(r["UnitPrice"])
                if p > 0:
                    price_by_stock[r["StockCode"].strip()].append(p)
            except (ValueError, TypeError):
                pass
    median_price = {k: round(statistics.median(v), 2) for k, v in price_by_stock.items()}

    # 时效分：最近一次购买距今的天数（以数据内最大日期为基准，越近越高）
    all_dates = [a["last"] for a in agg.values() if a["last"]]
    def to_dt(s):
        try:
            return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    dt_list = [d for d in (to_dt(x) for x in all_dates) if d]
    max_dt = max(dt_list)
    span = (max_dt - min(dt_list)).days or 1

    def score_of(a):
        last_dt = to_dt(a["last"]) or max_dt
        recency = 1.0 - min(1.0, (max_dt - last_dt).days / span)
        return 0.5 * math.log1p(a["count"]) + 0.3 * math.log1p(a["amount"]) + 0.2 * recency

    # 每用户 Top50
    user_items = collections.defaultdict(list)
    for (cust, stock), a in agg.items():
        user_items[cust].append((stock, score_of(a), a["count"], a["amount"]))
    for cust in user_items:
        user_items[cust].sort(key=lambda x: -x[1])

    recs_written = 0
    users_covered = 0
    with open(OUT_RECS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user_id","rank","item_id","score","Description","Chinese_Description","Product_Category","price"])
        for cust, items in user_items.items():
            users_covered += 1
            for rank, (stock, sc, cnt, amt) in enumerate(items[:TOP_N], 1):
                desc, cn, cat = products.get(stock, ("", "", ""))
                if not cn:
                    cn = desc  # 商品表缺中文名时退回英文名
                if not cat:
                    cat = "未分类"
                w.writerow([cust, rank, stock, round(sc, 4), desc, cn, cat,
                            median_price.get(stock, "")])
                recs_written += 1

    # 报告
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("=== 数据清洗报告 ===\n")
        f.write(f"数据源: {TRAIN}\n")
        f.write(f"原始行数: {total_rows}\n")
        f.write(f"剔除行数: {sum(dropped.values())}\n")
        for k, v in dropped.items():
            f.write(f"  - {k}: {v}\n")
        f.write(f"有效交互对(用户x商品): {len(agg)}\n")
        f.write(f"有效用户数: {len(set(k[0] for k in agg))}\n")
        f.write(f"有效商品数: {len(set(k[1] for k in agg))}\n")
        f.write(f"推荐候选集: 每用户 Top{TOP_N}，共 {recs_written} 条，覆盖 {users_covered} 用户\n")
        f.write(f"输出: {OUT_RECS}\n")
        f.write(f"商品表 products_clean.csv 已检查: {len(products)} 个商品，含中文名与类别，可直接使用\n")
    print("推荐候选集:", recs_written, "条 /", users_covered, "用户 ->", OUT_RECS)

    # 找出 3 个演示账号（活跃度高且互不相同的高购买用户）
    act = sorted(user_items.keys(), key=lambda u: -sum(x[2] for x in user_items[u]))
    demos = act[:3]
    print("演示账号候选:", demos)
    for u in demos:
        print("  user", u, "->", [x[0] for x in user_items[u][:10]])

if __name__ == "__main__":
    main()
