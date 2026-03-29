#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "正在把打包好的镜像加载到本地 Docker 中..."
docker load -i enc-chat-release.tar

echo "镜像加载完成！正在通过 docker compose 启动服务..."
docker compose up -d

echo "======================================="
echo "容器已在后台启动！"
echo "如果您需要查看日志，请运行: docker compose logs -f"
echo "默认访问地址: https://localhost:23456"
echo "部署完成！"
echo "======================================="
