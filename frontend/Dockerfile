FROM node:20-alpine AS build

WORKDIR /app

# 构建阶段
# 构建前端静态资源。
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# 运行阶段
# 运行阶段使用 Nginx 并生成本地 TLS 证书。
RUN apk add --no-cache openssl

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.d/40-generate-local-tls.sh

RUN chmod +x /docker-entrypoint.d/40-generate-local-tls.sh \
    && mkdir -p /etc/nginx/certs

EXPOSE 443
