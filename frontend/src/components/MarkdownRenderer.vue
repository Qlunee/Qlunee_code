<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { renderMarkdown } from '@/lib/markdown'

const props = defineProps<{
  content: string
}>()

const html = computed(() => renderMarkdown(props.content))
const articleRef = ref<HTMLElement | null>(null)

function attachCopyButtons() {
  if (!articleRef.value) return
  const blocks = articleRef.value.querySelectorAll('pre')
  blocks.forEach((pre) => {
    if (pre.querySelector('.copy-code-btn')) return
    const button = document.createElement('button')
    button.className = 'copy-code-btn'
    button.type = 'button'
    button.textContent = 'Copy'
    button.addEventListener('click', async () => {
      const code = pre.querySelector('code')
      const text = code?.textContent ?? ''
      await navigator.clipboard.writeText(text)
      button.textContent = 'Copied'
      window.setTimeout(() => {
        button.textContent = 'Copy'
      }, 900)
    })
    pre.appendChild(button)
  })
}

onMounted(() => {
  nextTick(attachCopyButtons)
})

watch(html, () => {
  nextTick(attachCopyButtons)
})
</script>

<template>
  <article ref="articleRef" class="markdown-body" v-html="html" />
</template>
