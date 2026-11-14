<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { Shield, Lock, User, ArrowRight } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Input from '@/components/ui/Input.vue';

const router = useRouter();
const authStore = useAuthStore();

const username = ref('admin');
const password = ref('admin123');
const error = ref('');

async function handleLogin() {
  error.value = '';
  if (!username.value.trim() || !password.value.trim()) {
    error.value = 'Введите логин и пароль.';
    return;
  }

  const success = await authStore.login({
    username: username.value.trim(),
    password: password.value,
  });

  if (success) {
    router.push('/dashboard');
  } else {
    error.value = 'Неверный логин или пароль.';
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 space-y-6">
      <!-- Icon & Welcome Header -->
      <div class="text-center space-y-2">
        <div class="w-14 h-14 bg-blue-600 text-white rounded-2xl flex items-center justify-center mx-auto shadow-md">
          <Shield class="w-8 h-8" />
        </div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Вход в систему SAM</h1>
        <p class="text-xs text-slate-500 max-w-sm mx-auto">
          Панель управления активами программного обеспечения и комплаенс-контроля предприятия.
        </p>
      </div>

      <div v-if="error" class="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
        {{ error }}
      </div>

      <!-- Form -->
      <form class="space-y-4" @submit.prevent="handleLogin">
        <Input
          v-model="username"
          label="Имя пользователя"
          placeholder="admin"
          required
        />

        <Input
          v-model="password"
          type="password"
          label="Пароль"
          placeholder="••••••••••••"
          required
        />

        <div class="pt-2">
          <Button
            type="submit"
            variant="primary"
            class="w-full py-2.5"
            :loading="authStore.loading"
          >
            Войти в систему
            <ArrowRight class="w-4 h-4 ml-1.5" />
          </Button>
        </div>
      </form>

      <div class="text-center pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
        <span>SAM Enterprise v2.4</span>
        <button
          type="button"
          class="hover:text-blue-600 cursor-pointer"
          @click="username = 'admin'; password = 'password'"
        >
          Автозаполнение демо-доступа
        </button>
      </div>
    </div>
  </div>
</template>
