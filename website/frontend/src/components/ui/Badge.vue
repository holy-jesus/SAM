<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'secondary' | 'outline' | 'info';
  size?: 'sm' | 'md';
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'sm',
});

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'success':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'warning':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'destructive':
      return 'bg-red-50 text-red-700 border-red-200';
    case 'info':
      return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'secondary':
      return 'bg-slate-100 text-slate-700 border-slate-200';
    case 'outline':
      return 'bg-transparent text-slate-700 border-slate-300';
    case 'default':
    default:
      return 'bg-slate-100 text-slate-800 border-slate-200';
  }
});
</script>

<template>
  <span
    :class="[
      'inline-flex items-center font-medium border rounded-full',
      variantClasses,
      size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm',
    ]"
  >
    <slot />
  </span>
</template>
