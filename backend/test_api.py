# -*- coding: utf-8 -*-
import urllib.request, json

BASE = "http://127.0.0.1:5000"

def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        r = urllib.request.urlopen(req, data=data, timeout=10)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"HTTP": e.code, "body": e.read().decode()}

# 1. 三个账号登录
for u in ["alice", "bob", "carol"]:
    r = call("POST", "/api/auth/login", {"username": u, "password": "demo123"})
    print(f"[login {u}] code={r.get('code')} user={r.get('user',{}).get('nickname')} token={str(r.get('token'))[:8]}...")
    assert r.get("code") == 0

# 2. alice 推荐第1页（候选集 Top50）
r = call("POST", "/api/auth/login", {"username": "alice", "password": "demo123"})
tok = r["token"]
r = call("GET", "/api/recommend?page=1&page_size=8", token=tok)
print("[rec p1] count=", len(r["list"]), "codes=", [x["code"] for x in r["list"]],
      "has_more=", r["has_more"], "total=", r["total"])

# 3. 商品详情 + 相似
r = call("GET", "/api/items/22423", token=tok)
print("[detail 22423]", r.get("item", {}).get("cn_name"), r.get("item", {}).get("price"))
r = call("GET", "/api/items/22423/similar?limit=3", token=tok)
print("[similar 22423]", [(x["code"], x["sim"]) for x in r.get("items", [])])

# 4. 点击行为上报（实时插入候选）
r = call("POST", "/api/behaviors", {"item_code": "22423", "action": "click"}, token=tok)
print("[behavior]", r.get("code"), "inserted=", [x["code"] for x in r.get("inserted", [])])

# 5. 第2页：应嵌入点击商品的相似商品
r = call("GET", "/api/recommend?page=2&page_size=8", token=tok)
print("[rec p2] count=", len(r["list"]), "codes=", [x["code"] for x in r["list"]],
      "from_click=", [x.get("from_click") for x in r["list"] if x.get("from_click")])

# 6. 错误密码
r = call("POST", "/api/auth/login", {"username": "alice", "password": "wrong"})
print("[bad login] code=", r.get("code"))

# 7. 三个账号推荐内容互不相同（个性化验证）
views = {}
for u in ["alice", "bob", "carol"]:
    r = call("POST", "/api/auth/login", {"username": u, "password": "demo123"})
    rr = call("GET", "/api/recommend?page=1&page_size=10", token=r["token"])
    views[u] = [x["code"] for x in rr["list"]]
    print(f"[{u} top10]", views[u])
print("[个性化] alice∩bob=", set(views["alice"]) & set(views["bob"]),
      " alice∩carol=", set(views["alice"]) & set(views["carol"]),
      " bob∩carol=", set(views["bob"]) & set(views["carol"]))
print("ALL OK")
