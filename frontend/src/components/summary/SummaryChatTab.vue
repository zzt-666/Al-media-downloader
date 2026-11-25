<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { chatVideoStream } from '../../api/client'

const props = defineProps({
  summary: { type: Object, default: null },
  ready: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
})

const input = ref('')
const sending = ref(false)
const error = ref('')
const messages = ref([])
const listRef = ref(null)
let abortCtrl = null

const suggestions = [
  '这段视频的核心观点是什么？',
  '帮我用三条要点复述内容',
  '有哪些值得深入了解的概念？',
]

const canSend = computed(
  () => props.ready && !sending.value && !!input.value.trim(),
)

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function sendText(text) {
  const q = (text || '').trim()
  if (!q || !props.ready || sending.value) return

  error.value = ''
  messages.value.push({ role: 'user', content: q })
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  input.value = ''
  sending.value = true
  await scrollToBottom()

  if (abortCtrl) abortCtrl.abort()
  abortCtrl = new AbortController()
  const assistantIdx = messages.value.length - 1
  let streamError = null

  try {
    await chatVideoStream(
      {
        title: props.summary?.title || '',
        summary: props.summary?.summary || '',
        transcript: props.summary?.transcript || '',
        chapters: props.summary?.chapters || [],
        key_points: props.summary?.key_points || [],
        messages: messages.value
          .filter((m) => !m.streaming || m.content)
          .filter((m, i) => i < assistantIdx)
          .map((m) => ({ role: m.role, content: m.content })),
      },
      {
        signal: abortCtrl.signal,
        onEvent(event, data) {
          if (event === 'delta') {
            const cur = messages.value[assistantIdx]
            if (cur) {
              cur.content = (cur.content || '') + (data?.text || '')
              scrollToBottom()
            }
            return
          }
          if (event === 'done') {
            const cur = messages.value[assistantIdx]
            if (cur) {
              cur.content = data?.content || cur.content
              cur.streaming = false
            }
            return
          }
          if (event === 'error') {
            streamError = new Error(data?.detail || 'AI 对话失败')
          }
        },
      },
    )
    if (streamError) throw streamError
    const cur = messages.value[assistantIdx]
    if (cur) cur.streaming = false
    if (!cur?.content) throw new Error('AI 未返回有效回答')
  } catch (e) {
    if (e?.name === 'AbortError') return
    error.value = e?.message || 'AI 对话失败，请稍后重试'
    const cur = messages.value[assistantIdx]
    if (cur && !cur.content) {
      messages.value.splice(assistantIdx, 1)
    } else if (cur) {
      cur.streaming = false
    }
  } finally {
    sending.value = false
    abortCtrl = null
    await scrollToBottom()
  }
}

function onSubmit() {
  sendText(input.value)
}

watch(
  () => props.summary?.title,
  () => {
    messages.value = []
    error.value = ''
  },
)
</script>

<template>
  <div class="flex min-h-[420px] flex-col gap-3">
    <div
      v-if="!ready"
      class="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-line bg-page/50 px-4 py-10 text-center text-sm text-muted"
    >
      请先完成视频总结后再开始 AI 对话
    </div>

    <template v-else>
      <div
        ref="listRef"
        class="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-line/80 bg-page/40 p-3 sm:p-4"
        style="max-height: 360px"
      >
        <div v-if="!messages.length" class="space-y-3 py-2">
          <p class="text-sm text-muted">围绕当前视频提问，例如：</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="s in suggestions"
              :key="s"
              type="button"
              class="cursor-pointer rounded-full border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink transition hover:border-brand/40 hover:bg-brand-soft/50"
              @click="sendText(s)"
            >
              {{ s }}
            </button>
          </div>
        </div>

        <div
          v-for="(m, idx) in messages"
          :key="idx"
          class="flex"
          :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[90%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
            :class="
              m.role === 'user'
                ? 'bg-brand text-white'
                : 'border border-line/80 bg-white text-ink/90'
            "
          >
            {{ m.content || (m.streaming ? '…' : '') }}<span
              v-if="m.streaming"
              class="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-brand align-[-2px]"
              aria-hidden="true"
            />
          </div>
        </div>
      </div>

      <div
        v-if="error"
        role="alert"
        class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
      >
        {{ error }}
      </div>

      <form class="flex gap-2" @submit.prevent="onSubmit">
        <input
          v-model="input"
          type="text"
          maxlength="2000"
          placeholder="针对这个视频提问…"
          class="min-h-11 flex-1 rounded-xl border border-line bg-white px-3 text-sm text-ink outline-none transition focus:border-brand"
          :disabled="sending"
        />
        <button
          type="submit"
          class="inline-flex min-h-11 min-w-20 cursor-pointer items-center justify-center rounded-xl bg-brand px-4 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="!canSend"
        >
          {{ sending ? '…' : '发送' }}
        </button>
      </form>
    </template>
  </div>
</template>
