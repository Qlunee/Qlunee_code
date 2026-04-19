<script setup lang="ts">
import { nextTick, ref } from 'vue'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  submit: []
  stop: []
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

function resize() {
  nextTick(() => {
    if (!textareaRef.value) return
    textareaRef.value.style.height = '0px'
    textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 220)}px`
  })
}

function onInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  resize()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    emit('submit')
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-3xl px-4 pb-6">
    <div class="rounded-2xl border border-white/10 bg-slate-900/85 p-2 shadow-glow backdrop-blur">
      <textarea
        ref="textareaRef"
        :value="props.modelValue"
        :disabled="props.disabled"
        rows="1"
        class="max-h-56 w-full resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        @input="onInput"
        @keydown="onKeydown"
      />
      <div class="mt-2 flex items-center justify-between px-2 pb-1">
        <p class="text-xs text-slate-400">支持 Markdown 与代码块高亮</p>
        <div class="flex items-center gap-2">
          <button
            v-if="props.disabled"
            class="rounded-lg border border-rose-300/40 bg-rose-500/20 px-3 py-1.5 text-sm font-medium text-rose-200 transition hover:bg-rose-500/30"
            @click="emit('stop')"
          >
            停止生成
          </button>
          <button
            class="rounded-lg bg-teal-500 px-3 py-1.5 text-sm font-medium text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="props.disabled || !props.modelValue.trim()"
            @click="emit('submit')"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
