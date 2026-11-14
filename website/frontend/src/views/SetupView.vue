<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { Shield, Lock, User, CheckCircle2, Sparkles } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Input from '@/components/ui/Input.vue';

const router = useRouter();
const authStore = useAuthStore();

const username = ref('');
const fullName = ref('');
const password = ref('');
const confirmPassword = ref('');
const error = ref('');

async function handleInit() {
  error.value = '';
  if (!username.value.trim() || !password.value.trim()) {
    error.value = 'Пожалуйста, заполните логин и пароль администратора.';
    return;
  }
  if (password.value !== confirmPassword.value) {
    error.value = 'Введённые пароли не совпадают.';
    return;
  }

  const success = await authStore.initAdmin({
    username: username.value.trim(),
    password: password.value,
    full_name: fullName.value.trim(),
  });

  if (success) {
    router.push('/dashboard');
  } else {
    error.value = 'Ошибка инициализации сервиса.';
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200/80 p-8 space-y-6">
      <!-- Иконка и приветственный заголовок -->
      <div class="text-center space-y-2">
        <div class="w-14 h-14 bg-blue-600 text-white rounded-2xl flex items-center justify-center mx-auto shadow-md">
          <Shield class="w-8 h-8" />
        </div>
        <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Первоначальная настройка SAM</h1>
        <p class="text-xs text-slate-500 max-w-sm mx-auto">
          Сервер SAM развернут. Создайте первичную учетную запись администратора для доступа к управлению активами и комплаенс-контролю.
        </p>
      </div>

      <div v-if="error" class="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
        {{ error }}
      </div>

      <!-- Форма первоначальной настройки -->
      <form class="space-y-4" @submit.prevent="handleInit">
        <Input
          v-model="fullName"
          label="ФИО Администратора"
          placeholder="Иванов Алексей Петрович"
          required
        />

        <Input
          v-model="username"
          label="Имя пользователя (Логин)"
          placeholder="admin"
          required
        />

        <Input
          v-model="password"
          type="password"
          label="Пароль администратора"
          placeholder="••••••••••••"
          required
        />

        <Input
          v-model="confirmPassword"
          type="password"
          label="Повторите пароль"
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
            <CheckCircle2 class="w-4 h-4 mr-1.5" />
            Создать профиль администратора
          </Button>
        </div>
      </form>

      <div class="text-center pt-2 border-t border-slate-100 text-[11px] text-slate-400">
        SAM Enterprise Platform • Безопасное хранение хэшей bcrypt
      </div>
    </div>
  </div>
</template>
