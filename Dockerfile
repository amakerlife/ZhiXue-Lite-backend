FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml ./
COPY gunicorn.conf.py ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY assets/ ./assets/

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV PYTHONPATH=/app/src

# 启动命令
CMD ["gunicorn", "--config", "gunicorn.conf.py", "src.ZhiXueLite.main:app"]