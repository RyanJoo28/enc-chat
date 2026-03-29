import axios from 'axios';

import {API_ORIGIN} from './runtime';

const USER_API_BASE = `${API_ORIGIN}/api/user`;

let accessToken = '';
let accessPayload = null;
let refreshPromise = null;

const emitAuthChanged = (payload = {}) => {
  window.dispatchEvent(new CustomEvent('auth:changed', {detail: payload}));
};

const decodeJwtPayload = (token) => {
  if (!token) return null;

  try {
    const base64Url = token.split('.')[1] || '';
    const base64 = base64Url
      .replace(/-/g, '+')
      .replace(/_/g, '/')
      .padEnd(Math.ceil(base64Url.length / 4) * 4, '=');
    return JSON.parse(atob(base64));
  } catch (error) {
    console.error(error);
    return null;
  }
};

const syncAxiosAuthHeader = () => {
  if (accessToken) {
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
  } else {
    delete axios.defaults.headers.common.Authorization;
  }
};

export const setAccessToken = (token) => {
  accessToken = token || '';
  accessPayload = decodeJwtPayload(accessToken);
  syncAxiosAuthHeader();
  return accessToken;
};

export const getAccessToken = () => accessToken;

export const getAccessPayload = () => accessPayload;

export const updateStoredProfile = (payload = {}) => {
  if (payload.username) {
    localStorage.setItem('username', payload.username);
  }

  if (payload.avatar) {
    localStorage.setItem('avatar', payload.avatar);
  } else if (Object.prototype.hasOwnProperty.call(payload, 'avatar')) {
    localStorage.removeItem('avatar');
  }
};

export const clearAuthState = () => {
  setAccessToken('');
  localStorage.removeItem('username');
  localStorage.removeItem('avatar');
  emitAuthChanged({});
};

export const applyAuthResponse = (payload = {}) => {
  setAccessToken(payload.access_token || payload.token || '');
  updateStoredProfile(payload);
  emitAuthChanged(payload);
  return payload;
};

export const loginWithPassword = async ({username, password}) => {
  const response = await axios.post(
    `${USER_API_BASE}/login`,
    {username, password},
    {withCredentials: true}
  );
  return applyAuthResponse(response.data);
};

export const refreshSession = async () => {
  const response = await axios.post(
    `${USER_API_BASE}/refresh`,
    {},
    {withCredentials: true}
  );
  return applyAuthResponse(response.data);
};

export const ensureAccessToken = async () => {
  if (accessToken) return accessToken;

  const payload = await refreshSession();
  return payload.access_token || payload.token || '';
};

export const logoutSession = async () => {
  try {
    await axios.post(
      `${USER_API_BASE}/logout`,
      {},
      {
        withCredentials: true,
        headers: accessToken ? {Authorization: `Bearer ${accessToken}`} : {},
      }
    );
  } finally {
    clearAuthState();
  }
};

const isAuthManagementRequest = (url = '') => {
  return url.includes('/api/user/login') || url.includes('/api/user/refresh') || url.includes('/api/user/logout');
};

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (!error.response || !originalRequest || originalRequest._retry || isAuthManagementRequest(originalRequest.url || '')) {
      return Promise.reject(error);
    }

    if (error.response.status !== 401) {
      return Promise.reject(error);
    }

    try {
      originalRequest._retry = true;
      if (!refreshPromise) {
        refreshPromise = refreshSession().finally(() => {
          refreshPromise = null;
        });
      }
      await refreshPromise;
      originalRequest.headers = {
        ...(originalRequest.headers || {}),
        Authorization: `Bearer ${getAccessToken()}`,
      };
      return axios(originalRequest);
    } catch (refreshError) {
      clearAuthState();
      return Promise.reject(refreshError);
    }
  }
);
