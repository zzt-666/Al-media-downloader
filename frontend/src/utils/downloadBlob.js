/** Trigger a browser download from text or Blob content. */
export function downloadBlob(content, filename, mime = 'application/octet-stream') {
  const blob =
    content instanceof Blob ? content : new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function safeDownloadName(title, fallback = '视频') {
  return String(title || fallback)
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
    .slice(0, 80)
}
