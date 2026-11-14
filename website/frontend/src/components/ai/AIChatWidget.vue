<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { useSamStore } from '@/stores/sam';
import { api } from '@/services/api';
import { AIChatMessage } from '@/types';
import Button from '@/components/ui/Button.vue';
import { Bot, Send, X, Terminal, Database, Sparkles, MessageSquare } from 'lucide-vue-next';

const samStore = useSamStore();

const queryText = ref('');
const loading = ref(false);
const messagesContainer = ref<HTMLDivElement | null>(null);

const messages = ref<AIChatMessage[]>([
  {
    id: 'm1',
    sender: 'assistant',
    text: 'Здравствуйте! Я ИИ-ассистент ИТ-директора SAM. Вы можете задать мне любые вопросы по лицензиям, балансу, хостам или комплаенсу на естественном языке.',
    timestamp: '12:00',
  },
]);

const quickPrompts = [
  'У кого стоит нелицензионный софт?',
  'Сколько лицензий простаивает («зомби-софт»)?',
  'Покажи ПК с запрещённым софтом',
  'Какой общий финансовый риск компании?',
];

async function scrollToBottom() {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

async function sendQuery(text?: string) {
  const q = text || queryText.value;
  if (!q.trim() || loading.value) return;

  const userMsg: AIChatMessage = {
    id: 'u-' + Date.now(),
    sender: 'user',
    text: q.trim(),
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  };
  messages.value.push(userMsg);
  queryText.value = '';
  loading.value = true;
  await scrollToBottom();

  try {
    const aiResp = await api.askAIChat(q);
    messages.value.push(aiResp);
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}
</script>

<template>
  <div
    v-if="samStore.aiChatWidgetOpen"
    class="fixed bottom-6 right-6 z-50 w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200/90 flex flex-col h-[580px] overflow-hidden transition-all duration-300"
  >
    <!-- Header -->
    <div class="px-4 py-3 bg-gradient-to-r from-blue-700 to-indigo-700 text-white flex items-center justify-between shadow-xs">
      <div class="flex items-center gap-2.5">
        <div class="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center backdrop-blur-xs">
          <Bot class="w-5 h-5 text-blue-200" />
        </div>
        <div>
          <h3 class="text-sm font-semibold flex items-center gap-1.5">
            Ассистент ИТ-Директора (Text-to-SQL)
            <Sparkles class="w-3.5 h-3.5 text-yellow-300" />
          </h3>
          <p class="text-[11px] text-blue-100">Интеллектуальная аналитика SAM по естественному запросу</p>
        </div>
      </div>
      <button
        type="button"
        class="text-white/70 hover:text-white p-1 rounded-md hover:bg-white/10 transition cursor-pointer"
        @click="samStore.aiChatWidgetOpen = false"
      >
        <X class="w-4 h-4" />
      </button>
    </div>

    <!-- Quick Prompts Chips -->
    <div class="p-2.5 bg-slate-50 border-b border-slate-100 flex items-center gap-1.5 overflow-x-auto text-[11px]">
      <button
        v-for="p in quickPrompts"
        :key="p"
        type="button"
        class="px-2.5 py-1 bg-white hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 border border-slate-200 rounded-full text-slate-700 whitespace-nowrap transition-colors cursor-pointer shrink-0"
        @click="sendQuery(p)"
      >
        {{ p }}
      </button>
    </div>

    <!-- Messages Container -->
    <div ref="messagesContainer" class="flex-1 p-4 overflow-y-auto space-y-3.5 text-xs bg-slate-50/30">
      <div
        v-for="m in messages"
        :key="m.id"
        :class="['flex flex-col', m.sender === 'user' ? 'items-end' : 'items-start']"
      >
        <!-- Chat Bubble -->
        <div
          :class="[
            'p-3.5 rounded-2xl max-w-[90%] shadow-2xs leading-relaxed',
            m.sender === 'user'
              ? 'bg-blue-600 text-white rounded-tr-xs'
              : 'bg-white text-slate-800 border border-slate-200 rounded-tl-xs',
          ]"
        >
          <div class="whitespace-pre-line">{{ m.text }}</div>

          <!-- SQL Transparency Box -->
          <div v-if="m.sql_executed" class="mt-2.5 pt-2 border-t border-slate-100 font-mono text-[10px]">
            <div class="flex items-center gap-1 text-slate-400 font-sans mb-1 font-semibold uppercase tracking-wider">
              <Database class="w-3 h-3 text-indigo-500" /> Выполненный SQL-запрос:
            </div>
            <pre class="bg-slate-900 text-emerald-400 p-2 rounded-md overflow-x-auto">{{ m.sql_executed }}</pre>
          </div>

          <!-- Data Table if provided -->
          <div v-if="m.data && m.data.length" class="mt-2 pt-2 border-t border-slate-100 overflow-x-auto">
            <table class="w-full text-left border-collapse text-[11px]">
              <thead>
                <tr class="border-b border-slate-200 text-slate-500">
                  <th v-for="key in Object.keys(m.data[0])" :key="key" class="p-1 font-medium capitalize">
                    {{ key }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in m.data" :key="idx" class="border-b border-slate-100">
                  <td v-for="(val, k) in row" :key="k" class="p-1 font-mono text-slate-700">
                    {{ val }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <span class="text-[10px] text-slate-400 mt-1 px-1">{{ m.timestamp }}</span>
      </div>

      <div v-if="loading" class="flex items-center gap-2 text-slate-400 text-xs py-2">
        <Sparkles class="w-4 h-4 text-blue-600 animate-spin" />
        <span>ИИ формирует аналитический ответ и выполняет запрос...</span>
      </div>
    </div>

    <!-- Input Footer -->
    <div class="p-3 bg-white border-t border-slate-200 flex gap-2 items-center">
      <input
        v-model="queryText"
        type="text"
        placeholder="Задайте вопрос ИТ-директора..."
        class="flex-1 px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        @keydown.enter="sendQuery()"
      />
      <Button variant="primary" size="sm" :disabled="loading || !queryText.trim()" @click="sendQuery()">
        <Send class="w-3.5 h-3.5" />
      </Button>
    </div>
  </div>
</template>
