<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  variant?: 'default' | 'primary' | 'secondary' | 'destructive' | 'outline' | 'ghost' | 'success';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  disabled?: boolean;
  loading?: boolean;
  type?: 'button' | 'submit' | 'reset';
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  disabled: false,
  loading: false,
  type: 'button',
});

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void;
}>();

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'primary':
    case 'default':
      return 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm border border-transparent';
    case 'secondary':
      return 'bg-slate-100 text-slate-900 hover:bg-slate-200 border border-slate-200';
    case 'destructive':
      return 'bg-red-600 text-white hover:bg-red-700 shadow-sm border border-transparent';
    case 'success':
      return 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm border border-transparent';
    case 'outline':
      return 'bg-white text-slate-700 hover:bg-slate-50 border border-slate-300 shadow-sm';
    case 'ghost':
      return 'bg-transparent text-slate-700 hover:bg-slate-100 border border-transparent';
    default:
      return 'bg-blue-600 text-white hover:bg-blue-700';
  }
});

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'px-2.5 py-1.5 text-xs rounded-md gap-1.5';
    case 'lg':
      return 'px-5 py-2.5 text-base rounded-lg gap-2.5';
    case 'icon':
      return 'p-2 text-sm rounded-md w-9 h-9 flex items-center justify-center';
    case 'md':
    default:
      return 'px-3.5 py-2 text-sm rounded-md gap-2';
  }
});
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 disabled:pointer-events-none cursor-pointer',
      variantClasses,
      sizeClasses,
    ]"
    @click="emit('click', $event)"
  >
    <svg
      v-if="loading"
      class="animate-spin -ml-0.5 mr-2 h-4 w-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
    <slot />
  </button>
</template>
