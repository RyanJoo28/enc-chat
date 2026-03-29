#!/bin/sh
set -eu

# 在前端容器首次启动时生成本地自签名证书。
CERT_DIR="${TLS_CERT_DIR:-/etc/nginx/certs}"
CERT_FILE="${TLS_CERT_FILE:-${CERT_DIR}/local-cert.pem}"
KEY_FILE="${TLS_KEY_FILE:-${CERT_DIR}/local-key.pem}"
TLS_COMMON_NAME="${TLS_COMMON_NAME:-localhost}"
TLS_DOMAINS="${TLS_DOMAINS:-localhost,127.0.0.1}"
TLS_CERT_DAYS="${TLS_CERT_DAYS:-825}"

# 证书目录持久化到 volume，避免每次重建容器都重新签发。
mkdir -p "${CERT_DIR}"

if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
  exit 0
fi

OPENSSL_CONFIG="$(mktemp)"

# 生成带 SAN 的 openssl 配置。
cat > "${OPENSSL_CONFIG}" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${TLS_COMMON_NAME}

[v3_req]
subjectAltName = @alt_names

[alt_names]
EOF

dns_index=1
ip_index=1
old_ifs="${IFS}"
IFS=','
set -- ${TLS_DOMAINS}
IFS="${old_ifs}"

# 根据域名/IP 列表写入 SAN。
for entry in "$@"; do
  value="$(printf '%s' "${entry}" | tr -d ' ')"
  if [ -z "${value}" ]; then
    continue
  fi

  case "${value}" in
    *[!0-9.]*)
      printf 'DNS.%s = %s\n' "${dns_index}" "${value}" >> "${OPENSSL_CONFIG}"
      dns_index=$((dns_index + 1))
      ;;
    *)
      printf 'IP.%s = %s\n' "${ip_index}" "${value}" >> "${OPENSSL_CONFIG}"
      ip_index=$((ip_index + 1))
      ;;
  esac
done

# 首次启动时生成自签名证书。
openssl req -x509 -nodes -newkey rsa:2048 \
  -days "${TLS_CERT_DAYS}" \
  -keyout "${KEY_FILE}" \
  -out "${CERT_FILE}" \
  -config "${OPENSSL_CONFIG}"

chmod 600 "${KEY_FILE}"
rm -f "${OPENSSL_CONFIG}"
