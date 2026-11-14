<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useSamStore } from '@/stores/sam';
import {
  LayoutDashboard,
  ShieldAlert,
  Users,
  Monitor,
  Laptop,
  CheckCircle2,
  KeyRound,
  Tags,
  FolderTree,
  Landmark,
  UploadCloud,
  Bot,
  Wand2,
  FileText,
} from 'lucide-vue-next';

const route = useRoute();
const samStore = useSamStore();

const activeAlertsCount = computed(() => {
  return samStore.alerts.filter((a) => a.status === 'active').length || 5;
});

const navigationSections = [
  {
    title: 'МОНИТОРИНГ И КОНТРОЛЬ',
    items: [
      { name: 'Главный дашборд', path: '/dashboard', icon: LayoutDashboard },
      {
        name: 'Комплаенс-контроль',
        path: '/compliance',
        icon: ShieldAlert,
        badge: activeAlertsCount,
        badgeVariant: 'destructive' as const,
      },
    ],
  },
  {
    title: 'АКТИВЫ И ЛИЦЕНЗИИ',
    items: [
      { name: 'Сотрудники', path: '/employees', icon: Users },
      { name: 'Компьютеры и хосты', path: '/computers', icon: Monitor },
      { name: 'Установленное ПО', path: '/installed-software', icon: Laptop },
      { name: 'Каталог разрешённого ПО', path: '/catalog', icon: CheckCircle2 },
      { name: 'Лицензии и соглашения', path: '/licenses', icon: KeyRound },
    ],
  },
  {
    title: 'КЛАССИФИКАЦИЯ И РЕЕСТРЫ',
    items: [
      { name: 'Категории софта', path: '/categories', icon: Tags },
      { name: 'Классификатор ПО РФ', path: '/classifiers', icon: FolderTree },
      { name: 'Реестр отечественного ПО', path: '/registry', icon: Landmark },
    ],
  },
  {
    title: 'СБОР ДАННЫХ И ИИ',
    items: [
      { name: 'Импорт дампа хостов', path: '/import', icon: UploadCloud },
      { name: 'Чат-ассистент ИТ-директора', path: '/ai-chat', icon: Bot },
    ],
  },
];
</script>

<template>
  <aside class="w-64 bg-white border-r border-slate-200/80 flex flex-col shrink-0 h-[calc(100vh-4rem)] sticky top-16 select-none overflow-y-auto">
    <div class="p-3.5 space-y-6">
      <div v-for="section in navigationSections" :key="section.title">
        <h4 class="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
          {{ section.title }}
        </h4>
        <nav class="space-y-0.5">
          <RouterLink
            v-for="item in section.items"
            :key="item.path"
            :to="item.path"
            :class="[
              'flex items-center justify-between px-3 py-2 text-xs font-medium rounded-lg transition-colors group',
              route.path === item.path
                ? 'bg-blue-50 text-blue-700 font-semibold shadow-2xs'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50',
            ]"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <component
                :is="item.icon"
                :class="[
                  'w-4 h-4 shrink-0 transition-colors',
                  route.path === item.path ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600',
                ]"
              />
              <span class="truncate">{{ item.name }}</span>
            </div>
            <span
              v-if="item.badge"
              :class="[
                'px-1.5 py-0.2 text-[10px] font-bold rounded-full',
                item.badgeVariant === 'destructive'
                  ? 'bg-red-100 text-red-700 border border-red-200'
                  : 'bg-slate-100 text-slate-700',
              ]"
            >
              {{ item.badge }}
            </span>
          </RouterLink>
        </nav>
      </div>
    </div>

    <!-- Bottom Quick AI Card -->
    <div class="mt-auto p-3.5 border-t border-slate-100">
      <div class="p-3 bg-gradient-to-br from-slate-900 to-slate-800 rounded-xl text-white text-xs space-y-2 shadow-xs">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-xs flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            SAM AI Engine
          </span>
          <span class="text-[9px] uppercase px-1.5 py-0.5 bg-white/20 rounded-sm font-mono">pgvector</span>
        </div>
        <p class="text-[11px] text-slate-300 leading-snug">
          Анализ EULA и автоматическая нормализация процессов активны.
        </p>
        <button
          type="button"
          class="w-full text-center py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium text-[11px] transition cursor-pointer"
          @click="samStore.toggleAIChat()"
        >
          Открыть чат с ИИ
        </button>
      </div>
    </div>
  </aside>
</template>
