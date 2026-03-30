<div align="center">

# Enc-Chat: 端到端加密即时通讯系统
[![Playwright E2E](https://img.shields.io/badge/playwright-tested-brightgreen.svg)](e2e/tests)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100.0-009688.svg?logo=fastapi)](backend)
[![Vue3](https://img.shields.io/badge/Vue.js-3.0-4FC08D.svg?logo=vue.js)](frontend)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED.svg?logo=docker)](docker-compose.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

一个高性能、纯端到端加密（E2EE）的实时通讯应用。基于 Signal 协议准则（双棘轮算法）构建。

<br>

🌐 Language / 语言 <br>
[English](README.md) | **简体中文**

</div>

---

## 🔒 核心安全架构
Enc-Chat 确保服务器**绝不会**破解或窃取消息、图片、文件的明文内容。服务器仅仅扮演着“透明路由”和信封中转站的角色。

- **端到端私聊与群聊加密**：采用 AES-256-GCM 消息加密并结合 RSA 密钥交换。群组聊天基于 Sender Keys，映射至广播套接字，并保证前向安全性（PFS）。
- **浏览器双棘轮加密机制**：直接基于前端 `window.crypto.subtle` 实现，确保会话状态在浏览器端绝对隔离。
- **临时密钥与 PFS**：使用 HKDF（基于 HMAC 的密钥派生），针对每个逻辑通信阶段滚动更新离线密钥。
- **纯内存处理加密信封**：服务器不仅脱敏化所有的载荷，客户端解密后，明文也仅短暂留存于本地内存中。
- **真正的多设备验证**：支持用户在 PC 桌面端和移动端并行登录认证，所有设备皆可使用同步密钥解密相应的分支流。
- **DevOps 自动化与回滚测试**：提供零污染的灰度和容灾回滚实机演练支持，并通过了极为严苛的大规模“撤回/设备踢除” E2E 回归测试 (`F9` 里程碑验证通过)。

## 🚀 快速启动（通过 Docker）

整套环境（包含 NGINX 前端入口、FastAPI 后端、MySQL 核心）已高度容器化，开箱即用：

```bash
# 1. 复制环境变量配置文件
cp docker/.env.example docker/.env

# 2. 编译并启动所有服务环境
docker-compose --env-file docker/.env up -d --build

# 3. 访问本地安全 UI
https://localhost:23456
```

## 📦 通过 GHCR 部署发布版

`my_project_deploy/` 目录下的部署包会从 GitHub Container Registry (GHCR) 拉取预构建镜像。`docker-compose.yml` 支持通过 `BACKEND_IMAGE` 和 `FRONTEND_IMAGE` 覆盖镜像地址，因此同一套部署文件既可以用于上游仓库，也可以用于 fork 或私有重新发布的镜像。

如果你只需要查看部署说明，请直接参考 `my_project_deploy/README.md`。
如果你需要使用发布归档进行离线部署，请参考 `my_project_deploy/README.offline.zh-CN.md`。

```bash
# 可选：先复制部署环境模板，再按需修改镜像覆盖项
cp my_project_deploy/.env.example my_project_deploy/.env

# 如果镜像还是 private，需要先使用带 read:packages 权限的 classic PAT 登录
echo "$CR_PAT" | docker login ghcr.io -u <github-username> --password-stdin

cd my_project_deploy
docker compose pull
docker compose up -d

# 或直接使用辅助脚本
./start.sh
# Windows: start.bat
```

镜像命名约定：

- `ghcr.io/<github-namespace>/enc-chat-backend:<tag>`
- `ghcr.io/<github-namespace>/enc-chat-frontend:<tag>`

说明：

- 如果没有设置 `BACKEND_IMAGE` 和 `FRONTEND_IMAGE`，Docker Compose 会使用 `my_project_deploy/docker-compose.yml` 中提交的默认镜像值。
- 公有 GHCR 镜像可以匿名拉取；私有 GHCR 镜像需要先执行 `docker login ghcr.io`。

停止发布栈：

```bash
cd my_project_deploy
docker compose down
```

## 📂 项目结构概览 (Monorepo)

```text
├── backend/                  # FastAPI & SQLAlchemy 数据库引擎
│   ├── app/e2ee/             # Python E2EE 路由及广播系统
│   ├── app/chat/             # WebSocket 长连多通道管理器
│   └── tests/                # Pytest 单元/接口测试环境
├── frontend/                 # Vue 3 Vite PWA
│   ├── src/views/            # 核心端到端加密通讯聊天室界面
│   ├── src/utils/e2ee/       # WebCrypto 浏览器密文引擎
│   └── src/components/       # UI 组件和覆盖配置
├── e2e/                      # Playwright 全链路集成测试
│   ├── tests/F9-02-chat      # 核心私聊与群组密文同步用例
│   ├── tests/F9-08-load      # 50 人大规模并发成员压力测试
│   └── tests/F9-09-recall    # 并发消息撤回安全断言测试
└── docker/                   # 容灾回滚、灰度发布、容器编排配置
```

## 🧪 E2E 端到端自动化测试

我们在 `e2e` 目录下构建了一套健壮的无头 Chromium 测试流水线，提供基于本地数据库节点的并行测试。

```bash
# 进入测试目录（此处为绝对路径示例）
cd d:\jetbrains_proj\pycharm_proj\enc_chat_proj\e2e
# 如果尚未安装依赖项，请先执行安装
npm ci

# 启动包括密聊、媒体、设备踢人、负载在内的 F9 核心测试用例
npx playwright test --project=chromium --reporter=list
```

### 容灾回滚演练脚本测试
如果在测试中需要验证独立的数据库回滚和无缝恢复，可在项目根目录通过以下命令执行灰度演练脚本：
```bash
# 注意：如果您在 Windows PowerShell 中执行，请务必带上 bash 命令前缀
bash docker/rollback_drill.sh
```

## 📄 开源许可证 (License)

本项目采用 **GNU Affero General Public License v3.0 (AGPLv3)** 协议开源。
这意味着任何基于此代码修改并提供网络服务的平台（即便是以 SaaS 云端或后端形式提供服务，不分发客户端），都必须公开其修改后的完整源代码。关于详细的条款限制，请参阅项目根目录下的 [LICENSE](LICENSE) 文件。
> 所有 E2E UI 自动化脚本在运行时，都会利用浏览器本地硬件真正地执行 RSA 密钥生成与注册流程。

## 🧰 技术栈组成
- **数据库驱动**: MySQL 8.4
- **后端架构**: Python 3.12+ (必需), FastAPI, SQLAlchemy, Uvicorn (WebSockets)
- **前端架构**: Vue 3 (Composition API), Vite, Element Plus, Axios. 环境要求：`Node.js ^20.19.0` 或 `>=22.12.0`
- **容器与 E2E**: Playwright Chromium, Docker Compose（隔离级建库）

## 📸 项目实机演示截图

<div align="center">

![Enc-Chat 界面总览](screenshots/merged.png)

*登录注册 · 私密端到端加密聊天 · 群组聊天 · 好友请求与通知*

</div>

## 🛠️ 项目测试环境修改与复现说明 (TEST MODIFICATIONS)

在 F9 里程碑（端到端双棘轮加密、群聊并发、多设备、容灾等）开发与测试期间，为了满足极限吞吐负载的要求，我们在配置层针对高并发进行了非侵入式调整：

### 1. 修改了后端速率限制 (`backend/.env`)
* **修改详情**：单用户 WebSocket 被放宽：`WS_MAX_MESSAGES_PER_MINUTE=500`。
* **修改原因**：由于 `F9-08` 测试中引入了大量的“并发离线消息拉取同步”测试用例（Inbox Retrieval），若使用默认限频，瞬时大规模刷新容易立刻触发 `429 Too Many Requests`，造成 WebSocket 直接被断开。
* **如何恢复生产安全基线**：如果您想阻止恶意刷接口的客户端，请把 `backend/.env` 里的值调回 `60` 以内。

### 2. 独立集成了灰度和回滚测试容器栈 (`docker-compose.canary.yml`)
* **修改详情**：为避免 `rollback_drill.sh` 测试暴力恢复数据库时污染开发者本地正在开发并挂载的 `enc_chat_db`，我们新建了通过 `23457` 端口隔离映射的独立 Canary 环境。
* **如何恢复**：测试完毕后执行 `docker compose -f docker/docker-compose.canary.yml down -v` ，清理掉所有为灰度测试而占用的无头容器卷及端口。

### 3. 如何在新的 CI 机器上保证全量 E2E 满分通过
如果您或您的团队在新机器里部署并进行回归测试，请确保：`WS_MAX_MESSAGES_PER_MINUTE` 不低于 500、确保后端没有撤掉 `--ssl-keyfile`（以开启 wss 测试连接），随后在 `e2e` 下方执行指令即可。
