<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { generateMindmap } from '../../api/client'
import { downloadBlob, safeDownloadName } from '../../utils/downloadBlob'
import { mindmapToPngBlob, mindmapToSvgString } from '../../utils/mindmapExport'

const props = defineProps({
  summary: { type: Object, default: null },
  ready: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
})

const loading = ref(false)
const error = ref('')
const exportTip = ref('')
const markdown = ref('')
const source = ref('')
const svgRef = ref(null)
const fullscreenSvgRef = ref(null)
const fullscreen = ref(false)
let mm = null
let mmFs = null
let lastKey = ''

const transformer = new Transformer()

function contextKey(s) {
  if (!s) return ''
  return [
    s.title || '',
    s.summary || '',
    (s.chapters || []).length,
    (s.key_points || []).length,
  ].join('|')
}

function fileBase() {
  return `${safeDownloadName(props.summary?.title, '视频')}-思维导图`
}

async function renderInto(svgEl, md, existing) {
  if (!svgEl || !md) return existing
  const { root } = transformer.transform(md)
  let instance = existing
  if (!instance) {
    instance = Markmap.create(svgEl, {
      autoFit: true,
      duration: 300,
      paddingX: 16,
      zoom: true,
      pan: true,
    })
  }
  await instance.setData(root)
  instance.fit()
  return instance
}

async function renderMarkmap(md) {
  await nextTick()
  mm = await renderInto(svgRef.value, md, mm)
  if (fullscreen.value) {
    mmFs = await renderInto(fullscreenSvgRef.value, md, mmFs)
  }
}

async function loadMindmap(force = false) {
  if (!props.ready || !props.summary) return
  const key = contextKey(props.summary)
  if (!force && key && key === lastKey && markdown.value) {
    await renderMarkmap(markdown.value)
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await generateMindmap({
      title: props.summary.title || '',
      summary: props.summary.summary || '',
      chapters: props.summary.chapters || [],
      key_points: props.summary.key_points || [],
    })
    markdown.value = data.markdown || ''
    source.value = data.source || ''
    lastKey = key
    await renderMarkmap(markdown.value)
  } catch (e) {
    error.value = e?.message || '思维导图生成失败'
  } finally {
    loading.value = false
  }
}

function waitFrames(n = 2) {
  return new Promise((resolve) => {
    const step = () => {
      if (n <= 0) resolve()
      else {
        n -= 1
        requestAnimationFrame(step)
      }
    }
    step()
  })
}

async function openFullscreen() {
  if (!markdown.value) return
  fullscreen.value = true
  document.body.style.overflow = 'hidden'
  await nextTick()
  // flex 全屏容器需等布局完成，否则 fit() 会出现 NaN transform
  await waitFrames(2)
  const el = fullscreenSvgRef.value
  if (el && (el.clientWidth < 40 || el.clientHeight < 40)) {
    await new Promise((r) => setTimeout(r, 50))
  }
  mmFs = await renderInto(fullscreenSvgRef.value, markdown.value, null)
  await waitFrames(1)
  mmFs?.fit?.()
}

function closeFullscreen() {
  fullscreen.value = false
  document.body.style.overflow = ''
  mmFs?.destroy?.()
  mmFs = null
  nextTick(() => {
    if (markdown.value) mm?.fit?.()
  })
}

function onKeydown(e) {
  if (e.key === 'Escape' && fullscreen.value) closeFullscreen()
}

function activeSvg() {
  if (fullscreen.value && fullscreenSvgRef.value) return fullscreenSvgRef.value
  return svgRef.value
}

function flashTip(msg, ms = 2500) {
  exportTip.value = msg
  setTimeout(() => {
    if (exportTip.value === msg) exportTip.value = ''
  }, ms)
}

function downloadSvg() {
  const svgEl = activeSvg()
  if (!svgEl) return
  try {
    // 完整内容 bbox + 去掉视口 pan/zoom，与当前缩放无关
    const xml = mindmapToSvgString(svgEl)
    downloadBlob(xml, `${fileBase()}.svg`, 'image/svg+xml;charset=utf-8')
    flashTip('已下载完整 SVG', 1800)
  } catch (e) {
    console.error('mindmap svg export failed', e)
    flashTip('SVG 导出失败，请稍后重试')
  }
}

async function downloadPng() {
  const svgEl = activeSvg()
  if (!svgEl) return
  try {
    flashTip('正在导出高清 PNG…', 8000)
    // 按完整导图尺寸高倍率光栅化，不受当前缩放/平移影响
    const blob = await mindmapToPngBlob(svgEl)
    downloadBlob(blob, `${fileBase()}.png`, 'image/png')
    flashTip('已下载完整高清 PNG', 1800)
  } catch (e) {
    console.error('mindmap png export failed', e)
    flashTip('PNG 导出失败，请改用 SVG')
  }
}

watch(
  () => [props.active, props.ready, contextKey(props.summary)],
  () => {
    if (props.active && props.ready) loadMindmap(false)
  },
  { immediate: true },
)

watch(fullscreen, (v) => {
  if (v) window.addEventListener('keydown', onKeydown)
  else window.removeEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  mm?.destroy?.()
  mm = null
  mmFs?.destroy?.()
  mmFs = null
})
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-muted">
        基于当前总结生成层级导图 · 滚轮平移，Ctrl+滚轮缩放
        <span v-if="source === 'fallback'">· 结构回退</span>
        <span v-else-if="source === 'llm'">· AI 生成</span>
      </p>
      <div v-if="markdown && !error" class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
          @click="openFullscreen"
        >
          全屏
        </button>
        <button
          type="button"
          class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
          @click="downloadPng"
        >
          下载 PNG
        </button>
        <button
          type="button"
          class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
          @click="downloadSvg"
        >
          下载 SVG
        </button>
        <span
          v-if="exportTip"
          class="text-xs font-medium"
          :class="exportTip.includes('失败') ? 'text-red-600' : 'text-emerald-600'"
        >{{ exportTip }}</span>
      </div>
    </div>

    <div
      v-if="!ready"
      class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-10 text-center text-sm text-muted"
    >
      正在生成思维导图…
    </div>
    <div
      v-else-if="error"
      role="alert"
      class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {{ error }}
    </div>
    <div
      v-else-if="loading && !markdown"
      class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-10 text-center text-sm text-muted"
    >
      正在生成思维导图…
    </div>
    <div
      v-else
      class="overflow-hidden rounded-2xl border border-line/80 bg-gradient-to-b from-page/80 to-white"
    >
      <svg
        ref="svgRef"
        class="h-[420px] w-full touch-manipulation"
        role="img"
        aria-label="视频思维导图"
      />
    </div>

    <Teleport to="body">
      <div
        v-if="fullscreen"
        class="fixed inset-0 z-[80] flex flex-col bg-white"
        role="dialog"
        aria-modal="true"
        aria-label="思维导图全屏"
      >
        <div
          class="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3"
        >
          <p class="text-sm font-semibold text-ink">
            {{ summary?.title || '思维导图' }}
            <span class="ml-2 text-xs font-normal text-muted">Esc 退出 · Ctrl+滚轮缩放</span>
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <button
              type="button"
              class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40"
              @click="downloadPng"
            >
              下载 PNG
            </button>
            <button
              type="button"
              class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40"
              @click="downloadSvg"
            >
              下载 SVG
            </button>
            <button
              type="button"
              class="inline-flex min-h-9 cursor-pointer items-center rounded-xl bg-brand px-3 text-xs font-semibold text-white transition hover:bg-brand-dark"
              @click="closeFullscreen"
            >
              退出全屏
            </button>
          </div>
        </div>
        <div class="min-h-0 flex-1 bg-gradient-to-b from-page/60 to-white">
          <svg
            ref="fullscreenSvgRef"
            class="h-full w-full touch-manipulation"
            role="img"
            aria-label="视频思维导图全屏"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
