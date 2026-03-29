// 统一解析前端访问后端 API 和 WebSocket 的地址。
const trimTrailingSlash = (value) => value.replace(/\/+$/, '');

const getApiOrigin = () => {
  const configuredOrigin = import.meta.env.VITE_API_ORIGIN?.trim();
  if (configuredOrigin) {
    return trimTrailingSlash(configuredOrigin);
  }

  if (import.meta.env.DEV) {
    return trimTrailingSlash(window.location.origin);
  }

  return trimTrailingSlash(window.location.origin);
};

const getWsOrigin = () => {
  const configuredOrigin = import.meta.env.VITE_WS_ORIGIN?.trim();
  if (configuredOrigin) {
    return trimTrailingSlash(configuredOrigin);
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};

export const API_ORIGIN = getApiOrigin();
export const WS_ORIGIN = getWsOrigin();
