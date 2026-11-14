<script setup lang="ts">
import { useAuthStore } from '@/stores/auth';
import { useSamStore } from '@/stores/sam';
import { Shield, Sparkles, Wand2, FileText, Bot, LogOut, User as UserIcon, RefreshCw } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';

const authStore = useAuthStore();
const samStore = useSamStore();

// Открытие модального окна умного мэтчинга
function handleSmartMatch() {
  const unverified = samStore.installedSoftware.find((s) => !s.catalog_software_id);
  samStore.triggerSmartMatch(unverified?.raw_display_name || '');
}
</script>

<template>
  <header class="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
    <!-- Логотип и наименование системы -->
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs">
        <Shield class="w-5 h-5" />
      </div>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-900 tracking-tight text-sm">SAM Enterprise</span>
        </div>
        <p class="text-[11px] text-slate-400">Учёт и комплаенс программных активов</p>
      </div>
    </div>

    <!-- Панель инструментов ИИ и быстрых действий -->
    <div class="hidden md:flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        class="text-xs bg-slate-50 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors"
        @click="handleSmartMatch"
      >
        <Wand2 class="w-3.5 h-3.5 mr-1 text-blue-600" />
        Умный мэтчинг ИИ
      </Button>

      <Button
        variant="outline"
        size="sm"
        class="text-xs bg-slate-50 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-700 transition-colors"
        @click="samStore.triggerEulaAnalysis()"
      >
        <FileText class="w-3.5 h-3.5 mr-1 text-indigo-600" />
        Анализ EULA ИИ
      </Button>

      <Button
        variant="default"
        size="sm"
        class="text-xs bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-xs"
        @click="samStore.toggleAIChat()"
      >
        <Bot class="w-3.5 h-3.5 mr-1 text-white" />
        Чат ИТ-директора
      </Button>
    </div>

    <!-- Меню пользователя и статус активности -->
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-3 pl-2 border-l border-slate-200">
        <div class="text-right hidden sm:block">
          <p class="text-xs font-semibold text-slate-800 leading-tight">
            {{ authStore.user?.full_name || authStore.user?.username || 'Администратор' }}
          </p>
          <span class="text-[10px] uppercase font-bold text-slate-400">
            {{ authStore.user?.role || 'admin' }}
          </span>
        </div>
        <button
          type="button"
          title="Выйти из системы"
          class="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
          @click="authStore.logout()"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </header>
</template>
