<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { generateMindmap } from '../../api/client'

const props = defineProps({
  summary: { type: Object, default: null },
  ready: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
})

const loading = ref(false)
const error = ref('')
const markdown = ref('')
const source = ref('')
const svgRef = ref(null)
let mm = null
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

async function renderMarkmap(md) {
  await nextTick()
  if (!svgRef.value || !md) return
  const { root } = transformer.transform(md)
  if (!mm) {
    mm = Markmap.create(svgRef.value, {
      autoFit: true,
      duration: 300,
      paddingX: 16,
    })
  }
  await mm.setData(root)
  mm.fit()
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

watch(
  () => [props.active, props.ready, contextKey(props.summary)],
  () => {
    // Lazy: only generate when user opens this tab
    if (props.active && props.ready) loadMindmap(false)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  mm?.destroy?.()
  mm = null
})
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-xs text-muted">
        基于当前总结生成层级导图
        <span v-if="source === 'fallback'">· 结构回退</span>
        <span v-else-if="source === 'llm'">· AI 生成</span>
      </p>
      <button
        type="button"
        class="inline-flex min-h-9 cursor-pointer items-center rounded-xl border border-line bg-page px-3 text-xs font-semibold text-ink transition hover:border-brand/40 hover:bg-brand-soft/40 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="loading || !ready"
        @click="loadMindmap(true)"
      >
        {{ loading ? '生成中…' : '重新生成' }}
      </button>
    </div>

    <div
      v-if="!ready"
      class="rounded-2xl border border-dashed border-line bg-page/50 px-4 py-10 text-center text-sm text-muted"
    >
      请先完成视频总结后再查看思维导图
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
        class="h-[420px] w-full touch-pan-y"
        role="img"
        aria-label="视频思维导图"
      />
    </div>
  </div>
</template>
