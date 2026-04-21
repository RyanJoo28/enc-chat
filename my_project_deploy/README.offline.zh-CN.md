# Enc Chat 离线部署

Language / 语言: [English](README.offline.md) | **简体中文**

本说明适用于无法从 GHCR 拉取镜像的离线或受限网络环境。

## 离线镜像标签

发布包 `enc-chat-release.tar` 内包含以下本地镜像标签：

- `enc-chat-docker-backend:latest`
- `enc-chat-docker-frontend:latest`

## 环境要求

- Docker Engine 或 Docker Desktop
- Docker Compose v2
- `enc-chat-release.tar`

## 快速启动

先创建部署环境文件：

```bash
cp .env.example .env
```

然后在 `.env` 中指定离线导入后的本地镜像标签：

```env
BACKEND_IMAGE=enc-chat-docker-backend:latest
FRONTEND_IMAGE=enc-chat-docker-frontend:latest
```

加载离线镜像包：

```bash
docker load -i enc-chat-release.tar
```

在不访问 GHCR 的情况下启动服务：

```bash
docker compose up -d
```

或者使用离线模式的辅助脚本：

```bash
./start.sh offline
```

Windows：

```bat
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

- 如果缺少 `.env`，`start.sh` 和 `start.bat` 会自动根据 `.env.example` 创建默认配置
- 部署包默认使用 `COMPOSE_PROJECT_NAME=enc-chat-release`，避免复用开发环境的 Docker volumes
- 离线模式下不要运行 `docker compose pull`
- `./start.sh offline` 和 `start.bat offline` 会自动加载 `enc-chat-release.tar`，并强制使用离线包内的本地镜像标签
- 如果 `.env` 中没有设置 `BACKEND_IMAGE` 和 `FRONTEND_IMAGE`，Docker Compose 会回退到 `docker-compose.yml` 中的 GHCR 镜像地址
- 应用和数据库数据保存在 Docker volumes 中
