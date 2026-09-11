# 后端镜像：离线产物（CSV）已随代码目录挂载/拷贝，容器内直接装配
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据目录由构建上下文带入（含离线流水线产物 user_recs_expanded.csv 等）
EXPOSE 5000

# 生产用 gunicorn；SQLite 文件存储无需外部依赖
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
