# Docker 部署说明

本项目支持通过 Docker 和 Docker Compose 进行部署。

## 快速开始

### 1. 准备环境文件

```bash
# 复制环境配置文件
cp .env.docker .env

# 编辑 .env 文件，填写必要的配置信息
# 特别注意需要修改以下配置项：
# - PROD_SECRET_KEY: 生产环境密钥，请使用随机字符串
# - CAPTCHA_URL: 验证码服务地址
# - FRONTEND_URLS: 前端应用的URL
```

### 2. 启动服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 访问应用

- 应用主服务: http://localhost:5000
- 数据库: localhost:5432

## 服务说明

### web 服务
- 主要的 Flask 应用服务，使用 Gunicorn 作为 WSGI 服务器
- 端口: 5000
- 自动执行数据库迁移
- 支持多进程并发处理，提供更好的性能和稳定性

### task-worker 服务  
- 后台任务处理服务
- 处理异步任务如考试数据抓取等

### db 服务
- PostgreSQL 数据库
- 端口: 5432
- 数据持久化存储

## 常用命令

```bash
# 停止服务
docker-compose down

# 重新构建并启动
docker-compose up -d --build

# 查看特定服务日志
docker-compose logs -f web
docker-compose logs -f task-worker

# 进入容器内部
docker-compose exec web bash

# 执行数据库迁移
docker-compose exec web flask db upgrade

# 清理数据和重启
docker-compose down -v
docker-compose up -d
```

## 注意事项

1. 首次启动前确保修改 `.env` 文件中的敏感配置
2. 生产环境请使用强密码和安全的密钥
3. 日志和缓存文件会挂载到宿主机的 `./logs` 和 `./cache` 目录
4. 数据库数据持久化存储在 Docker volume 中
5. 应用使用 Gunicorn 作为 WSGI 服务器，提供更好的生产环境性能

## Gunicorn 配置

项目使用 Gunicorn 作为 WSGI 服务器，配置文件为 `gunicorn.conf.py`。主要配置包括：

- **进程数量**: CPU 核数 * 2 + 1，自动优化并发性能
- **超时设置**: 30秒请求超时，适合处理复杂业务逻辑
- **日志管理**: 独立的访问日志和错误日志
- **连接管理**: 支持 Keep-Alive，提升连接复用
- **优雅重启**: 支持零停机更新

可以根据实际需求修改 `gunicorn.conf.py` 中的配置参数。