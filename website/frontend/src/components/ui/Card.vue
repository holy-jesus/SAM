<script setup lang="ts">
interface Props {
  title?: string;
  subtitle?: string;
  noPadding?: boolean;
}

withDefaults(defineProps<Props>(), {
  noPadding: false,
});
</script>

<template>
  <div class="bg-white rounded-xl border border-slate-200/80 shadow-sm overflow-hidden transition-all">
    <div v-if="title || $slots.header || $slots.actions" class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
      <div>
        <slot name="header">
          <h3 v-if="title" class="font-semibold text-slate-900 text-base leading-none">{{ title }}</h3>
          <p v-if="subtitle" class="text-xs text-slate-500 mt-1.5">{{ subtitle }}</p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <div :class="noPadding ? '' : 'p-5'">
      <slot />
    </div>
    <div v-if="$slots.footer" class="px-5 py-3.5 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between">
      <slot name="footer" />
    </div>
  </div>
</template>
