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

export async function summarizeVideo(url) {
  const res = await fetch('/api/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) await readError(res)
  return res.json()
}

/**
 * POST SSE stream for AI summary.
 * callbacks: onEvent(eventName, data), optional signal (AbortSignal)
 */
export async function summarizeVideoStream(url, { onEvent, signal } = {}) {
  const res = await fetch('/api/summarize/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ url }),
    signal,
  })
  if (!res.ok) await readError(res)
  if (!res.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'
  let dataLines = []

  const flush = () => {
    if (!dataLines.length && currentEvent === 'message') return
    const raw = dataLines.join('\n')
    dataLines = []
    const eventName = currentEvent || 'message'
    currentEvent = 'message'
    if (!raw) return
    let parsed = raw
    try {
      parsed = JSON.parse(raw)
    } catch {
      // keep raw string
    }
    onEvent?.(eventName, parsed)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n/)
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      if (line === '') {
        flush()
        continue
      }
      if (line.startsWith(':')) continue
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
  }
  if (buffer.trim()) {
    const line = buffer
    if (line.startsWith('event:')) currentEvent = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  flush()
}

export async function generateMindmap(payload) {
  const res = await fetch('/api/summarize/mindmap', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) await readError(res)
  return res.json()
}

/**
 * POST SSE stream for AI chat over a summarized video.
 */
export async function chatVideoStream(payload, { onEvent, signal } = {}) {
  const res = await fetch('/api/summarize/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
    signal,
  })
  if (!res.ok) await readError(res)
  if (!res.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'
  let dataLines = []

  const flush = () => {
    if (!dataLines.length && currentEvent === 'message') return
    const raw = dataLines.join('\n')
    dataLines = []
    const eventName = currentEvent || 'message'
    currentEvent = 'message'
    if (!raw) return
    let parsed = raw
    try {
      parsed = JSON.parse(raw)
    } catch {
      // keep raw string
    }
    onEvent?.(eventName, parsed)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n/)
    buffer = parts.pop() ?? ''
    for (const line of parts) {
      if (line === '') {
        flush()
        continue
      }
      if (line.startsWith(':')) continue
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
  }
  if (buffer.trim()) {
    const line = buffer
    if (line.startsWith('event:')) currentEvent = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  flush()
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
