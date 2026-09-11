# -*- coding: utf-8 -*-
"""
download_pending.py —— 从 pending_images.json 批量下载商品图到前端目录
映射格式：{ "p25.jpg": "https://..." }
"""
import json, os, urllib.request, time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
META = os.path.join(DATA, "pending_images.json")
DST = r"E:\1\diversity\recsys-shop\frontend\public\images"

if not os.path.exists(META):
    print("no pending_images.json")
    raise SystemExit

m = json.load(open(META, encoding="utf-8"))
ok = fail = 0
for name, url in m.items():
    dst = os.path.join(DST, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 10000:
        ok += 1
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
            f.write(r.read())
        ok += 1
        print("OK", name, os.path.getsize(dst))
    except Exception as e:
        fail += 1
        print("FAIL", name, e)
    time.sleep(0.3)

print("done ok=%d fail=%d" % (ok, fail))
