<script setup>
import { computed, ref, watch } from 'vue'
import { SUMMARY_EXTENSION_TABS } from './summary/extensions'
import { downloadBlob, safeDownloadName } from '../utils/downloadBlob'
import { renderMarkdown } from '../utils/renderMarkdown'
import { transcriptToSrt } from '../utils/transcriptExport'

const props = defineProps({
  summary: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  streaming: { type: Boolean, default: false },
  stage: { type: String, default: '' },
  error: { type: String, default: '' },
  /** 嵌入一体工作区时去掉独立外层大卡 */
  embedded: { type: Boolean, default: false },
})

const activeTab = ref('summary')
const copyTip = ref('')
const subTip = ref('')

const CORE_TABS = [
  { id: 'summary', label: '全文总结' },
  { id: 'chapters', label: '章节大纲' },
  { id: 'points', label: '核心知识点' },
  { id: 'transcript', label: '字幕原文' },
]

const tabs = computed(() => [
  ...CORE_TABS,
  ...SUMMARY_EXTENSION_TABS.map((t) => ({ id: t.id, label: t.label })),
])

const summaryReady = computed(
  () =>
    !props.loading &&
    !props.error &&
    !!(props.summary?.summary || props.summary?.chapters?.length || props.summary?.markdown),
)

const safeName = computed(() => safeDownloadName(props.summary?.title, '视频总结'))

const exportMarkdown = computed(() => {
  const md = props.summary?.markdown || props.summary?.summary || ''
  return String(md).trim()
})

const summaryHtml = computed(() => renderMarkdown(props.summary?.summary || ''))

const chapterCount = computed(() => props.summary?.chapters?.length || 0)
const pointCount = computed(() => props.summary?.key_points?.length || 0)

const statusText = computed(() => {
  if (props.error) return '总结失败'
  if (props.stage === 'fetching_subtitles') return '正在拉取字幕…'
  if (props.stage === 'generating') {
    if (props.streaming) return '正在流式生成全文总结，章节同步生成中…'
    return '正在生成总结…'
  }
  if (props.stage === 'done' || (props.summary?.markdown && !props.loading)) {
    return '总结完成'
  }
  if (props.loading) return '正在生成总结…'
  return ''
})

const showPanel = computed(
  () => props.embedded || props.loading || props.summary || !!props.error,
)

watch(
  () => props.loading,
  (v) => {
    if (v) activeTab.value = 'summary'
  },
)

function tabLabel(tab) {
  if (tab.id === 'chapters' && chapterCount.value) {
    return `${tab.label} (${chapterCount.value})`
  }
  if (tab.id === 'points' && pointCount.value) {
    return `${tab.label} (${pointCount.value})`
  }
  return tab.label
}

async function copyMarkdown() {
  const md = exportMarkdown.value
  if (!md) return
  try {
    await navigator.clipboard.writeText(md)
    copyTip.value = '已复制 Markdown'
  } catch {
    copyTip.value = '复制失败，请手动选择文本'
  }
  setTimeout(() => {
    copyTip.value = ''
  }, 2000)
}

function downloadMarkdown() {
  const md = exportMarkdown.value
  if (!md) return
  downloadBlob(md, `${safeName.value}-总结.md`, 'text/markdown;charset=utf-8')
}

function downloadTranscriptTxt() {
  const text = props.summary?.transcript
  if (!text) return
  downloadBlob(text, `${safeName.value}-字幕.txt`, 'text/plain;charset=utf-8')
  subTip.value = '已下载 TXT'
  setTimeout(() => {
    subTip.value = ''
  }, 2000)
}

function downloadTranscriptSrt() {
  const text = props.summary?.transcript
  if (!text) return
  const srt = transcriptToSrt(text)
  if (!srt) {
    subTip.value = '无法转换为 SRT'
    setTimeout(() => {
      subTip.value = ''
    }, 2000)
    return
  }
  downloadBlob(srt, `${safeName.value}-字幕.srt`, 'application/x-subrip;charset=utf-8')
  subTip.value = '已下载 SRT'
  setTimeout(() => {
    subTip.value = ''
  }, 2000)
}
</script>

<template>
  <div
    v-if="showPanel"
    id="summary-panel"
    class="flex min-h-0 flex-1 flex-col"
    :class="
      embedded
        ? ''
        : 'anim-rise mx-auto max-w-6xl scroll-mt-28 overflow-hidden rounded-3xl border border-line/80 bg-white px-0 shadow-[var(--shadow-elev-3)] sm:mx-auto'
    "
  >
    <div
      class="flex flex-wrap items-start justify-between gap-3 border-b border-line/70 px-4 py-3.5 sm:px-5"
    >
      <div class="min-w-0">
        <p class="text-sm font-semibold tracking-wide text-brand">AI 视频总结</p>
        <h2 class="mt-1 line-clamp-2 text-lg font-bold text-ink sm:text-xl">
          {{ summary?.title || (loading ? '正在生成总结…' : error ? '总结未完成' : '视频总结') }}
        </h2>
        <p
          v-if="!error && (summary?.source_lang || summary?.subtitle_kind)"
          class="mt-1 text-xs text-muted"
        >
          字幕：{{ summary.source_lang || '未知' }}
          ·
          {{ summary.subtitle_kind === 'manual' ? '人工字幕' : '自动字幕' }}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span
          v-if="statusText"
          class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          :class="
            error
              ? 'bg-red-50 text-red-700'
              : stage === 'done' && !loading
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-brand-soft text-brand'
          "
        >
          <span
            class="size-1.5 rounded-full"
            :class="
              error
                ? 'bg-red-500'
                : stage === 'done' && !loading
                  ? 'bg-emerald-500'
                  : 'animate-pulse bg-brand'
            "
          />
          {{ statusText }}
        </span>
      </div>
    </div>

    <div v-if="error" class="flex-1 px-4 py-5 sm:px-5">
      <div
        role="alert"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm leading-relaxed text-red-700"
      >
        <p class="font-semibold">无法生成 AI 总结</p>
        <p class="mt-1.5">{{ error }}</p>
      </div>
    </div>

    <template v-else>
      <div
        role="tablist"
        aria-label="总结视图"
        class="flex shrink-0 gap-1 overflow-x-auto border-b border-line/70 px-2 pt-2 sm:px-4"
      >
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          class="relative shrink-0 cursor-pointer rounded-t-xl px-3.5 py-2.5 text-sm font-semibold transition"
          :class="
            activeTab === tab.id
              ? 'bg-brand-soft/70 text-brand'
              : 'text-muted hover:bg-page hover:text-ink'
          "
          @click="activeTab = tab.id"
        >
          {{ tabLabel(tab) }}
          <span
            v-if="activeTab === tab.id"
            class="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-brand"
          />
        </button>
      </div>

      <div class="min-h-[220px] flex-1 overflow-y-auto px-4 py-4 sm:px-5">
        <div v-show="activeTab === 'summary'" role="tabpanel">
          <div
            v-if="exportMarkdown && !error"
            class="mb-4 flex flex-wrap items-center gap-2"
          >
            <button
              type="button"
              class="inline-flex min-h-10 cursor-pointer items-center justify-center rounded-xl border border-line bg-page px-4 text-sm font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
              @click="copyMarkdown"
            >
              复制 Markdown
            </button>
            <button
              type="button"
              class="inline-flex min-h-10 cursor-pointer items-center justify-center rounded-xl bg-brand px-4 text-sm font-semibold text-white transition hover:bg-brand-dark"
              @click="downloadMarkdown"
            >
              下载 .md
            </button>
            <span v-if="copyTip" class="text-xs font-medium text-emerald-600">{{ copyTip }}</span>
          </div>

          <div v-if="!summary?.summary && loading" class="space-y-3">
            <div class="h-4 w-3/4 animate-pulse rounded bg-slate-100" />
            <div class="h-4 w-full animate-pulse rounded bg-slate-100" />
            <div class="h-4 w-5/6 animate-pulse rounded bg-slate-100" />
            <p class="pt-2 text-sm text-muted">{{ statusText || '请稍候…' }}</p>
          </div>
          <div v-else-if="summary?.summary" class="relative">
            <div
              class="summary-md text-sm leading-relaxed text-ink/90"
              v-html="summaryHtml"
            />
            <span
              v-if="streaming"
              class="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-brand align-[-2px]"
              aria-hidden="true"
            />
            <p v-if="streaming" class="mt-3 text-xs text-muted">章节大纲与知识点正在同步生成…</p>
          </div>
          <p v-else class="text-sm text-muted">暂无整体摘要</p>
        </div>

        <div v-show="activeTab === 'chapters'" role="tabpanel">
          <div
            v-if="loading && !summary?.chapters?.length"
            class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-8 text-center text-sm text-muted"
          >
            章节大纲生成中，请稍候…
          </div>
          <ol v-else-if="summary?.chapters?.length" class="space-y-3">
            <li
              v-for="(ch, idx) in summary.chapters"
              :key="`${ch.start}-${idx}`"
              class="rounded-2xl border border-line/80 bg-page/60 px-4 py-3"
            >
              <p class="text-sm font-semibold text-ink">
                <span class="mr-2 font-mono text-xs text-brand">{{ ch.start }}</span>
                {{ ch.title }}
              </p>
              <p v-if="ch.summary" class="mt-1.5 text-sm leading-relaxed text-muted">
                {{ ch.summary }}
              </p>
            </li>
          </ol>
          <p v-else class="text-sm text-muted">暂无章节大纲</p>
        </div>

        <div v-show="activeTab === 'points'" role="tabpanel">
          <div
            v-if="loading && !summary?.key_points?.length"
            class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-8 text-center text-sm text-muted"
          >
            核心知识点生成中，请稍候…
          </div>
          <ul v-else-if="summary?.key_points?.length" class="space-y-2">
            <li
              v-for="(kp, idx) in summary.key_points"
              :key="`${kp.timestamp}-${idx}`"
              class="flex gap-3 rounded-xl border border-line/60 bg-page/40 px-3 py-2.5 text-sm leading-relaxed text-ink/90"
            >
              <span class="mt-0.5 shrink-0 font-mono text-xs font-semibold text-brand">
                {{ kp.timestamp }}
              </span>
              <span>{{ kp.text }}</span>
            </li>
          </ul>
          <p v-else class="text-sm text-muted">暂无核心知识点</p>
        </div>

        <div v-show="activeTab === 'transcript'" role="tabpanel">
          <div
            v-if="summary?.transcript"
            class="mb-3 flex flex-wrap items-center gap-2"
          >
            <button
              type="button"
              class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
              @click="downloadTranscriptTxt"
            >
              下载 TXT
            </button>
            <button
              type="button"
              class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40"
              @click="downloadTranscriptSrt"
            >
              下载 SRT
            </button>
            <span v-if="subTip" class="text-xs font-medium text-emerald-600">{{ subTip }}</span>
          </div>
          <div
            v-if="loading && !summary?.transcript"
            class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-8 text-center text-sm text-muted"
          >
            字幕加载中…
          </div>
          <pre
            v-else-if="summary?.transcript"
            class="max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-2xl border border-line/80 bg-page/60 p-4 font-mono text-xs leading-relaxed text-ink/80"
          >{{ summary.transcript }}</pre>
          <p v-else class="text-sm text-muted">暂无字幕原文</p>
        </div>

        <div
          v-for="ext in SUMMARY_EXTENSION_TABS"
          v-show="activeTab === ext.id"
          :key="ext.id"
          role="tabpanel"
        >
          <component
            :is="ext.component"
            :summary="summary"
            :ready="summaryReady"
            :active="activeTab === ext.id"
          />
        </div>
      </div>
    </template>
  </div>
</template>
