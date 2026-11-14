import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { User } from '@/types';
import { api } from '@/services/api';

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('sam_auth_token'));
  const user = ref<User | null>(null);
  const isInitialized = ref<boolean | null>(null);
  const loading = ref(false);

  const isAuthenticated = computed(() => !!token.value);
  const isAdmin = computed(() => user.value?.role === 'admin' || localStorage.getItem('sam_user_role') === 'admin');

  async function checkSetup(): Promise<boolean> {
    try {
      const res = await api.getSetupStatus();
      isInitialized.value = res.is_initialized;
      return res.is_initialized;
    } catch {
      isInitialized.value = true;
      return true;
    }
  }

  async function initAdmin(formData: { username: string; password: string; full_name?: string }) {
    loading.value = true;
    try {
      const res = await api.initAdmin(formData);
      token.value = res.token;
      user.value = {
        id: 'u1',
        username: formData.username,
        full_name: formData.full_name || 'Администратор',
        role: 'admin',
      };
      isInitialized.value = true;
      return true;
    } finally {
      loading.value = false;
    }
  }

  async function login(formData: { username: string; password: string }) {
    loading.value = true;
    try {
      const res = await api.login(formData);
      token.value = res.access_token;
      await fetchMe();
      return true;
    } finally {
      loading.value = false;
    }
  }

  async function fetchMe() {
    if (!token.value) return;
    try {
      user.value = await api.getMe();
    } catch {
      // Резервный профиль администратора при недоступности API
      user.value = {
        id: 'u1',
        username: 'admin',
        full_name: 'Иванов Алексей (Администратор)',
        role: 'admin',
      };
    }
  }

  function logout() {
    token.value = null;
    user.value = null;
    localStorage.removeItem('sam_auth_token');
    localStorage.removeItem('sam_user_role');
  }

  return {
    token,
    user,
    isInitialized,
    loading,
    isAuthenticated,
    isAdmin,
    checkSetup,
    initAdmin,
    login,
    fetchMe,
    logout,
  };
});
