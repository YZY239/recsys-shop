# -*- coding: utf-8 -*-
"""
app.py —— Flask 后端主应用
接口（对应《完整推荐系统》第 4 节「接口设计」）：
  POST /api/auth/login            登录接口（鉴权后绑定用户身份 → token）
  POST /api/auth/logout           登出接口（吊销当前 token）
  GET  /api/recommend             推荐列表接口（分页拉取该用户候选集推荐）
  GET  /api/items/<code>          商品详情接口
  GET  /api/items/<code>/similar  相似商品接口
  POST /api/behaviors             行为上报接口（点击日志 → 触发推荐流更新）
  GET  /api/profile               当前用户画像接口

安全设计：
  - 密码：库内只存 Werkzeug 哈希（scrypt），登录时 check_password_hash 比对；
    存量明文由 db.init_db() 自动迁移
  - Token：uuid4 随机 + 落库（tokens 表）+ 7 天过期；重启/多 worker 不失效，
    支持登出吊销（内存 token 表的三个老问题一并解决）
"""
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

import db
import recommend

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def _public_user(u):
    return {
        "id": u["id"], "username": u["username"], "nickname": u["nickname"],
        "customer_id": u["customer_id"],
        "interest": __import__("json").loads(u["interest"]),
        "color": u["color"], "slogan": u["slogan"],
        "avatar": u.get("avatar") or "",
    }


def _auth():
    """从 Authorization: Bearer <token> 取当前用户（token 落库校验 + 过期检查）"""
    h = request.headers.get("Authorization", "")
    token = h.replace("Bearer ", "").strip() if h else ""
    uid = db.token_customer(token)
    if uid is None:
        return None, token
    row = db.user_by_customer(str(uid)) if str(uid).isdigit() else None
    # 兼容按 username 绑定的情况
    if row is None:
        for u in db.DEMO_USERS:
            if u["username"] == str(uid):
                row = db.user_by_username(u["username"])
    return row, token


# ---------- 登录 ----------
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    u = db.user_by_username(username)
    if not u or not db.verify_password(u["password"], password):
        return jsonify({"code": 401, "msg": "用户名或密码错误"}), 401
    token = uuid.uuid4().hex
    db.save_token(token, u["customer_id"])   # 绑定真实 CustomerID → 个性化推荐
    return jsonify({"code": 0, "token": token, "user": _public_user(u)})


# ---------- 登出 ----------
@app.route("/api/auth/logout", methods=["POST"])
def logout():
    _, token = _auth()
    if token:
        db.delete_token(token)
    return jsonify({"code": 0, "msg": "已退出登录"})


@app.route("/api/profile", methods=["GET"])
def profile():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    clicked = db.clicked_codes(u["id"])
    return jsonify({"code": 0, "user": _public_user(u), "clicked_count": len(clicked)})


# ---------- 推荐列表（分页） ----------
@app.route("/api/recommend", methods=["GET"])
def recommend_list():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    page = max(1, request.args.get("page", 1, type=int))
    page_size = min(20, max(1, request.args.get("page_size", 8, type=int)))
    data = recommend.get_paged_recs(u["customer_id"], page, page_size)

    # 实时插入联动：把该用户点击过的商品的相似商品嵌入后续页（去重 + 会话冷却）
    clicked = db.clicked_codes(u["id"])
    extra = []
    if page > 1 and clicked:
        seen = {it["code"] for it in data["list"]}
        shown = recommend.shown_codes(u["customer_id"])
        clicked_set = set(clicked)
        for code in clicked:
            for sim in recommend.similar_items(code, 2):
                if sim["code"] in seen or sim["code"] in shown or sim["code"] in clicked_set:
                    continue
                if not (sim.get("cn_name") or sim.get("en_name")):
                    continue  # 数据缺口商品不参与实时插入
                extra.append({**sim, "sim": sim["sim"], "from_click": code})
                seen.add(sim["code"])
                if len(extra) >= 3:
                    break
            if len(extra) >= 3:
                break
        data["list"] = data["list"] + extra
        if extra:
            recommend.mark_shown(u["customer_id"], [it["code"] for it in extra])
    return jsonify({"code": 0, **data})


# ---------- 商品详情 ----------
@app.route("/api/items/<code>", methods=["GET"])
def item_detail(code):
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    p = recommend.item_detail(code)
    if not p:
        return jsonify({"code": 404, "msg": "商品不存在"}), 404
    return jsonify({"code": 0, "item": p})


# ---------- 相似商品 ----------
@app.route("/api/items/<code>/similar", methods=["GET"])
def item_similar(code):
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    limit = min(8, max(1, request.args.get("limit", 4, type=int)))
    sims = recommend.similar_items(code, limit)
    return jsonify({"code": 0, "items": sims})


# ---------- 行为上报（点击日志） ----------
@app.route("/api/behaviors", methods=["POST"])
def behaviors():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("item_code") or "").strip()
    action = (data.get("action") or "click").strip()
    if not code:
        return jsonify({"code": 400, "msg": "缺少 item_code"}), 400
    db.add_behavior(u["id"], code, action)
    # 返回该商品的相似商品 → 前端实时插入推荐流
    # 去重口径：已点击过的（永久冷却）、本轮已展示过的（会话冷却）、无名的商品一律不返回；
    # 且按"展示名"再兜一层（目录存在同名不同码商品），保证插入商品绝不与已出现商品重复
    clicked = set(db.clicked_codes(u["id"]))
    shown = recommend.shown_codes(u["customer_id"])
    from db import product_by_code
    shown_names = set()
    for c in shown | clicked | {code}:
        p = product_by_code(c)
        if p:
            shown_names.add(((p.get("cn_name") or p.get("en_name")) or "").strip().lower())
    inserted = []
    for s in recommend.similar_items(code, 12):
        if s["code"] in clicked or s["code"] in shown:
            continue
        nm = ((s.get("cn_name") or s.get("en_name")) or "").strip().lower()
        if not nm or nm in shown_names:
            continue
        shown_names.add(nm)
        inserted.append(s)
        if len(inserted) >= 3:
            break
    if inserted:
        recommend.mark_shown(u["customer_id"], [s["code"] for s in inserted])
    return jsonify({"code": 0, "msg": "已记录", "inserted": inserted})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"code": 0, "msg": "ok"})


# ---------- 测试辅助接口（TEST-ONLY：测试面板「清理测试数据」使用，删除面板时一并删除） ----------
# ---------- 注册 ----------
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or "").strip()
    interest = data.get("interest") or []
    if len(username) < 2:
        return jsonify({"code": 400, "msg": "用户名至少 2 个字符"}), 400
    if len(password) < 6:
        return jsonify({"code": 400, "msg": "密码至少 6 位"}), 400
    if db.user_by_username(username):
        return jsonify({"code": 409, "msg": "用户名已被占用"}), 409
    interest = [t for t in interest if t in db.INTEREST_TAGS][:4]
    u = db.register_user(username, password, nickname, interest)
    token = uuid.uuid4().hex
    db.save_token(token, u["customer_id"])
    return jsonify({"code": 0, "token": token, "user": _public_user(u)})


# ---------- 账号设置（资料 / 密码 / 头像） ----------
@app.route("/api/profile/update", methods=["POST"])
def profile_update():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    fields = {}
    if "nickname" in data:
        nick = (data.get("nickname") or "").strip()
        if not nick:
            return jsonify({"code": 400, "msg": "昵称不能为空"}), 400
        fields["nickname"] = nick
    if "username" in data:
        uname = (data.get("username") or "").strip()
        if len(uname) < 2:
            return jsonify({"code": 400, "msg": "用户名至少 2 个字符"}), 400
        exist = db.user_by_username(uname)
        if exist and exist["id"] != u["id"]:
            return jsonify({"code": 409, "msg": "用户名已被占用"}), 409
        fields["username"] = uname
    if "color" in data and data.get("color"):
        fields["color"] = str(data["color"])[:16]
    if "slogan" in data:
        fields["slogan"] = str(data.get("slogan") or "")[:60]
    if "interest" in data:
        tags = [t for t in (data.get("interest") or []) if t in db.INTEREST_TAGS][:4]
        fields["interest"] = tags
    if not fields:
        return jsonify({"code": 400, "msg": "没有可更新的字段"}), 400
    nu = db.update_profile(u["id"], **fields)
    return jsonify({"code": 0, "user": _public_user(nu), "msg": "资料已更新"})


@app.route("/api/profile/password", methods=["POST"])
def profile_password():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    old_pw = data.get("old_password") or ""
    new_pw = data.get("new_password") or ""
    if not db.verify_password(u["password"], old_pw):
        return jsonify({"code": 400, "msg": "当前密码不正确"}), 400
    if len(new_pw) < 6:
        return jsonify({"code": 400, "msg": "新密码至少 6 位"}), 400
    db.update_password(u["id"], new_pw)
    return jsonify({"code": 0, "msg": "密码已修改，下次登录请使用新密码"})


@app.route("/api/profile/avatar", methods=["POST"])
def profile_avatar():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    avatar = (data.get("avatar") or "").strip()
    if avatar:
        # 仅接受 dataURL 图片（前端压缩到 200px）；限制 200KB 防止撑爆 SQLite
        if not avatar.startswith("data:image/"):
            return jsonify({"code": 400, "msg": "头像格式不正确"}), 400
        if len(avatar) > 200 * 1024:
            return jsonify({"code": 400, "msg": "头像图片过大，请换一张"}), 400
    nu = db.update_profile(u["id"], avatar=avatar)
    return jsonify({"code": 0, "user": _public_user(nu), "msg": "头像已更新"})


# ---------- 我的收藏 ----------
@app.route("/api/favorites", methods=["GET"])
def favorites_list():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    items = db.list_favorites(u["id"])
    return jsonify({"code": 0, "items": items, "count": len(items)})


@app.route("/api/favorites/toggle", methods=["POST"])
def favorites_toggle():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("item_code") or "").strip()
    if not code or not db.product_by_code(code):
        return jsonify({"code": 400, "msg": "商品不存在"}), 400
    favorited = db.toggle_favorite(u["id"], code)
    return jsonify({"code": 0, "favorited": favorited,
                    "msg": "已收藏" if favorited else "已取消收藏",
                    "count": db.favorites_count(u["id"])})


@app.route("/api/favorites/status", methods=["GET"])
def favorites_status():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    code = (request.args.get("item_code") or "").strip()
    return jsonify({"code": 0, "favorited": db.is_favorited(u["id"], code)})


# ---------- 购物车 ----------
def _cart_payload(user_id):
    items = db.list_cart(user_id)
    total = round(sum((it["price"] or 0) * it["qty"] for it in items), 2)
    return {"items": items, "count": sum(it["qty"] for it in items), "total": total}


@app.route("/api/cart", methods=["GET"])
def cart_list():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    return jsonify({"code": 0, **_cart_payload(u["id"])})


@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("item_code") or "").strip()
    qty = max(1, min(99, int(data.get("qty") or 1)))
    if not code or not db.product_by_code(code):
        return jsonify({"code": 400, "msg": "商品不存在"}), 400
    db.add_cart(u["id"], code, qty)
    return jsonify({"code": 0, "msg": "已加入购物车", **_cart_payload(u["id"])})


@app.route("/api/cart/qty", methods=["POST"])
def cart_qty():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("item_code") or "").strip()
    qty = int(data.get("qty") or 0)
    db.set_cart_qty(u["id"], code, qty)
    return jsonify({"code": 0, **_cart_payload(u["id"])})


@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("item_code") or "").strip()
    db.remove_cart(u["id"], code)
    return jsonify({"code": 0, "msg": "已移除", **_cart_payload(u["id"])})


@app.route("/api/test/clean", methods=["POST"])
def test_clean():
    u, _ = _auth()
    if not u:
        return jsonify({"code": 401, "msg": "未登录"}), 401
    db.clear_behaviors()
    recommend.reset_cool()
    return jsonify({"code": 0, "msg": "测试数据已清理"})


# ---------- 前端静态托管（单容器/单进程部署用） ----------
# 本地开发仍走 Vite dev server(:5173)；托管部署（PythonAnywhere 等）时
# 由 Flask 直接服务 frontend/dist 构建产物，/api 路由优先级更高不受影响。
import os
from flask import send_from_directory

_DIST = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"))
_PUBLIC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "public"))


@app.route("/images/<path:p>")
def images(p):
    # 商品图片直接复用 public/images（dist 里不再重复拷贝 32MB）
    return send_from_directory(os.path.join(_PUBLIC, "images"), p)


@app.route("/")
@app.route("/<path:path>")
def spa(path=""):
    full = os.path.normpath(os.path.join(_DIST, path))
    if path and full.startswith(_DIST) and os.path.isfile(full):
        return send_from_directory(_DIST, path)
    return send_from_directory(_DIST, "index.html")


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
