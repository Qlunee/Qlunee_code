import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code: string, language: string): string {
    if (language && hljs.getLanguage(language)) {
      const highlighted = hljs.highlight(code, {
        language,
        ignoreIllegals: true,
      }).value
      return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
    }
    const escaped = escapeHtml(code)
    return `<pre><code class="hljs">${escaped}</code></pre>`
  },
})

export function renderMarkdown(source: string): string {
  const raw = markdown.render(source)
  return DOMPurify.sanitize(raw)
}
