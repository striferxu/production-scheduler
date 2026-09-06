# 生产排程系统（APS）v1.0 - Docker 镜像
FROM python:3.12-slim

# 时区
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先复制依赖清单并安装（利用 Docker 层缓存，代码变更不重复装依赖）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端与前端源码
# 注意：数据库路径为 /app/data/scheduler.db，由程序首次启动自动创建
COPY backend ./backend
COPY frontend ./frontend

# 预创建数据目录（配合 volume 持久化）
RUN mkdir -p /app/data && chmod -R a+w /app/data

EXPOSE 8899

# 直接以 Python 启动（无需 start.sh 的 venv/增量依赖逻辑，容器内已装好依赖）
ENTRYPOINT ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8899"]
