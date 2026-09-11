# -*- coding: utf-8 -*-
"""
build_full_catalog.py —— 构建全量商品目录 + 热门商品（供 db.init_db / recommend 使用）
输出:
  backend/data/products_full.csv  (code,en_name,cn_name,category,price,img)
  backend/data/hot_items.csv      (code,score)  数据集热门商品 Top200（train 销量聚合）
  frontend/public/images/placeholder-*.svg（分类占位图，全量商品中非演示 24 个使用）
数据源:
  E:\\1\\diversity\\data\\products_clean.csv  3542 商品（中英文名，类目列为 '?' 需自行归类）
  E:\\1\\diversity\\data\\train.csv           原始交互（Description / UnitPrice / Quantity）
  backend/data/demo_candidates.json           演示 24 商品（真实类目 + 图片映射）
  backend/data/user_recs_clean.csv            每用户 Top50 候选（决定商品全集覆盖）
"""
import csv, json, os, collections, statistics

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
ROOT = os.path.dirname(BASE)
RAW = r"E:\1\diversity\data"
FRONT_IMAGES = os.path.join(ROOT, "frontend", "public", "images")

# ---------- 1. 读入数据源 ----------
prod_clean = {}  # StockCode -> {en, cn}
with open(os.path.join(RAW, "products_clean.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        prod_clean[r["StockCode"]] = {
            "en": r["Description"] or "",
            "cn": r["Chinese_Description"] or "",
        }

with open(os.path.join(DATA, "demo_candidates.json"), encoding="utf-8") as f:
    demo = json.load(f)
demo_by = {it["id"]: it for it in demo}

rec_items = set()
with open(os.path.join(DATA, "user_recs_clean.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rec_items.add(r["item_id"])

# train.csv：每商品 Description（首见）+ 中位单价 + 销量（热门）
train_desc, prices, qty = {}, collections.defaultdict(list), collections.Counter()
with open(os.path.join(RAW, "train.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        code = r["StockCode"]
        train_desc.setdefault(code, r["Description"] or "")
        try:
            p = float(r["UnitPrice"])
            if p > 0:
                prices[code].append(p)
        except (ValueError, TypeError):
            pass
        try:
            q = float(r["Quantity"])
            if q > 0:
                qty[code] += q
        except (ValueError, TypeError):
            pass

# ---------- 2. 类目规则（自行增加类目：按中文/英文名关键词归类） ----------
# 规则有序，先命中先得；演示 24 个商品用官方类目覆盖
CATS = [
    ("食品",      ["糖果", "巧克力", "饼干", "咖啡豆", "茶叶", "茶包", "零食", "饮料", "食品", "蜜饯", "果酱", "蜂蜜", "茶"]),
    ("厨房用品",  ["蛋糕", "烘焙", "烤", "咖啡", "茶杯", "茶壶", "马克杯", "杯子", "餐盘", "餐具", "碗", "碟", "勺", "叉", "锅", "厨", "餐", "面包", "糕点", "蛋架", "搅拌", "奶油", "围裙", "砧板", "厨房"]),
    ("装饰品",    ["圣诞", "心形", "蝴蝶结", "摆件", "公仔", "玩偶", "雕像", "挂饰", "挂件", "手链", "项链", "发饰", "饰品"]),
    ("家居装饰",  ["灯", "烛台", "蜡烛", "相框", "时钟", "钟", "花瓶", "花盆", "窗帘", "靠垫", "抱枕", "地毯", "镜子", "壁挂", "墙饰", "灯笼"]),
    ("派对用品",  ["派对", "气球", "贺卡", "礼品", "礼物", "彩带", "皇冠", "聚会", "彩条", "派对帽"]),
    ("购物袋",    ["包", "袋", "购物"]),
    ("收纳用品",  ["收纳", "盒", "箱", "篮", "挂钩", "衣架", "抽屉", "整理", "架"]),
    ("文具",      ["笔", "笔记本", "卡片", "信封", "标签", "印章", "胶带", "文件夹", "便签", "贴纸", "书签", "文具", "纸"]),
    ("玩具",      ["玩具", "积木", "模型", "棋", "游戏", "娃娃", "毛绒"]),
    ("服饰",      ["衣", "帽", "围巾", "手套", "袜", "鞋", "头饰", "腰带"]),
]
EN_PATTERNS = [
    ("食品",     ["TEA", "CHOCOLATE", "BISCUIT", "JAM", "HONEY", "SWEET", "FOOD"]),
    ("厨房用品", ["KITCHEN", "CAKE", "BAKING", "MUG", "CUP", "PLATE", "BOWL", "SPOON", "PAN", "COFFEE", "JUG", "TRAY", "OVEN"]),
    ("装饰品",   ["CHRISTMAS", "HEART", "ORNAMENT", "STATUE", "DOLL", "BEADS", "DECORATION"]),
    ("家居装饰", ["LAMP", "CANDLE", "LANTERN", "CLOCK", "VASE", "CURTAIN", "CUSHION", "RUG", "MIRROR", "PICTURE FRAME", "LIGHT", "DOORBELL"]),
    ("派对用品", ["PARTY", "BALLOON", "GIFT", "CONFETTI", "CROWN", "CARD"]),
    ("购物袋",   ["BAG", "TOTE", "SHOPPER"]),
    ("收纳用品", ["STORAGE", "BOX", "BASKET", "HANGER", "ORGANI", "SHELF"]),
    ("文具",     ["PEN", "NOTE", "ENVELOPE", "LABEL", "STICKER", "BOOKMARK", "PAPER", "CARD"]),
    ("玩具",     ["TOY", "PUZZLE", "GAME"]),
    ("服饰",     ["HAT", "SCARF", "GLOVE", "SOCKS", "SHOES", "APRON"]),
]


def classify(cn, en):
    text = (cn or "") + "|" + (en or "").upper()
    for cat, kws in CATS:
        for k in kws:
            if k in text:
                return cat
    for cat, kws in EN_PATTERNS:
        for k in kws:
            if k in text:
                return cat
    return "生活用品"


# ---------- 3. 构建全量商品目录 ----------
SLUG = {"厨房用品": "kitchen", "家居装饰": "home", "装饰品": "decor", "派对用品": "party",
        "购物袋": "bag", "收纳用品": "storage", "文具": "stationery", "玩具": "toy",
        "食品": "food", "服饰": "clothing", "生活用品": "life", "未分类": "other"}


def _slug_placeholder(cat):
    return "/images/placeholder-" + SLUG.get(cat, "other") + ".svg"


universe = set(prod_clean) | rec_items | set(demo_by)
rows = []
for code in sorted(universe):
    pc = prod_clean.get(code, {})
    dm = demo_by.get(code)
    en = dm["en"] if dm and dm.get("en") else pc.get("en") or train_desc.get(code) or ""
    cn = dm["cn"] if dm and dm.get("cn") else pc.get("cn") or ""
    cat = dm["cat"] if dm and dm.get("cat") and dm["cat"] != "未分类" else classify(cn, en)
    if dm:
        try:
            price = float(dm["price"]) if dm.get("price") else None
        except ValueError:
            price = None
    else:
        ps = prices.get(code)
        price = round(statistics.median(ps), 2) if ps else None
    img = "/images/" + dm["file"] if dm else _slug_placeholder(cat)
    rows.append({
        "code": code, "en_name": en, "cn_name": cn, "category": cat,
        "price": price, "img": img,
    })

# 演示 24 个商品即使在全量规则下也用官方类目（已在上面处理）


# ---------- 4. 输出商品表 ----------
with open(os.path.join(DATA, "products_full.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["code", "en_name", "cn_name", "category", "price", "img"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

# ---------- 5. 热门商品（train 销量聚合，取 Top200，仅在商品目录内） ----------
cat_of = {r["code"]: r["category"] for r in rows}
hot = [(c, q) for c, q in qty.items() if c in cat_of]
hot.sort(key=lambda x: -x[1])
hot = hot[:200]
with open(os.path.join(DATA, "hot_items.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["code", "score"])
    for i, (code, q) in enumerate(hot):
        score = round(2.0 + 1.8 * (1 - i / 200), 4)  # 3.8 -> 2.0，低于真实 Top10 推荐分
        w.writerow([code, score])

# ---------- 6. 分类占位图（SVG，浅色暖物集风格） ----------
COLOR = {"kitchen": "#F6A97A", "home": "#9CC3A8", "decor": "#E8B4C8", "party": "#F7C873",
         "bag": "#A8B7E8", "storage": "#C9B4E8", "stationery": "#A8DCE8", "toy": "#F4D07C",
         "food": "#F0A58F", "clothing": "#B8C98F", "life": "#D8C4A8", "other": "#C9CDD4"}
NAME = {"kitchen": "厨房用品", "home": "家居装饰", "decor": "装饰品", "party": "派对用品",
        "bag": "购物袋", "storage": "收纳用品", "stationery": "文具", "toy": "玩具",
        "food": "食品", "clothing": "服饰", "life": "生活用品", "other": "精选好物"}
os.makedirs(FRONT_IMAGES, exist_ok=True)
for slug, color in COLOR.items():
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <rect width="400" height="400" fill="#FFF6EE"/>
  <circle cx="200" cy="178" r="86" fill="{color}" opacity="0.9"/>
  <text x="200" y="198" font-size="34" font-family="Microsoft YaHei, sans-serif" fill="#FFFFFF" text-anchor="middle" font-weight="bold">{NAME[slug]}</text>
  <text x="200" y="300" font-size="18" font-family="Microsoft YaHei, sans-serif" fill="#B0896F" text-anchor="middle">暖物集 · 精选好物</text>
</svg>'''
    with open(os.path.join(FRONT_IMAGES, "placeholder-" + slug + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)

# ---------- 7. 统计 ----------
from collections import Counter
c_cat = Counter(r["category"] for r in rows)
no_name = sum(1 for r in rows if not r["cn_name"] and not r["en_name"])
no_price = sum(1 for r in rows if r["price"] is None)
demo_ok = all(any(x["code"] == it["id"] for x in rows) for it in demo)
print("products_full rows:", len(rows))
print("categories:", dict(c_cat.most_common()))
print("no name:", no_name, "| no price:", no_price, "| demo all covered:", demo_ok)
print("hot items:", len(hot), "| hot top5:", [(c, round(q)) for c, q in hot[:5]])
print("bob missing now:", [(r['code'], r['cn_name'] or r['en_name'], r['category']) for r in rows if r['code'] in ('79160', '22356')])
