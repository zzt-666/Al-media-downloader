async function readError(res) {
  let detail = `请求失败（${res.status}）`
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') {
      detail = data.detail
    } else if (Array.isArray(data?.detail)) {
      detail = data.detail.map((d) => d.msg || JSON.stringify(d)).join('；')
    }
  } catch {
    // keep default
  }
  const err = new Error(detail)
  err.status = res.status
  throw err
}

export async function getHealth() {
  const res = await fetch('/api/health')
  if (!res.ok) await readError(res)
  return res.json()
}

export async function parseVideo(url) {
  const res = await fetch('/api/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) await readError(res)
  return res.json()
}

export async function downloadVideo(url, option) {
  const payload = {
    url,
    option_id: option?.id,
    media_type: option?.media_type || 'av',
    quality: option?.quality || 'best',
  }
  if (option?.format_id) payload.format_id = option.format_id
  const res = await fetch('/api/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) await readError(res)
  return res.json()
}

export function fileUrl(fileId) {
  return `/api/files/${encodeURIComponent(fileId)}`
}

export async function saveFile(fileId, filename) {
  const res = await fetch(fileUrl(fileId))
  if (!res.ok) await readError(res)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename || 'video'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}
