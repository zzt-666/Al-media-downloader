import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

export function renderMarkdown(source) {
  if (!source) return ''
  return md.render(String(source))
}
