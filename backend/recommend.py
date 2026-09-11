# -*- coding: utf-8 -*-
"""
recommend.py —— 推荐服务（召回 → 精排 → 打散 → 分页 → 无限流）
- 召回（三档，按可用性自动降级）：
    ① ItemCF 扩展候选（user_recs_expanded.csv，build_expanded_recs.py 产物）：
       已购全部过滤、未购商品按 CF 分降序 —— "猜你喜欢"推荐的是没买过但可能喜欢的；
    ② 历史候选（user_recs_clean.csv 每用户 Top50，RFM 式打分）—— 旧口径兜底；
    ③ 热门兜底（hot_items.csv，train 销量聚合 Top200）填充至 POOL_SIZE
- 精排：tier 分层（扩展/历史候选为 tier0，热门兜底为 tier1），层内按分数降序
- 打散：相邻商品类别不连续超过 2 个
- 冷却（无限流核心）：
    · 永久冷却 —— 点击过的商品不再出现在推荐流（db.behaviors）
    · 会话冷却 —— 本次浏览已展示过的商品不重复出现
    · 轮转重排 —— 候选池滑完后自动进入下一轮（换随机种子重排 + 类目打散），
                   前端因此可以无限下滑、没有底部
- 相似商品：item_similar.csv 预计算共现相似度 + 同类别兜底
"""
import csv, os, collections, random, json

import db

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
EXP_CSV = os.path.join(DATA, "user_recs_expanded.csv")
PUR_CSV = os.path.join(DATA, "user_purchased.csv")
RECS_CSV = os.path.join(DATA, "user_recs_clean.csv")
SIM_CSV = os.path.join(DATA, "item_similar.csv")
HOT_CSV = os.path.join(DATA, "hot_items.csv")

# 候选池目标大小：真实 Top50 + 候选集内热门兜底 10 个 = 60（对应约 8 屏推荐流）
POOL_SIZE = 60

# 每用户 Top50：{customer_id: [ {code, rank, score} ]}
_USER_RECS = None
# ItemCF 扩展候选：{customer_id: [ {code, score, seed_cnt} ]}（未购商品，build_expanded_recs.py 产物）
_EXPANDED = None
# 全量已购集合：{customer_id: set(code)}（user_purchased.csv，供候选池统一过滤已购）
_PURCHASED = None
# 商品: {code: {code, score(该用户分), ...}}  —— 实际详情查 db
_SIM = None  # {code: [(sim_code, score), ...]}
_HOT = None  # [(code, score), ...] 数据集热门商品（按热度降序）
# 会话状态已迁入 SQLite（db.sessions 表）：重启不丢、多 worker 一致。
# 内存._COOL 字典弃用。


def _load_recs():
    global _USER_RECS
    if _USER_RECS is not None:
        return _USER_RECS
    d = collections.defaultdict(list)
    with open(RECS_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d[r["user_id"]].append({
                "code": r["item_id"],
                "rank": int(r["rank"]),
                "score": float(r["score"]),
            })
    for k in d:
        d[k].sort(key=lambda x: x["rank"])
    _USER_RECS = d
    return d


def _load_expanded():
    """ItemCF 扩展候选（未购商品）。文件缺失时返回空表，召回自动降级到历史口径。"""
    global _EXPANDED
    if _EXPANDED is not None:
        return _EXPANDED
    d = collections.defaultdict(list)
    if os.path.exists(EXP_CSV):
        with open(EXP_CSV, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                d[r["user_id"]].append({
                    "code": r["item_id"],
                    "score": float(r["score"]),
                    "seed_cnt": int(r["seed_cnt"]),
                    # 贡献最大的种子商品（旧版文件无此列时为空 → 在线层退化为通用理由）
                    "seed_code": (r.get("seed_code") or "").strip(),
                })
    _EXPANDED = d
    return d


def _load_purchased():
    """全量已购集合（build_expanded_recs.py 产物）。文件缺失时返回空表。"""
    global _PURCHASED
    if _PURCHASED is not None:
        return _PURCHASED
    d = collections.defaultdict(set)
    if os.path.exists(PUR_CSV):
        with open(PUR_CSV, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                d[r["user_id"]].add(r["item_id"])
    _PURCHASED = d
    return d


def _load_sim():
    global _SIM
    if _SIM is not None:
        return _SIM
    d = collections.defaultdict(list)
    with open(SIM_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d[r["item_id"]].append((r["similar_id"], float(r["score"])))
    _SIM = d
    return d


def _load_hot():
    """数据集热门商品（train 销量聚合 Top200，热度分降序）"""
    global _HOT
    if _HOT is not None:
        return _HOT
    d = []
    with open(HOT_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d.append((r["code"], float(r["score"])))
    _HOT = d
    return d


def user_recs(customer_id):
    """该用户 Top50 候选集（code 列表 + 分数）"""
    return _load_recs().get(customer_id, [])


def _diversify(items):
    """打散：同类别商品在流中不相邻（按类别间隔重排，保持分数降序的大体顺序）"""
    if len(items) <= 2:
        return items
    from db import product_by_code
    cat_seq = []
    for it in items:
        p = product_by_code(it["code"])
        cat_seq.append((p["category"] if p else "未分类", it))
    out = []
    by_cat = collections.defaultdict(list)
    for cat, it in cat_seq:
        by_cat[cat].append(it)
    # 轮询各类别队列（保持每个类别内分数序）
    order = []
    while any(by_cat.values()):
        for cat in list(by_cat.keys()):
            if by_cat[cat]:
                order.append((cat, by_cat[cat].pop(0)))
    return [it for _, it in order]


def _decorate(recs):
    """把候选集条目补全为可展示的商品信息（详情 join）"""
    from db import product_by_code
    out = []
    for r in recs:
        p = product_by_code(r["code"])
        out.append({**r, **(p or {})})
    return out


def _user_interest(customer_id):
    """演示用户兴趣标签（真实场景来自用户画像表）"""
    from db import user_by_customer
    u = user_by_customer(str(customer_id))
    if not u:
        return []
    try:
        return json.loads(u.get("interest") or "[]")
    except Exception:
        return []


def _pool_for(customer_id):
    """候选池（个性化召回 + 兴趣冷启动 + 热门兜底，三层结构）：
    第一层：ItemCF 扩展候选（user_recs_expanded.csv：已购全部过滤的未购商品，
            按 CF 分降序），附推荐理由"因为你买过 ×××"（取贡献最大的种子商品名）；
            扩展文件缺失或该用户无数据时降级为旧口径——历史 Top50 已购候选
    第二层：第一层为空（新用户/无历史）→ interest 兴趣冷启动：
            按用户画像 interest 标签匹配商品类目，类目内按热度取未购商品，
            附理由"根据你的兴趣 ×××"
    第三层：仍不足 POOL_SIZE → 全站热门兜底（热度降序填充）
    （个性化候选永远排在兜底之前；兜底只用候选集内商品，保证推荐流每张卡片都有图）
    """
    from db import list_products
    prod_by = {p["code"]: p for p in list_products()}
    bought = _load_purchased().get(str(customer_id), set())
    real, hot, seen = [], [], set()
    # 名称级去重：目录中存在"同名不同码"商品（如同一商品多个 StockCode），
    # 只按 code 去重会导致同款重复出现——按展示名（cn/en 归一小写）再兜一层
    name_seen = set()

    def _name(code):
        p = prod_by.get(code)
        return (p and (p.get("cn_name") or p.get("en_name"))) or ""

    def _nm_of(p):
        return ((p.get("cn_name") or p.get("en_name")) or "").strip().lower()

    def _dup_name(p):
        nm = _nm_of(p)
        if nm and nm in name_seen:
            return True
        if nm:
            name_seen.add(nm)
        return False

    # 第一层 A：ItemCF 扩展候选（未购商品，"猜你喜欢"的主口径，带推荐理由）
    expanded = _load_expanded().get(str(customer_id))
    if expanded:
        for r in expanded:
            p = prod_by.get(r["code"])
            if not p or not (p.get("cn_name") or p.get("en_name")):
                continue
            if _dup_name(p):
                continue
            seed_name = _name(r.get("seed_code", ""))
            reason = f"因为你买过「{seed_name}」" if seed_name else "根据你的喜好推荐"
            real.append({**p, "score": r["score"], "tier": 0, "cf": True,
                         "seed_cnt": r["seed_cnt"], "reason": reason})
            seen.add(r["code"])
            if len(real) >= POOL_SIZE:
                break
    else:
        # 第一层 B（降级）：历史已购 Top50 候选（真实精排分）
        for r in user_recs(customer_id):
            p = prod_by.get(r["code"])
            if not p or not (p.get("cn_name") or p.get("en_name")):
                continue
            if _dup_name(p):
                continue
            real.append({**p, "score": r["score"], "tier": 0, "reason": "你购买过的同类好物"})
            seen.add(r["code"])

    # 第二层：兴趣冷启动（新用户/无任何历史候选时启用，替代纯热门兜底）
    if not real:
        tags = _user_interest(customer_id)
        if tags:
            tag_set = set(tags)
            hot_map = {code: s for code, s in _load_hot()}
            cand = [
                p for p in prod_by.values()
                if p["category"] in tag_set
                and p["code"] not in bought
                and not ("placeholder" in (p.get("img") or ""))
                and (p.get("cn_name") or p.get("en_name"))
            ]
            cand.sort(key=lambda p: -hot_map.get(p["code"], 0))
            for p in cand:
                if len(real) >= POOL_SIZE:
                    break
                if _dup_name(p):
                    continue
                real.append({**p, "score": hot_map.get(p["code"], 0), "tier": 0, "cold": True,
                             "reason": "根据你的兴趣「" + "、".join(tags[:2]) + "」精选"})
                seen.add(p["code"])

    # 第三层：候选集内热门兜底（有真实图；热度分降序；仅填充，不高于真实候选层）
    if len(real) < POOL_SIZE:
        hot_map = {code: s for code, s in _load_hot()}
        cand = [
            p for p in prod_by.values()
            if p["code"] not in seen
            and p["code"] not in bought
            and not ("placeholder" in (p.get("img") or ""))
            and (p.get("cn_name") or p.get("en_name"))
        ]
        cand.sort(key=lambda p: -hot_map.get(p["code"], 0))
        for p in cand:
            if len(real) + len(hot) >= POOL_SIZE:
                break
            if _dup_name(p):
                continue
            hot.append({**p, "score": hot_map.get(p["code"], 0), "hot": True, "tier": 1})
            seen.add(p["code"])
    pool = real + hot
    pool.sort(key=lambda x: (x["tier"], -x["score"]))
    return pool


def _build_cycle_order(avail, cycle):
    """第 0 轮按精排分降序（真实推荐优先）；之后每轮换随机种子重排 + 类目打散（轮转）"""
    if cycle <= 0:
        return list(avail)
    rng = random.Random(2026 + cycle)
    items = list(avail)
    rng.shuffle(items)
    return _diversify(items)


def shown_codes(customer_id):
    """该用户本次会话已展示过的商品 code 集合（供 app.py 实时插入去重；SQLite 持久化）"""
    return set(db.get_session(str(customer_id))["shown"])


def mark_shown(customer_id, codes):
    """把实时插入的商品也记入会话已展示，避免后续重复出现"""
    st = db.get_session(str(customer_id))
    st["shown"].extend(codes)
    db.set_session(str(customer_id), st["cycle"], st["shown"])


def reset_cool():
    """清空全部会话冷却状态（TEST-ONLY：测试面板「清理测试数据」使用，删除面板时一并删除）"""
    db.reset_sessions()


def get_paged_recs(customer_id, page=1, page_size=8):
    """无限流分页：全量候选池 + 冷却（点击/曝光去重）+ 轮转重排

    - 已绕过 rec_cache 页缓存：动态流依赖会话状态，与静态页缓存不兼容
      （建表/读写函数保留，可随时换回）
    - 会话状态（cycle/shown）存于 db.sessions：请求开始读一次、结束写一次
    """
    from db import user_by_customer, clicked_codes
    u = user_by_customer(str(customer_id)) if str(customer_id).isdigit() else None
    clicked = set(clicked_codes(u["id"])) if u else set()
    pool = _pool_for(customer_id)
    avail = [it for it in pool if it["code"] not in clicked]

    st = db.get_session(str(customer_id))
    if page <= 1:
        # 首屏/下拉刷新 → 开启新一轮浏览
        st["cycle"] += 1
        st["shown"] = []

    order = _build_cycle_order(avail, st["cycle"])
    seen = set(st["shown"])   # 本轮已展示（跨页防重复）
    chunk = []
    # 从本轮 order 中取"未展示过"的商品；
    # 本轮排列滑完即返回空（前端显示"到底啦"）——会话内每个商品只出现一次，
    # 绝不自动轮转重排已看过的商品（零重复由后端保证，前端去重仅作双保险）；
    # 用户点"换一批"（page<=1）时 cycle+1 换随机种子重排，开启新一轮不重复浏览
    fresh = [it for it in order if it["code"] not in seen]
    take = fresh[:page_size]
    chunk.extend(take)
    for it in take:
        seen.add(it["code"])
        st["shown"].append(it["code"])
    remaining = any(it["code"] not in seen for it in order)

    # 请求结束：会话状态一次性写回 SQLite（重启/多 worker 不丢）
    db.set_session(customer_id, st["cycle"], st["shown"])
    return {
        "list": chunk,
        "page": page,
        "page_size": page_size,
        "total": len(avail),
        "has_more": remaining,    # 本轮排列是否还有未展示商品
        "round": st["cycle"],     # 当前轮次：0 = 首轮（不重复）；≥1 = 重排后的新一轮（也不重复）
    }


def similar_items(code, limit=4):
    """相似商品（预计算共现相似度），附商品详情与相似度；code + 展示名双重去重"""
    from db import product_by_code
    sims = _load_sim().get(code, [])
    out, used_names = [], set()
    for sim_code, score in sims:
        p = product_by_code(sim_code)
        if not p:
            continue
        nm = ((p.get("cn_name") or p.get("en_name")) or "").strip().lower()
        if nm and nm in used_names:
            continue
        if nm:
            used_names.add(nm)
        out.append({**p, "sim": round(score * 100)})
        if len(out) >= limit:
            break
    # 同类别兜底：候选集内（有真实图）同类别但未出现在共现表中的
    if len(out) < limit:
        me = product_by_code(code)
        if me:
            from db import list_products
            exist = {o["code"] for o in out}
            for p in list_products():
                if "placeholder" in (p.get("img") or ""):
                    continue
                if p["code"] in exist:
                    continue
                nm = ((p.get("cn_name") or p.get("en_name")) or "").strip().lower()
                if nm and nm in used_names:
                    continue
                if p["category"] == me["category"] and p["code"] != code:
                    if nm:
                        used_names.add(nm)
                    out.append({**p, "sim": 60})
                    if len(out) >= limit:
                        break
    return out


def item_detail(code):
    from db import product_by_code
    return product_by_code(code)
