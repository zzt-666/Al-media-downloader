/**
 * Export a Markmap SVG as a complete map (ignore current pan/zoom viewport).
 * PNG path converts foreignObject → SVG text so canvas export stays untainted & sharp.
 */

const SVG_NS = 'http://www.w3.org/2000/svg'
const PAD = 48
const MAX_CANVAS_SIDE = 8192
const MAX_CANVAS_PIXELS = 40_000_000
const MIN_PNG_SCALE = 3
const MAX_PNG_SCALE = 8

function createSvgEl(tag) {
  return document.createElementNS(SVG_NS, tag)
}

/** Content bbox in layout coords (Markmap puts pan/zoom on the top-level <g>). */
export function getMindmapContentBounds(svgEl) {
  const g = svgEl?.querySelector(':scope > g') || svgEl
  if (!g?.getBBox) {
    return { x: 0, y: 0, width: 800, height: 420 }
  }
  const bbox = g.getBBox()
  const width = Math.max(Math.ceil(bbox.width + PAD * 2), 1)
  const height = Math.max(Math.ceil(bbox.height + PAD * 2), 1)
  return {
    x: Math.floor(bbox.x - PAD),
    y: Math.floor(bbox.y - PAD),
    width,
    height,
  }
}

function convertForeignObjects(svgRoot) {
  svgRoot.querySelectorAll('foreignObject').forEach((fo) => {
    const host = fo.querySelector('div') || fo
    const textContent = (host.textContent || '').replace(/\s+/g, ' ').trim()
    if (!textContent) {
      fo.remove()
      return
    }
    const x = Number(fo.getAttribute('x') || 0)
    const y = Number(fo.getAttribute('y') || 0)
    const height = Number(fo.getAttribute('height') || 20)
    let fontSize = 14
    let fill = '#0f172a'
    try {
      const cs = window.getComputedStyle(host)
      const parsed = Number.parseFloat(cs.fontSize || '')
      if (Number.isFinite(parsed) && parsed > 0) fontSize = parsed
      if (cs.color) fill = cs.color
    } catch {
      // detached / cross-origin style — keep defaults
    }
    const text = createSvgEl('text')
    text.setAttribute('x', String(x))
    text.setAttribute('y', String(y + height * 0.65))
    text.setAttribute('font-size', String(fontSize))
    text.setAttribute(
      'font-family',
      'DM Sans, Noto Sans SC, Microsoft YaHei, PingFang SC, sans-serif',
    )
    text.setAttribute('fill', fill)
    text.textContent = textContent
    fo.replaceWith(text)
  })
}

/** Convert css Color / rgb() to a concrete paint string safe for standalone SVG. */
function paintToAttr(paint, fallback) {
  if (!paint || paint === 'none' || paint === 'transparent') return paint || fallback
  // already hex / named / rgb — keep as-is; Image rasterizer accepts rgb()
  if (paint.includes('var(')) return fallback
  return paint
}

/**
 * Markmap fold circles use fill="var(--markmap-circle-open-bg)".
 * Standalone SVG/PNG cannot resolve page CSS vars → fill becomes black.
 * Bake live computed fill/stroke so export matches the on-page hollow rings 1:1.
 */
function bakeCircleStyles(liveSvg, cloneSvg) {
  const liveCircles = liveSvg.querySelectorAll('circle')
  const cloneCircles = cloneSvg.querySelectorAll('circle')
  const n = Math.min(liveCircles.length, cloneCircles.length)
  for (let i = 0; i < n; i += 1) {
    const live = liveCircles[i]
    const clone = cloneCircles[i]
    const cs = getComputedStyle(live)
    const fillAttr = live.getAttribute('fill') || ''
    // Open nodes: white fill + colored stroke. Folded: branch-colored fill.
    const fill = fillAttr.includes('var(')
      ? paintToAttr(cs.fill, '#ffffff')
      : fillAttr || paintToAttr(cs.fill, '#ffffff')
    const stroke =
      live.getAttribute('stroke') || paintToAttr(cs.stroke, '#333333')
    const strokeWidth =
      live.getAttribute('stroke-width') ||
      (cs.strokeWidth && cs.strokeWidth !== '0px' ? cs.strokeWidth : '1.5')
    const r = live.getAttribute('r') || '6'
    clone.setAttribute('fill', fill)
    clone.setAttribute('stroke', stroke)
    clone.setAttribute('stroke-width', String(strokeWidth).replace(/px$/, '') || '1.5')
    clone.setAttribute('r', r)
  }
}

/**
 * Build a full-content SVG clone (no viewport transform).
 * @param {SVGSVGElement} svgEl
 * @param {{ forCanvas?: boolean }} [opts]
 */
export function buildFullMindmapSvg(svgEl, opts = {}) {
  if (!svgEl) return null
  const bounds = getMindmapContentBounds(svgEl)
  const clone = svgEl.cloneNode(true)

  // Drop current pan/zoom — keep nested node layout transforms.
  clone.querySelector(':scope > g')?.removeAttribute('transform')

  clone.setAttribute('xmlns', SVG_NS)
  clone.setAttribute('xmlns:xhtml', 'http://www.w3.org/1999/xhtml')
  if (!clone.classList.contains('markmap')) clone.classList.add('markmap')
  clone.setAttribute('width', String(bounds.width))
  clone.setAttribute('height', String(bounds.height))
  clone.setAttribute(
    'viewBox',
    `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`,
  )
  clone.setAttribute('overflow', 'visible')

  const bg = createSvgEl('rect')
  bg.setAttribute('x', String(bounds.x))
  bg.setAttribute('y', String(bounds.y))
  bg.setAttribute('width', String(bounds.width))
  bg.setAttribute('height', String(bounds.height))
  bg.setAttribute('fill', '#ffffff')
  clone.insertBefore(bg, clone.firstChild)

  // Resolve fold-circle paints before leaving the live document context
  bakeCircleStyles(svgEl, clone)

  if (opts.forCanvas) {
    // Need styles resolved — mount briefly, then convert FO → text.
    const mount = document.createElement('div')
    mount.setAttribute('aria-hidden', 'true')
    mount.style.cssText =
      'position:fixed;left:-100000px;top:0;width:0;height:0;overflow:hidden;opacity:0;pointer-events:none'
    mount.appendChild(clone)
    document.body.appendChild(mount)
    try {
      convertForeignObjects(clone)
    } finally {
      mount.remove()
    }
  }

  return { svg: clone, bounds }
}

export function serializeSvg(svgEl) {
  return new XMLSerializer().serializeToString(svgEl)
}

function pickPngScale(width, height) {
  const byMinEdge = 2400 / Math.max(1, Math.min(width, height))
  let scale = Math.max(MIN_PNG_SCALE, byMinEdge)
  scale = Math.min(scale, MAX_PNG_SCALE)
  scale = Math.min(scale, MAX_CANVAS_SIDE / width, MAX_CANVAS_SIDE / height)
  const pixels = width * height
  if (pixels * scale * scale > MAX_CANVAS_PIXELS) {
    scale = Math.sqrt(MAX_CANVAS_PIXELS / pixels)
  }
  return Math.max(2, scale)
}

/**
 * Rasterize a full mindmap SVG to a high-resolution PNG Blob.
 * @param {SVGSVGElement} svgEl live markmap svg
 * @returns {Promise<Blob>}
 */
export async function mindmapToPngBlob(svgEl) {
  const prepared = buildFullMindmapSvg(svgEl, { forCanvas: true })
  if (!prepared) throw new Error('无可导出的思维导图')

  const { svg, bounds } = prepared
  const scale = pickPngScale(bounds.width, bounds.height)
  const outW = Math.max(1, Math.ceil(bounds.width * scale))
  const outH = Math.max(1, Math.ceil(bounds.height * scale))

  const xml = serializeSvg(svg)
  const blob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)

  try {
    const img = await new Promise((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error('SVG 光栅化失败'))
      image.src = url
    })

    const canvas = document.createElement('canvas')
    canvas.width = outW
    canvas.height = outH
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 不可用')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, outW, outH)
    ctx.setTransform(scale, 0, 0, scale, 0, 0)
    ctx.drawImage(img, 0, 0, bounds.width, bounds.height)

    const pngBlob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('PNG 生成失败'))),
        'image/png',
      )
    })
    return pngBlob
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** @param {SVGSVGElement} svgEl */
export function mindmapToSvgString(svgEl) {
  const prepared = buildFullMindmapSvg(svgEl, { forCanvas: false })
  if (!prepared) throw new Error('无可导出的思维导图')
  return serializeSvg(prepared.svg)
}
