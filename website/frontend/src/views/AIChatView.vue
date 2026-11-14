<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import { api } from '@/services/api';
import { AIChatMessage } from '@/types';
import Button from '@/components/ui/Button.vue';
import Card from '@/components/ui/Card.vue';
import {
  Bot,
  Send,
  Database,
  Sparkles,
  HelpCircle,
  ShieldAlert,
  UserX,
  FileText,
  DollarSign,
} from 'lucide-vue-next';

const queryText = ref('');
const loading = ref(false);
const chatContainer = ref<HTMLDivElement | null>(null);

const messages = ref<AIChatMessage[]>([
  {
    id: 'm-init',
    sender: 'assistant',
    text: `Здравствуйте! Я интеллектуальный ассистент ИТ-директора SAM.
Я преобразую ваши вопросы на естественном языке в структурированные SQL-запросы к базе данных (Text-to-SQL + RAG) и анализирую комплаенс, финансовые риски и рабочие станции.

Задайте вопрос или выберите одну из готовых тем ниже.`,
    timestamp: '12:00',
  },
]);

const featuredPrompts = [
  {
    title: 'Нелицензионный софт и дефицит',
    query: 'У кого стоит нелицензионный софт и сколько денег мы рискуем потерять?',
    icon: ShieldAlert,
    color: 'text-red-600',
  },
  {
    title: 'Зомби-софт и уволенные',
    query: 'Сколько лицензий простаивает («зомби-софт») у уволенных сотрудников?',
    icon: UserX,
    color: 'text-amber-600',
  },
  {
    title: 'Запрещённое ПО (Shadow IT)',
    query: 'Покажи все ПК с запрещённым софтом или торрентами',
    icon: Bot,
    color: 'text-purple-600',
  },
  {
    title: 'Финансовый баланс компании',
    query: 'Какой общий финансовый штрафной риск по всем продуктам?',
    icon: DollarSign,
    color: 'text-emerald-600',
  },
];

async function scrollToBottom() {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
}

async function send(query?: string) {
  const text = query || queryText.value;
  if (!text.trim() || loading.value) return;

  const userMsg: AIChatMessage = {
    id: 'u-' + Date.now(),
    sender: 'user',
    text: text.trim(),
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  };
  messages.value.push(userMsg);
  queryText.value = '';
  loading.value = true;
  await scrollToBottom();

  try {
    const aiResp = await api.askAIChat(text);
    messages.value.push(aiResp);
  } finally {
    loading.value = false;
    await scrollToBottom();
  }
}
</script>

<template>
  <div class="space-y-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-2xl font-bold text-slate-900 tracking-tight">Чат-ассистент ИТ-директора</h1>
          <span class="px-2 py-0.5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-xs font-bold shadow-2xs">
            Text-to-SQL / RAG
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          Естественно-языковая аналитика по активам, лицензиям и рискам ИБ предприятия
        </p>
      </div>
    </div>

    <!-- Featured Prompt Cards Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <button
        v-for="p in featuredPrompts"
        :key="p.title"
        type="button"
        class="p-3.5 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl text-left transition shadow-2xs group cursor-pointer"
        @click="send(p.query)"
      >
        <div class="flex items-center gap-2 mb-1.5">
          <component :is="p.icon" :class="['w-4 h-4', p.color]" />
          <h4 class="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
            {{ p.title }}
          </h4>
        </div>
        <p class="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
          {{ p.query }}
        </p>
      </button>
    </div>

    <!-- Main Chat Window -->
    <div class="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col h-[560px] overflow-hidden">
      <!-- Chat Header -->
      <div class="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center">
            <Bot class="w-4 h-4" />
          </div>
          <div>
            <span class="text-xs font-bold text-slate-800">Интеллектуальный агент SAM</span>
            <span class="text-[10px] text-emerald-600 font-medium ml-2">● В сети</span>
          </div>
        </div>
        <div class="text-[11px] text-slate-400 font-mono">
          PostgreSQL / pgvector AI RAG
        </div>
      </div>

      <!-- Messages Stream -->
      <div ref="chatContainer" class="flex-1 p-5 overflow-y-auto space-y-4 text-xs bg-slate-50/20">
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['flex flex-col', msg.sender === 'user' ? 'items-end' : 'items-start']"
        >
          <div
            :class="[
              'p-4 rounded-2xl max-w-[85%] shadow-2xs leading-relaxed space-y-3',
              msg.sender === 'user'
                ? 'bg-blue-600 text-white rounded-tr-xs'
                : 'bg-white text-slate-800 border border-slate-200/90 rounded-tl-xs',
            ]"
          >
            <div class="whitespace-pre-line text-xs font-sans">{{ msg.text }}</div>

            <!-- SQL Query Transparency -->
            <div v-if="msg.sql_executed" class="pt-3 border-t border-slate-100">
              <div class="flex items-center gap-1.5 text-slate-500 font-semibold text-[10px] uppercase mb-1">
                <Database class="w-3.5 h-3.5 text-indigo-600" /> Сгенерированный SQL-запрос:
              </div>
              <pre class="bg-slate-900 text-emerald-400 p-2.5 rounded-lg font-mono text-[11px] overflow-x-auto">{{ msg.sql_executed }}</pre>
            </div>

            <!-- Result Table -->
            <div v-if="msg.data && msg.data.length" class="pt-2 border-t border-slate-100 overflow-x-auto">
              <table class="w-full text-left border-collapse text-[11px]">
                <thead>
                  <tr class="border-b border-slate-200 text-slate-500 font-semibold">
                    <th v-for="key in Object.keys(msg.data[0])" :key="key" class="py-1 px-2 uppercase text-[10px]">
                      {{ key }}
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="(row, idx) in msg.data" :key="idx" class="hover:bg-slate-50">
                    <td v-for="(val, k) in row" :key="k" class="py-1.5 px-2 font-mono text-slate-700">
                      {{ val }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <span class="text-[10px] text-slate-400 mt-1 px-2 font-mono">{{ msg.timestamp }}</span>
        </div>

        <div v-if="loading" class="flex items-center gap-2 text-slate-400 text-xs py-2">
          <Sparkles class="w-4 h-4 text-blue-600 animate-spin" />
          <span>Генерация аналитики и исполнение запроса к базе данных...</span>
        </div>
      </div>

      <!-- Input Bar -->
      <div class="p-3 bg-white border-t border-slate-200 flex gap-2">
        <input
          v-model="queryText"
          type="text"
          placeholder="Напишите вопрос ИТ-директора, например: «У кого стоит нелицензионный MS Office?»..."
          class="flex-1 px-3.5 py-2.5 text-xs bg-slate-50 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          @keydown.enter="send()"
        />
        <Button variant="primary" :disabled="loading || !queryText.trim()" @click="send()">
          <Send class="w-4 h-4 mr-1.5" />
          Спросить
        </Button>
      </div>
    </div>
  </div>
</template>
