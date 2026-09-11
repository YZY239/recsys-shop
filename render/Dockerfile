# 单容器镜像（用于 Render / 任意单容器免费托管平台）
# 构建上下文必须是项目根目录（recsys-shop/），Dockerfile 路径指向 render/Dockerfile
# 两阶段：node 构建 Vue 前端 → python 镜像内 nginx 托管静态文件 + gunicorn 跑后端

# ---------- 阶段 1：前端构建 ----------
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.12-slim

# nginx 用于托管前端静态文件并反代 /api 到本机 gunicorn
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码 + 数据（SQLite / 离线推荐产物，约 60MB，随镜像带入）
COPY backend/ /app/

# 前端构建产物
COPY --from=frontend-build /build/dist /usr/share/nginx/html

# nginx 配置与启动脚本
COPY render/nginx-render.conf /etc/nginx/conf.d/app.conf
COPY render/start.sh /start.sh
RUN chmod +x /start.sh

# Render 会注入 PORT 环境变量；本地测试默认 8080
ENV PORT=8080
EXPOSE 8080

CMD ["/start.sh"]
