<script setup>
import { nextTick, ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import HeroSearch from './components/HeroSearch.vue'
import PlatformPills from './components/PlatformPills.vue'
import ResultWorkspace from './components/ResultWorkspace.vue'
import GeoContent from './components/GeoContent.vue'
import FeaturePlaceholders from './components/FeaturePlaceholders.vue'
import AppFooter from './components/AppFooter.vue'
import { downloadVideo, parseVideo, saveFile, summarizeVideoStream } from './api/client'

const url = ref('')
const parsing = ref(false)
const downloading = ref(false)
const summarizing = ref(false)
const summaryStreaming = ref(false)
const summaryStage = ref('')
const error = ref('')
const summaryError = ref('')
const result = ref(null)
const summary = ref(null)
const selectedOptionId = ref('')
const downloadMessage = ref('')
let summarizeAbort = null

/** 滚到目标卡片，并避开 sticky 顶栏，尽量让整框露在可视区 */
function scrollPanelIntoView(id) {
  const el = document.getElementById(id)
  if (!el) return
  const header = document.querySelector('header.sticky')
  const headerH = header ? header.getBoundingClientRect().height : 64
  const gap = 20
  const rect = el.getBoundingClientRect()
  const absoluteTop = rect.top + window.scrollY
  const absoluteBottom = absoluteTop + rect.height
  const viewTop = window.scrollY + headerH + gap
  const viewBottom = window.scrollY + window.innerHeight - gap

  if (absoluteTop >= viewTop - 1 && absoluteBottom <= viewBottom + 1) return

  const targetScroll = absoluteTop - headerH - gap
  window.scrollTo({ top: Math.max(0, targetScroll), behavior: 'smooth' })
}

function scrollToWorkspace() {
  scrollPanelIntoView('result-workspace')
}

function abortSummarize() {
  if (summarizeAbort) {
    summarizeAbort.abort()
    summarizeAbort = null
  }
}

async function onParse() {
  abortSummarize()
  error.value = ''
  summaryError.value = ''
  downloadMessage.value = ''
  result.value = null
  summary.value = null
  summaryStage.value = ''
  summaryStreaming.value = false
  summarizing.value = false
  selectedOptionId.value = ''
  parsing.value = true
  try {
    const data = await parseVideo(url.value.trim())
    result.value = data
    const preferred =
      data.options?.find((o) => o.recommended) || data.options?.[0] || null
    selectedOptionId.value = preferred?.id || ''
    await nextTick()
    requestAnimationFrame(() => scrollToWorkspace())
    // 解析成功后自动总结（无需再点）
    void onSummarize({ fromParse: true })
  } catch (e) {
    error.value = e?.message || '解析失败，请稍后重试'
  } finally {
    parsing.value = false
  }
}

async function onDownload() {
  if (!result.value) return
  const option =
    result.value.options?.find((o) => o.id === selectedOptionId.value) ||
    result.value.options?.[0]
  if (!option) {
    error.value = '请选择一个下载选项'
    return
  }
  error.value = ''
  downloadMessage.value = ''
  downloading.value = true
  try {
    const info = await downloadVideo(url.value.trim(), option)
    await saveFile(info.file_id, info.filename)
    downloadMessage.value = '下载完成，文件已开始保存到本地'
  } catch (e) {
    error.value = e?.message || '下载失败，请稍后重试'
  } finally {
    downloading.value = false
  }
}

function emptySummary() {
  return {
    title: '',
    source_lang: null,
    subtitle_kind: 'auto',
    summary: '',
    chapters: [],
    key_points: [],
    markdown: '',
    transcript: '',
  }
}

/**
 * @param {{ fromParse?: boolean }} [opts]
 */
async function onSummarize(opts = {}) {
  if (!url.value.trim()) {
    error.value = '请先粘贴并解析视频链接'
    return
  }
  // 总结进行中禁止重复触发（自动解析触发除外：此时刚清过状态）
  if (summarizing.value && !opts.fromParse) return

  abortSummarize()
  error.value = ''
  summaryError.value = ''
  summarizing.value = true
  summaryStreaming.value = false
  summaryStage.value = 'fetching_subtitles'
  summary.value = emptySummary()
  if (result.value?.title) {
    summary.value.title = result.value.title
  }

  const ac = new AbortController()
  summarizeAbort = ac
  let streamError = null

  try {
    await summarizeVideoStream(url.value.trim(), {
      signal: ac.signal,
      onEvent(event, data) {
        if (event === 'status') {
          summaryStage.value = data?.stage || ''
          return
        }
        if (event === 'meta') {
          summary.value = {
            ...summary.value,
            title: data?.title || summary.value.title,
            source_lang: data?.source_lang ?? null,
            subtitle_kind: data?.subtitle_kind || 'auto',
            transcript: data?.transcript || '',
          }
          return
        }
        if (event === 'summary_delta') {
          summaryStreaming.value = true
          summary.value = {
            ...summary.value,
            summary: (summary.value.summary || '') + (data?.text || ''),
          }
          return
        }
        if (event === 'summary') {
          summaryStreaming.value = false
          if (data?.summary) {
            summary.value = {
              ...summary.value,
              summary: data.summary,
              markdown: data.summary,
            }
          }
          return
        }
        if (event === 'chapters') {
          summary.value = {
            ...summary.value,
            chapters: Array.isArray(data?.chapters) ? data.chapters : [],
          }
          return
        }
        if (event === 'key_points') {
          summary.value = {
            ...summary.value,
            key_points: Array.isArray(data?.key_points) ? data.key_points : [],
          }
          return
        }
        if (event === 'done') {
          summaryStreaming.value = false
          summaryStage.value = 'done'
          summary.value = {
            ...summary.value,
            markdown: data?.markdown || summary.value.markdown || '',
          }
          return
        }
        if (event === 'error') {
          streamError = Object.assign(new Error(data?.detail || 'AI 总结失败，请稍后重试'), {
            status: data?.status_code,
          })
        }
      },
    })

    if (streamError) throw streamError
    if (!summary.value?.summary && !summary.value?.chapters?.length) {
      throw new Error('AI 未能生成有效总结，请稍后重试')
    }
    summaryStage.value = 'done'
  } catch (e) {
    if (e?.name === 'AbortError') return
    summaryError.value = e?.message || 'AI 总结失败，请稍后重试'
    summaryStage.value = ''
  } finally {
    summarizing.value = false
    summaryStreaming.value = false
    if (summarizeAbort === ac) summarizeAbort = null
  }
}
</script>

<template>
  <div class="min-h-screen">
    <AppHeader />
    <main>
      <HeroSearch v-model="url" :loading="parsing" @parse="onParse" />
      <PlatformPills />

      <div v-if="error" class="mx-auto max-w-6xl px-4 pb-4 sm:px-6">
        <div
          role="alert"
          class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-[var(--shadow-elev-1)]"
        >
          {{ error }}
        </div>
      </div>

      <ResultWorkspace
        :result="result"
        v-model:selected-option-id="selectedOptionId"
        :downloading="downloading"
        :download-message="downloadMessage"
        :summarizing="summarizing"
        :summary="summary"
        :summary-streaming="summaryStreaming"
        :summary-stage="summaryStage"
        :summary-error="summaryError"
        @download="onDownload"
        @summarize="onSummarize"
      />

      <GeoContent />
      <FeaturePlaceholders />
    </main>
    <AppFooter />
  </div>
</template>
