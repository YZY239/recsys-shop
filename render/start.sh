#!/bin/sh
# 单容器启动脚本：把 ${PORT} 写进 nginx 配置 → 后台起 gunicorn → 前台跑 nginx
set -e

PORT="${PORT:-8080}"
sed -i "s/\${PORT}/${PORT}/g" /etc/nginx/conf.d/app.conf

# 后端：gunicorn 2 worker，监听容器内部回环端口（不对外）
gunicorn -w 2 -b 127.0.0.1:5000 app:app &

# 前台运行 nginx，保持容器存活
exec nginx -g 'daemon off;'
