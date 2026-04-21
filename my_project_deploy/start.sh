#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

mode=${1:-online}

case "$mode" in
  online|offline)
    ;;
  *)
    echo "用法: $0 [offline]"
    echo "默认模式会从 GHCR 拉取镜像；offline 模式会从 enc-chat-release.tar 加载离线镜像。"
    exit 1
    ;;
esac

backend_image_override=""
frontend_image_override=""

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "未检测到 .env，已根据 .env.example 创建默认配置。"
fi

if [ -f ".env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      BACKEND_IMAGE=*)
        backend_image_override=${line#BACKEND_IMAGE=}
        ;;
      FRONTEND_IMAGE=*)
        frontend_image_override=${line#FRONTEND_IMAGE=}
        ;;
    esac
  done < .env

  if [ -n "$backend_image_override" ] || [ -n "$frontend_image_override" ]; then
    echo "检测到 .env 中配置了自定义镜像："
    [ -n "$backend_image_override" ] && echo "  BACKEND_IMAGE=$backend_image_override"
    [ -n "$frontend_image_override" ] && echo "  FRONTEND_IMAGE=$frontend_image_override"
  fi
fi

if [ "$mode" = "offline" ]; then
  offline_backend_image="enc-chat-docker-backend:latest"
  offline_frontend_image="enc-chat-docker-frontend:latest"

  if [ -n "$backend_image_override" ] || [ -n "$frontend_image_override" ]; then
    echo "检测到 .env 中配置了自定义镜像，但 offline 模式将使用离线包内的本地镜像标签。"
  fi

  if [ ! -f "enc-chat-release.tar" ]; then
    echo "未找到 enc-chat-release.tar，无法执行离线部署。"
    exit 1
  fi

  echo "正在从 enc-chat-release.tar 加载离线镜像..."
  docker load -i enc-chat-release.tar

  echo "离线镜像加载完成！正在通过 docker compose 启动服务..."
  BACKEND_IMAGE="$offline_backend_image" FRONTEND_IMAGE="$offline_frontend_image" docker compose up -d
else
  echo "正在从 GHCR 拉取镜像..."
  docker compose pull

  echo "镜像拉取完成！正在通过 docker compose 启动服务..."
  docker compose up -d
fi

echo "======================================="
echo "容器已在后台启动！"
echo "如果您需要查看日志，请运行: docker compose logs -f"
echo "默认访问地址: https://localhost:23456"
echo "部署完成！"
echo "======================================="
