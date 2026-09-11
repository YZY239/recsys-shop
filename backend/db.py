# -*- coding: utf-8 -*-
"""
db.py —— SQLite 存储层（数据与存储设计）
表：
  users       用户表（演示账号 + 真实 CustomerID 关联；密码仅存哈希）
  products    商品表（候选集商品，含图片）
  behaviors   行为日志表（点击/浏览）
  rec_cache   推荐结果缓存表（模拟 Redis 缓存，生产可替换为 Redis）
  tokens      登录令牌表（带过期时间；落库保证重启/多 worker 不失效）
  sessions    会话冷却状态表（shown/cycle 落库，重启/多 worker 一致）
"""
import csv, json, os, sqlite3, datetime

from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DB_PATH = os.path.join(DATA, "recsys.db")

# 3 个演示账号（绑定 train.csv 中的真实高活跃 CustomerID）
# 注意：password 字段只是"种子明文"，入库前一律先哈希（见 init_db），数据库中不存明文
DEMO_USERS = [
    {"username": "alice",  "password": "123456", "nickname": "小艾",
     "customer_id": "14911", "interest": ["厨房用品", "派对用品"], "color": "#E8590C",
     "slogan": "烘焙与下午茶爱好者"},
    {"username": "bob",    "password": "123456", "nickname": "小博",
     "customer_id": "17841", "interest": ["购物袋", "收纳用品"], "color": "#0E9F6E",
     "slogan": "收纳控 · 实用主义"},
    {"username": "carol",  "password": "123456", "nickname": "卡罗",
     "customer_id": "14606", "interest": ["厨房用品", "收纳用品"], "color": "#7C5CFC",
     "slogan": "把家布置成喜欢的样子"},
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """建表 + 写入种子数据（幂等）"""
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nickname TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        interest TEXT NOT NULL DEFAULT '[]',
        color TEXT NOT NULL DEFAULT '#4F6EF7',
        slogan TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS products(
        code TEXT PRIMARY KEY,
        en_name TEXT NOT NULL,
        cn_name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL,
        img TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS behaviors(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        action TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS rec_cache(
        user_id INTEGER NOT NULL,
        page INTEGER NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY(user_id, page)
    );
    CREATE TABLE IF NOT EXISTS tokens(
        token TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS sessions(
        customer_id TEXT PRIMARY KEY,
        cycle INTEGER NOT NULL DEFAULT -1,
        shown TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS favorites(
        user_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY(user_id, item_code)
    );
    CREATE TABLE IF NOT EXISTS cart(
        user_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        qty INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY(user_id, item_code)
    );
    """)
    # 旧库迁移：users 表补 avatar 列（头像 dataURL / 为空则用昵称首字 + color）
    cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    if "avatar" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT ''")
    # 种子账号（密码哈希入库；已存在的账号不受 INSERT OR IGNORE 影响，由下方迁移兜底）
    for u in DEMO_USERS:
        c.execute(
            "INSERT OR IGNORE INTO users(username,password,nickname,customer_id,interest,color,slogan) "
            "VALUES(?,?,?,?,?,?,?)",
            (u["username"], generate_password_hash(u["password"]), u["nickname"], u["customer_id"],
             json.dumps(u["interest"], ensure_ascii=False), u["color"], u["slogan"]))
    # 存量明文密码自动迁移：哈希串一定含冒号（scrypt:.../pbkdf2:...），不含则视为明文
    for r in c.execute("SELECT id, password FROM users").fetchall():
        if ":" not in (r["password"] or ""):
            c.execute("UPDATE users SET password=? WHERE id=?",
                      (generate_password_hash(r["password"]), r["id"]))
    # 演示账号密码统一迁移为 123456：仅当当前密码仍能以旧种子 demo123 登录时才重置
    # （用户后续在「账号设置」里改过的密码不会被覆盖）
    for u in DEMO_USERS:
        row = c.execute("SELECT id, password FROM users WHERE username=?", (u["username"],)).fetchone()
        if row and check_password_hash(row["password"], "demo123") \
                and not check_password_hash(row["password"], "123456"):
            c.execute("UPDATE users SET password=? WHERE id=?",
                      (generate_password_hash("123456"), row["id"]))
    # 顺手清理已过期的令牌
    c.execute("DELETE FROM tokens WHERE expires_at <= datetime('now','localtime')")
    # 商品表（全量目录：products_full.csv，含完整数据集 4226 个商品；演示 24 个带真实图片，
    # 其余商品使用分类占位图）
    with open(os.path.join(DATA, "products_full.csv"), encoding="utf-8-sig", newline="") as f:
        cand = list(csv.DictReader(f))
    c.execute("DELETE FROM products")
    for it in cand:
        try:
            price = float(it["price"]) if it["price"] not in ("", "None") else None
        except ValueError:
            price = None
        c.execute(
            "INSERT OR REPLACE INTO products(code,en_name,cn_name,category,price,img) VALUES(?,?,?,?,?,?)",
            (it["code"], it["en_name"], it["cn_name"] or it["en_name"],
             it["category"] or "未分类", price, it["img"] or ""))
    conn.commit()
    conn.close()


def list_products():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def product_by_code(code):
    conn = get_conn()
    r = conn.execute("SELECT * FROM products WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(r) if r else None


def user_by_username(username):
    conn = get_conn()
    r = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(r) if r else None


def user_by_customer(customer_id):
    conn = get_conn()
    r = conn.execute("SELECT * FROM users WHERE customer_id=?", (customer_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def add_behavior(user_id, item_code, action):
    conn = get_conn()
    conn.execute("INSERT INTO behaviors(user_id,item_code,action) VALUES(?,?,?)",
                 (user_id, item_code, action))
    conn.commit()
    conn.close()


def clicked_codes(user_id, limit=20):
    """该用户最近点击过的商品（行为日志 → 实时插入的依据）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT item_code FROM behaviors WHERE user_id=? AND action='click' "
        "ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
    conn.close()
    return [r["item_code"] for r in rows]


def clear_behaviors():
    """清空全部行为记录（TEST-ONLY：测试面板「清理测试数据」使用，删除面板时一并删除）"""
    conn = get_conn()
    conn.execute("DELETE FROM behaviors")
    conn.commit()
    conn.close()


# ---------- 登录令牌（带过期时间，落库持久化） ----------
TOKEN_TTL_HOURS = 24 * 7   # 登录态有效期：7 天


def save_token(token, customer_id, ttl_hours=TOKEN_TTL_HOURS):
    """签发令牌：写入 tokens 表，expires_at 到期后自动失效"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO tokens(token,customer_id,expires_at) "
        "VALUES(?,?,datetime('now','localtime',?))",
        (token, str(customer_id), f"+{ttl_hours} hours"))
    conn.commit()
    conn.close()


def token_customer(token):
    """校验令牌：有效返回 customer_id；过期/不存在返回 None（过期记录顺手删除）"""
    if not token:
        return None
    conn = get_conn()
    r = conn.execute("SELECT customer_id, expires_at FROM tokens WHERE token=?", (token,)).fetchone()
    if not r:
        conn.close()
        return None
    if r["expires_at"] <= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"):
        conn.execute("DELETE FROM tokens WHERE token=?", (token,))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return r["customer_id"]


def delete_token(token):
    """注销令牌（登出）"""
    conn = get_conn()
    conn.execute("DELETE FROM tokens WHERE token=?", (token,))
    conn.commit()
    conn.close()


def verify_password(password_hash, password):
    """校验密码（哈希比对；明文旧数据由 init_db 迁移兜底）"""
    return check_password_hash(password_hash, password)


# ---------- 会话冷却状态（SQLite 持久化，重启/多 worker 一致） ----------
def get_session(customer_id):
    """读取会话状态 {cycle, shown: [code...]}；无记录返回默认值"""
    conn = get_conn()
    r = conn.execute("SELECT cycle, shown FROM sessions WHERE customer_id=?",
                     (str(customer_id),)).fetchone()
    conn.close()
    if not r:
        return {"cycle": -1, "shown": []}
    try:
        return {"cycle": int(r["cycle"]), "shown": json.loads(r["shown"])}
    except Exception:
        return {"cycle": -1, "shown": []}


def set_session(customer_id, cycle, shown):
    """写入会话状态（整表覆盖，调用方在请求结束时一次性保存）"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO sessions(customer_id,cycle,shown) VALUES(?,?,?)",
        (str(customer_id), int(cycle), json.dumps(list(shown)[-500:])))
    conn.commit()
    conn.close()


def reset_sessions():
    """清空全部会话状态（TEST-ONLY：测试面板「清理测试数据」使用）"""
    conn = get_conn()
    conn.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()


# ---------- 用户中心（注册 / 资料修改） ----------
INTEREST_TAGS = ["厨房用品", "食品", "装饰品", "家居装饰", "派对用品",
                 "购物袋", "收纳用品", "文具", "玩具", "服饰"]


def register_user(username, password, nickname="", interest=None):
    """注册新用户：密码哈希入库；customer_id 用 9 开头的 6 位号段（与数据集真实
    CustomerID 区分）；新用户无历史 → 推荐自动走兴趣冷启动/热门兜底"""
    conn = get_conn()
    try:
        cid = None
        for _ in range(20):
            cand = "9" + str(os.getpid())[-2:] + str(uuid_like())
            if not conn.execute("SELECT 1 FROM users WHERE customer_id=?", (cand,)).fetchone():
                cid = cand
                break
        c = conn.cursor()
        c.execute(
            "INSERT INTO users(username,password,nickname,customer_id,interest,color,slogan) "
            "VALUES(?,?,?,?,?,?,?)",
            (username, generate_password_hash(password),
             nickname or username, cid,
             json.dumps(interest or [], ensure_ascii=False),
             "#FF5000", "新朋友 · 欢迎来到暖物集"))
        conn.commit()
        return user_by_username(username)
    finally:
        conn.close()


def uuid_like():
    """轻量随机串（避免额外依赖）"""
    import random
    return "".join(random.choice("0123456789") for _ in range(4))


def update_profile(user_id, **fields):
    """更新用户资料（白名单字段）；返回更新后的用户"""
    allowed = {"username", "nickname", "color", "slogan", "avatar", "interest"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "interest":
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k}=?")
        vals.append(v)
    if sets:
        conn = get_conn()
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", (*vals, user_id))
        conn.commit()
        conn.close()
    conn = get_conn()
    r = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def update_password(user_id, new_password):
    """重置密码（哈希入库）"""
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE id=?",
                 (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()


# ---------- 我的收藏 ----------
def list_favorites(user_id):
    """收藏列表（join 商品信息，按收藏时间倒序）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.*, f.created_at AS fav_time FROM favorites f "
        "JOIN products p ON p.code = f.item_code "
        "WHERE f.user_id=? ORDER BY f.created_at DESC, f.rowid DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_favorited(user_id, item_code):
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND item_code=?",
                     (user_id, item_code)).fetchone()
    conn.close()
    return bool(r)


def toggle_favorite(user_id, item_code):
    """收藏 / 取消收藏（幂等切换）；返回切换后的状态"""
    conn = get_conn()
    if conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND item_code=?",
                    (user_id, item_code)).fetchone():
        conn.execute("DELETE FROM favorites WHERE user_id=? AND item_code=?",
                     (user_id, item_code))
        conn.commit()
        conn.close()
        return False
    conn.execute("INSERT OR IGNORE INTO favorites(user_id,item_code) VALUES(?,?)",
                 (user_id, item_code))
    conn.commit()
    conn.close()
    return True


def favorites_count(user_id):
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) AS n FROM favorites WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return r["n"]


# ---------- 购物车 ----------
def list_cart(user_id):
    """购物车列表（join 商品信息，按加入时间倒序）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT p.*, c.qty FROM cart c JOIN products p ON p.code = c.item_code "
        "WHERE c.user_id=? ORDER BY c.created_at DESC, c.rowid DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_cart(user_id, item_code, qty=1):
    """加入购物车（已存在则数量累加）"""
    conn = get_conn()
    conn.execute(
        "INSERT INTO cart(user_id,item_code,qty) VALUES(?,?,?) "
        "ON CONFLICT(user_id,item_code) DO UPDATE SET qty = qty + ?",
        (user_id, item_code, max(1, int(qty)), max(1, int(qty))))
    conn.commit()
    conn.close()


def set_cart_qty(user_id, item_code, qty):
    """修改数量；qty<=0 视为移除"""
    conn = get_conn()
    if qty <= 0:
        conn.execute("DELETE FROM cart WHERE user_id=? AND item_code=?", (user_id, item_code))
    else:
        conn.execute("UPDATE cart SET qty=? WHERE user_id=? AND item_code=?",
                     (int(qty), user_id, item_code))
    conn.commit()
    conn.close()


def remove_cart(user_id, item_code):
    conn = get_conn()
    conn.execute("DELETE FROM cart WHERE user_id=? AND item_code=?", (user_id, item_code))
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def cart_count(user_id):
    conn = get_conn()
    r = conn.execute("SELECT COALESCE(SUM(qty),0) AS n FROM cart WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return r["n"]


def get_cache(user_id, page):
    conn = get_conn()
    r = conn.execute("SELECT payload FROM rec_cache WHERE user_id=? AND page=?",
                     (user_id, page)).fetchone()
    conn.close()
    return json.loads(r["payload"]) if r else None


def set_cache(user_id, page, payload):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO rec_cache(user_id,page,payload,updated_at) "
        "VALUES(?,?,?,datetime('now','localtime'))",
        (user_id, page, json.dumps(payload, ensure_ascii=False)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("db ready:", DB_PATH)
    print("products:", len(list_products()))
