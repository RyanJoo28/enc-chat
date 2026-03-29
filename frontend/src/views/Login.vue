<template>
  <div class="tg-login-bg">
    <div class="tg-card">

      <div class="lang-switch-wrapper" @click="toggleLanguage" :title="t('switchLangTip')">
        <svg class="lang-icon" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
          <rect
              x="0"
              y="0"
              width="48"
              height="48"
              rx="14"
              :fill="currentLang === 'zh' ? '#ff5252' : '#3390ec'"
              class="bg-rect"
          />

          <g v-if="currentLang === 'en'" fill="white">
            <path d="M14 16h10v3h-7v4h6v3h-6v5h7v3h-10z"/>
            <path
                d="M26 19h3v1.5a3.5 3.5 0 0 1 3-1.5c2.5 0 4 1.8 4 4.5v10.5h-3v-10c0-1.5-.8-2.3-2.2-2.3-1.5 0-2.5 1-2.5 2.8v9.5h-3z"/>
          </g>

          <g v-else fill="white" transform="translate(11, 11) scale(1.1)">
            <path d="M2 4h20v13h-20z m17 10v-7h-14v7z" fill-rule="evenodd"/>
            <path d="M10.5 0v24h3v-24z"/>
          </g>
        </svg>
      </div>

      <div class="tg-logo-wrapper">
        <svg class="tg-logo" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
          <circle cx="120" cy="120" r="120" fill="#3390ec"/>
          <g transform="translate(48, 48) scale(0.6)">
            <path
                d="M120 0C53.73 0 0 49.25 0 110c0 33.36 16.35 63.2 41.96 83.13-2.15 14.88-10.32 30.58-25.26 38.35 34.36 1.76 59.83-13.9 73.18-24.96C99.27 209.15 109.43 210 120 210c66.27 0 120-49.25 120-110S186.27 0 120 0z"
                fill="#ffffff"/>
            <path
                d="M120 55c-16.57 0-30 13.43-30 30v20h-5c-5.52 0-10 4.48-10 10v50c0 5.52 4.48 10 10 10h70c5.52 0 10-4.48 10-10v-50c0-5.52-4.48-10-10-10h-5V85c0-16.57-13.43-30-30-30zm0 15c8.28 0 15 6.72 15 15v20h-30V85c0-8.28 6.72-15 15-15zm0 52c4.42 0 8 3.58 8 8s-3.58 8-8 8-8-3.58-8-8 3.58-8 8-8z"
                fill="#3390ec"/>
          </g>
        </svg>
      </div>

      <h2 class="tg-title">{{ isLogin ? t('loginTitle') : t('registerTitle') }}</h2>
      <p class="tg-subtitle">
        {{ isLogin ? t('loginSubtitle') : t('registerSubtitle') }}
      </p>

      <div class="tg-form">
        <div class="input-group">
          <el-input
              v-model="form.username"
              :placeholder="t('username')"
              size="large"
              class="tg-input"
          />
        </div>

        <div class="input-group">
          <el-input
              v-model="form.password"
              type="password"
              :placeholder="t('password')"
              show-password
              size="large"
              class="tg-input"
              @keydown.enter.prevent="handleSubmit"
          />
        </div>

        <div v-if="!isLogin" class="input-group">
          <el-input
              v-model="form.confirmPassword"
              type="password"
              :placeholder="t('confirmPassword')"
              show-password
              size="large"
              class="tg-input"
              @keydown.enter.prevent="handleSubmit"
          />
        </div>

        <button class="tg-btn" type="button" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? (isLogin ? t('loggingIn') : t('registering')) : (isLogin ? t('loginBtn') : t('registerBtn')) }}
        </button>

        <div class="tg-footer">
          <a class="tg-link" @click="toggleMode">
            {{ isLogin ? t('toRegister') : t('toLogin') }}
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {onMounted, reactive, ref} from 'vue';
import axios from 'axios';
import {useRouter} from 'vue-router';
import {ElMessage} from 'element-plus';
import {API_ORIGIN} from '../utils/runtime';
import {loginWithPassword, refreshSession} from '../utils/auth';

const API_BASE = `${API_ORIGIN}/api/user`;
const router = useRouter();
const isLogin = ref(true);
const submitting = ref(false);

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
});

// 界面文案
const savedLang = localStorage.getItem('app_lang');
const currentLang = ref(savedLang || 'en');

const translations = {
  en: {
    loginTitle: 'Sign in to Encrypted Chat',
    registerTitle: 'Sign up',
    loginSubtitle: 'Please enter your username and password.',
    registerSubtitle: 'Create an account to start messaging.',
    username: 'Username',
    password: 'Password',
    loginBtn: 'LOG IN',
    loggingIn: 'LOGGING IN...',
    registerBtn: 'REGISTER',
    registering: 'REGISTERING...',
    toRegister: "Don't have an account? Sign up",
    toLogin: "Already have an account? Log in",
    switchLangTip: 'Switch to Chinese',
    inputEmpty: 'Please enter username and password',
    loginSuccess: 'Login successful',
    registerSuccess: 'Registration successful, please login',
    networkError: 'Network error, cannot connect to server',
    requestFailed: 'Request failed',
    serverError: 'Server error',
    confirmPassword: 'Confirm Password',
    passwordMismatch: 'Passwords do not match',
  },
  zh: {
    loginTitle: '登录加密聊天',
    registerTitle: '注册账号',
    loginSubtitle: '请输入您的用户名和密码。',
    registerSubtitle: '创建一个账号以开始加密通信。',
    username: '用户名',
    password: '密码',
    loginBtn: '登 录',
    loggingIn: '登录中...',
    registerBtn: '注 册',
    registering: '注册中...',
    toRegister: "还没有账号？去注册",
    toLogin: "已有账号？去登录",
    switchLangTip: '切换为英文',
    inputEmpty: '请输入用户名和密码',
    loginSuccess: '登录成功',
    registerSuccess: '注册成功，请登录',
    networkError: '网络错误，无法连接服务器',
    requestFailed: '请求失败',
    serverError: '服务器内部错误',
    confirmPassword: '确认密码',
    passwordMismatch: '两次输入的密码不一致',
  }
};

const t = (key) => translations[currentLang.value][key];

// 后端错误文案映射，仅在英文界面下使用。
const backendErrorTranslations = {
  '密码长度不能少于 8 位': 'Password must be at least 8 characters',
  '密码必须包含至少一个大写字母': 'Password must contain at least one uppercase letter',
  '密码必须包含至少一个小写字母': 'Password must contain at least one lowercase letter',
  '密码必须包含至少一个数字': 'Password must contain at least one number',
  '密码必须包含至少一个特殊字符 (如 @, #, $ 等)': 'Password must contain at least one special character (@, #, $, etc.)',

  '用户名或密码错误': 'Incorrect username or password',
  '注册失败，该用户名可能已存在': 'Registration failed, username may already exist',
  'Token 已失效 (已注销)': 'Token expired or logged out'
};

const translateError = (msg) => {
  if (currentLang.value === 'zh') return msg;
  if (backendErrorTranslations[msg]) {
    return backendErrorTranslations[msg];
  }
  return msg;
};

const toggleLanguage = () => {
  currentLang.value = currentLang.value === 'en' ? 'zh' : 'en';
  localStorage.setItem('app_lang', currentLang.value);
};

const toggleMode = () => {
  isLogin.value = !isLogin.value;
  form.username = '';
  form.password = '';
  form.confirmPassword = '';
};

onMounted(async () => {
  try {
    await refreshSession();
    await navigateToChat();
  } catch {
    // 未登录时保持在登录页。
  }
});

const navigateToChat = async () => {
  const chatHref = router.resolve('/chat').href;
  window.location.replace(chatHref);
};

const handleSubmit = async () => {
  if (submitting.value) {
    return;
  }
  if (!form.username || !form.password) {
    ElMessage.warning(t('inputEmpty'));
    return;
  }


  if (!isLogin.value) {
    if (!form.confirmPassword) {
      ElMessage.warning(t('inputEmpty'));
      return;
    }
    if (form.password !== form.confirmPassword) {
      ElMessage.error(t('passwordMismatch'));
      return;
    }
  }

  submitting.value = true;
  try {
    if (isLogin.value) {
      await loginWithPassword({
        username: form.username,
        password: form.password
      });

      ElMessage.success(t('loginSuccess'));
      await navigateToChat();

    } else {
      await axios.post(`${API_BASE}/register`, {
        username: form.username,
        password: form.password
      });

      ElMessage.success(t('registerSuccess'));
      isLogin.value = true;
    }
  } catch (error) {
    console.error(error);
    if (error.response) {
      const {status, data} = error.response;

      // 422 响应中的 detail 是 Pydantic 验证数组。
      if (status === 422 && Array.isArray(data.detail)) {
        const firstError = data.detail[0];
        let msg = firstError.msg;
        if (msg.startsWith('Value error, ')) {
          msg = msg.replace('Value error, ', '');
        }
        ElMessage.error(translateError(msg));
      } else if (data && data.detail) {
        ElMessage.error(translateError(data.detail));
      } else {
        ElMessage.error(t('requestFailed'));
      }
    } else {
      ElMessage.error(t('networkError'));
    }
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.tg-login-bg {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.tg-card {
  position: relative;
  background: white;
  width: 100%;
  max-width: 380px;
  padding: 48px 36px;
  border-radius: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  text-align: center;
  transition: all 0.3s ease;
}

/* 语言切换按钮 */
.lang-switch-wrapper {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 32px;
  height: 32px;
  cursor: pointer;
  transition: transform 0.2s, opacity 0.2s;
  opacity: 0.8;
}

.lang-switch-wrapper:hover {
  transform: scale(1.1);
  opacity: 1;
}

.lang-icon {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.15));
}

.bg-rect {
  transition: fill 0.3s ease;
}

.tg-logo-wrapper {
  margin-bottom: 24px;
}

.tg-logo {
  width: 120px;
  height: 120px;
}

.tg-title {
  font-size: 26px;
  font-weight: 700;
  color: #000;
  margin-bottom: 12px;
}

.tg-subtitle {
  font-size: 16px;
  color: #707579;
  margin-bottom: 36px;
  line-height: 1.5;
}

.tg-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tg-input :deep(.el-input__wrapper) {
  padding: 12px 15px;
  border-radius: 12px;
  box-shadow: 0 0 0 1px #dfe1e5 inset;
  transition: all 0.2s;
}

.tg-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #3390ec inset !important;
}

.tg-input :deep(.el-input__inner) {
  font-size: 16px;
  height: 24px;
}

.tg-btn {
  background-color: #3390ec;
  color: white;
  border: none;
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 12px;
  cursor: pointer;
  text-transform: uppercase;
  transition: background-color 0.2s, transform 0.1s;
  width: 100%;
  margin-top: 10px;
}

.tg-btn:hover {
  background-color: #2b7fc7;
}

.tg-btn:active {
  transform: scale(0.98);
}

.tg-footer {
  margin-top: 16px;
}

.tg-link {
  color: #3390ec;
  text-decoration: none;
  font-size: 15px;
  cursor: pointer;
}

.tg-link:hover {
  text-decoration: underline;
}

@media (max-width: 480px) {
  .tg-card {
    box-shadow: none;
    background: transparent;
  }

  .tg-login-bg {
    background: white;
  }
}
</style>
