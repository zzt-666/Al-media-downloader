/**
 * Parse transcript lines like `[01:21] text` or `[1:02:03] text`.
 * @returns {{ ts: string, text: string }[]}
 */
export function parseTranscriptCues(transcript) {
  const lines = String(transcript || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  const cueRe = /^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.*)$/
  const cues = []
  for (const line of lines) {
    const m = line.match(cueRe)
    if (m) {
      cues.push({ ts: m[1], text: m[2].trim() })
    } else if (cues.length) {
      cues[cues.length - 1].text = `${cues[cues.length - 1].text} ${line}`.trim()
    } else {
      cues.push({ ts: '00:00', text: line })
    }
  }
  return cues.filter((c) => c.text)
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

/** @returns {[h, m, s]} */
function parseTsParts(ts) {
  const parts = String(ts).split(':').map((p) => Number.parseInt(p, 10) || 0)
  if (parts.length === 2) return [0, parts[0], parts[1]]
  if (parts.length >= 3) return [parts[0], parts[1], parts[2]]
  return [0, 0, 0]
}

function partsToSeconds([h, m, s]) {
  return h * 3600 + m * 60 + s
}

function secondsToParts(total) {
  const t = Math.max(0, Math.floor(total))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  return [h, m, s]
}

function toSrtTimestamp(tsOrParts) {
  const [h, m, s] = Array.isArray(tsOrParts) ? tsOrParts : parseTsParts(tsOrParts)
  return `${pad2(h)}:${pad2(m)}:${pad2(s)},000`
}

/** Convert displayed transcript text to SRT. */
export function transcriptToSrt(transcript) {
  const cues = parseTranscriptCues(transcript)
  if (!cues.length) return ''
  const chunks = []
  for (let i = 0; i < cues.length; i += 1) {
    const startParts = parseTsParts(cues[i].ts)
    const startSec = partsToSeconds(startParts)
    let endSec
    if (i + 1 < cues.length) {
      endSec = partsToSeconds(parseTsParts(cues[i + 1].ts))
      if (endSec <= startSec) endSec = startSec + 3
    } else {
      endSec = startSec + 3
    }
    chunks.push(
      `${i + 1}\n${toSrtTimestamp(startParts)} --> ${toSrtTimestamp(secondsToParts(endSec))}\n${cues[i].text}\n`,
    )
  }
  return chunks.join('\n')
}
