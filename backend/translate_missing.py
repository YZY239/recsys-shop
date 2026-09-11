# -*- coding: utf-8 -*-
"""
translate_missing.py —— 补齐 672 个缺失中文商品名的翻译
数据源：UCI Online Retail（英文原始描述），清洗时部分商品漏翻中文，
前端 cn_name 为空时回退显示 en_name，导致出现英文商品名。
本脚本：
  1. 更新 data/products_full.csv 的 cn_name
  2. 同步更新 SQLite recsys.db 的 products 表
  3. 同步更新 user_recs_expanded.csv / user_recs_clean.csv 的中文列
"""
import csv, json, os, sqlite3, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

from translations import T as TRANS

def main():
    # 1) products_full.csv
    pf_path = os.path.join(DATA, "products_full.csv")
    rows = list(csv.DictReader(open(pf_path, encoding="utf-8-sig")))
    fixed, missing = 0, []
    for r in rows:
        if not r["cn_name"].strip():
            cn = TRANS.get(r["code"])
            if cn:
                r["cn_name"] = cn
                fixed += 1
            else:
                missing.append(r["code"])
    with open(pf_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print(f"[products_full.csv] fixed {fixed}, still missing {len(missing)}")

    # 2) recsys.db products 表
    db_path = os.path.join(DATA, "recsys.db")
    n_db = 0
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        for code, cn in TRANS.items():
            # 注意：历史数据里 cn_name 可能被回退写成英文名（非空），需一并修正
            cur = conn.execute(
                "UPDATE products SET cn_name=? WHERE code=? AND (cn_name='' OR cn_name IS NULL OR cn_name=en_name)",
                (cn, code))
            n_db += cur.rowcount
        conn.commit()
        left = conn.execute(
            "SELECT COUNT(*) FROM products WHERE cn_name='' OR cn_name IS NULL").fetchone()[0]
        conn.close()
        print(f"[recsys.db] updated {n_db}, products still without cn_name: {left}")

    # 3) 推荐结果文件中的中文列
    for name in ("user_recs_expanded.csv", "user_recs_clean.csv"):
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            continue
        recs = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        n = 0
        for r in recs:
            if not r.get("Chinese_Description", "").strip():
                cn = TRANS.get(r["item_id"])
                if cn:
                    r["Chinese_Description"] = cn
                    n += 1
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=recs[0].keys())
            w.writeheader(); w.writerows(recs)
        print(f"[{name}] fixed {n}")

    # 4) demo_candidates.json
    cand_path = os.path.join(DATA, "demo_candidates.json")
    if os.path.exists(cand_path):
        cands = json.load(open(cand_path, encoding="utf-8"))
        n = 0
        for c in cands:
            if not c.get("cn"):
                cn = TRANS.get(c["id"])
                if cn:
                    c["cn"] = cn
                    n += 1
        json.dump(cands, open(cand_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[demo_candidates.json] fixed {n}")

    if missing:
        print("STILL MISSING:", missing[:20], "...")
        sys.exit(1)
    print("ALL DONE")

if __name__ == "__main__":
    main()
