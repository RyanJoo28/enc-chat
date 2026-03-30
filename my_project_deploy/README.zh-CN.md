# Enc Chat 部署包

Language / 语言: [English](README.md) | **简体中文**

本目录提供基于 GHCR 的在线部署说明。

如果你需要使用 `enc-chat-release.tar` 进行离线部署，请参考 `README.offline.zh-CN.md`。

## 文件说明

- `docker-compose.yml`: 部署栈定义
- `.env.example`: 部署环境变量模板
- `start.sh`: Linux/macOS 启动脚本
- `start.bat`: Windows 启动脚本

## 环境要求

- Docker Engine 或 Docker Desktop
- Docker Compose v2

## 快速启动

```bash
cp .env.example .env
```

如果你想使用自己发布的 GHCR 镜像，请编辑 `.env` 并设置：

```env
BACKEND_IMAGE=ghcr.io/<github-namespace>/enc-chat-backend:<tag>
FRONTEND_IMAGE=ghcr.io/<github-namespace>/enc-chat-frontend:<tag>
```

如果镜像是私有的，请先登录：

```bash
echo "$CR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

启动部署栈：

```bash
docker compose pull
docker compose up -d
```

或者直接使用辅助脚本：

```bash
# 在线模式（默认）
./start.sh

# 使用 enc-chat-release.tar 的离线模式
./start.sh offline
```

Windows：

```bat
REM 在线模式（默认）
start.bat

REM 使用 enc-chat-release.tar 的离线模式
start.bat offline
```

默认访问地址：

```text
https://localhost:23456
```

## 停止服务

```bash
docker compose down
```

## 查看日志

```bash
docker compose logs -f
```

## 说明

- 默认启动脚本会从 GHCR 拉取镜像；如果要使用离线包，请运行 `./start.sh offline` 或 `start.bat offline`
- 公有 GHCR 镜像可匿名拉取；私有镜像需要先执行 `docker login ghcr.io`
- 应用和数据库数据保存在 Docker volumes 中
