#!/bin/sh
set -eu

# 为后端准备运行目录，并在缺省情况下生成持久化密钥。
APP_DATA_DIR="${APP_DATA_DIR:-/data}"
APP_LOG_PATH="${APP_LOG_PATH:-${APP_DATA_DIR}/app.log}"
SERVER_PRIVATE_KEY_FILE="${SERVER_PRIVATE_KEY_FILE:-${APP_DATA_DIR}/server_private.pem}"

SECRET_DIR="${APP_DATA_DIR}/secrets"
JWT_SECRET_FILE="${SECRET_DIR}/jwt_secret.hex"
DB_KEY_FILE="${SECRET_DIR}/db_encryption_key.hex"

# 生成 32 字节随机十六进制密钥。
generate_hex() {
  python - <<'PY'
import secrets

print(secrets.token_hex(32))
PY
}

# 准备运行目录和日志文件。
mkdir -p "${SECRET_DIR}" "$(dirname "${APP_LOG_PATH}")" "$(dirname "${SERVER_PRIVATE_KEY_FILE}")"
touch "${APP_LOG_PATH}"

# 若未注入密钥，则从 volume 中读取或首次生成。
if [ -z "${JWT_SECRET_KEY:-}" ]; then
  if [ -f "${JWT_SECRET_FILE}" ]; then
    JWT_SECRET_KEY="$(cat "${JWT_SECRET_FILE}")"
  else
    JWT_SECRET_KEY="$(generate_hex)"
    printf '%s' "${JWT_SECRET_KEY}" > "${JWT_SECRET_FILE}"
  fi
fi

if [ -z "${DB_ENCRYPTION_KEY:-}" ]; then
  if [ -f "${DB_KEY_FILE}" ]; then
    DB_ENCRYPTION_KEY="$(cat "${DB_KEY_FILE}")"
  else
    DB_ENCRYPTION_KEY="$(generate_hex)"
    printf '%s' "${DB_ENCRYPTION_KEY}" > "${DB_KEY_FILE}"
  fi
fi

if [ -f "${JWT_SECRET_FILE}" ]; then
  chmod 600 "${JWT_SECRET_FILE}"
fi

if [ -f "${DB_KEY_FILE}" ]; then
  chmod 600 "${DB_KEY_FILE}"
fi

# 将运行所需配置导出给应用进程。
export JWT_SECRET_KEY DB_ENCRYPTION_KEY APP_DATA_DIR APP_LOG_PATH SERVER_PRIVATE_KEY_FILE

exec "$@"
