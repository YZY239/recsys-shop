# -*- coding: utf-8 -*-
"""
test_no_duplicates.py —— 推荐流零重复回归测试（可直接运行）

验证三个检测点：
  ① 候选池内 code 与展示名均唯一（防"同名不同码"商品重复出现）
  ② 整条推荐流连续下滑（含轮转轮次）不出现重复商品
  ③ 实时插入候选（similar_items / behaviors 同口径）不与已展示重复

运行：
    python test_no_duplicates.py
退出码 0 = 全部通过；1 = 存在重复（可用于 CI / 答辩演示）
"""
import sys

import db
import recommend


def norm_name(p):
    """商品展示名归一（与前端 nameOf 口径一致）"""
    return ((p.get("cn_name") or p.get("en_name")) or "").strip().lower()


def test_pool_unique(customer_id):
    """检测点①：候选池 code + 名称 双重唯一"""
    pool = recommend._pool_for(customer_id)
    codes = [p["code"] for p in pool]
    names = [norm_name(p) for p in pool]
    ok = len(set(codes)) == len(pool) and len(set(names)) == len(pool)
    print("[检测点①] 候选池唯一性: 池=%d 唯一code=%d 唯一名=%d -> %s"
          % (len(pool), len(set(codes)), len(set(names)), "PASS" if ok else "FAIL"))
    return ok


def test_stream_unique(customer_id, max_pages=30, page_size=8):
    """检测点②：整条推荐流（含轮转轮次）零重复（模拟前端过滤后的最终渲染口径）"""
    db.reset_sessions()
    seen_codes, seen_names, dups = set(), set(), []
    rendered = 0
    for page in range(1, max_pages + 1):
        r = recommend.get_paged_recs(customer_id, page, page_size)
        if not r["list"]:
            break
        new_cnt = 0
        for it in r["list"]:
            nm = norm_name(it)
            if it["code"] in seen_codes or nm in seen_names:
                dups.append((page, it["code"], nm[:24]))
            else:
                seen_codes.add(it["code"])
                seen_names.add(nm)
                new_cnt += 1
            rendered += 1
        # 前端口径：一页拉回全是已见商品 → 过滤后 0 新增 → 终止加载
        if new_cnt == 0:
            break
    db.reset_sessions()
    ok = not dups
    print("[检测点②] 整流唯一性: 返回 %d 张卡片, 唯一商品 %d 个, 重复 %d 次 -> %s"
          % (rendered, len(seen_codes), len(dups), "PASS" if ok else "FAIL"))
    if dups:
        print("   重复明细(前5):", dups[:5])
    return ok


def test_insert_unique(customer_id):
    """检测点③：实时插入候选不与已展示商品重复（code + 名称）"""
    db.reset_sessions()
    r1 = recommend.get_paged_recs(customer_id, 1, 8)
    shown = recommend.shown_codes(customer_id)
    shown_names = {norm_name(db.product_by_code(c) or {}) for c in shown}
    code0 = r1["list"][0]["code"]
    dups = []
    for s in recommend.similar_items(code0, 12):
        nm = norm_name(s)
        if s["code"] in shown or (nm and nm in shown_names):
            dups.append((s["code"], nm[:24]))
    db.reset_sessions()
    ok = not dups
    print("[检测点③] 插入候选唯一性: %s -> %s"
          % ("无重复" if ok else "重复:%s" % dups[:5], "PASS" if ok else "FAIL"))
    return ok


def main():
    db.init_db()
    users = ["14911", "17841", "14606"]  # alice / bob / carol
    all_ok = True
    for uid in users:
        u = db.user_by_customer(uid)
        print("\n===== 用户 %s(%s) =====" % (u["nickname"] if u else "?", uid))
        for fn in (test_pool_unique, test_stream_unique, test_insert_unique):
            all_ok = fn(uid) and all_ok
    print("\n结论:", "全部通过 ✅" if all_ok else "存在重复 ❌")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
