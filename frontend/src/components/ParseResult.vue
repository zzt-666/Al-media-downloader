<script setup>
defineProps({
  result: { type: Object, default: null },
  selectedOptionId: { type: String, default: '' },
  downloading: { type: Boolean, default: false },
  downloadMessage: { type: String, default: '' },
  summarizing: { type: Boolean, default: false },
})

const emit = defineEmits(['update:selectedOptionId', 'download', 'summarize'])

function formatDuration(sec) {
  if (sec == null || Number.isNaN(Number(sec))) return null
  const s = Math.floor(Number(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
  return `${m}:${String(r).padStart(2, '0')}`
}

function formatCount(n) {
  const num = Number(n)
  if (n == null || Number.isNaN(num) || num < 0) return null
  if (num >= 100_000_000) return `${(num / 100_000_000).toFixed(1).replace(/\.0$/, '')}亿`
  if (num >= 10_000) return `${(num / 10_000).toFixed(1).replace(/\.0$/, '')}万`
  return String(Math.floor(num))
}
</script>

<template>
  <section v-if="result" class="anim-rise mx-auto max-w-6xl scroll-mt-28 px-4 pb-10 sm:px-6">
    <div
      id="result-panel"
      class="rounded-3xl border border-line/80 bg-white p-4 shadow-[var(--shadow-elev-3)] sm:p-6"
    >
      <div class="grid items-start gap-5 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-7">
        <aside class="w-full">
          <div class="relative aspect-video w-full overflow-hidden rounded-2xl bg-slate-900 shadow-[var(--shadow-elev-2)]">
            <img
              v-if="result.thumbnail"
              :src="result.thumbnail"
              :alt="result.title"
              class="absolute inset-0 h-full w-full object-cover object-center"
              referrerpolicy="no-referrer"
              loading="lazy"
            />
            <div
              v-else
              class="absolute inset-0 grid place-items-center text-sm text-slate-300"
            >
              暂无封面
            </div>
            <div
              class="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent"
              aria-hidden="true"
            />
            <span
              v-if="formatDuration(result.duration)"
              class="absolute bottom-2.5 left-2.5 rounded-md bg-black/50 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm"
            >
              {{ formatDuration(result.duration) }}
            </span>
            <span
              class="absolute bottom-2.5 right-2.5 rounded-md bg-black/50 px-2 py-0.5 text-xs font-medium text-white backdrop-blur-sm"
            >
              {{ result.options?.length || 0 }} 个选项
            </span>
          </div>

          <div class="mt-3 rounded-2xl border border-vip/25 bg-gradient-to-br from-vip-soft to-white p-3.5">
            <p class="text-sm font-semibold text-vip-deep">VIP 下载更省心</p>
            <p class="mt-1 text-xs leading-relaxed text-muted">
              高清优先队列 · 批量加速 · 更多 AI 能力
            </p>
            <a
              href="#features"
              class="mt-2.5 inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-gradient-to-r from-vip to-[#d4a017] text-sm font-semibold text-white transition duration-200 hover:brightness-105"
            >
              查看会员方案
            </a>
          </div>
        </aside>

        <div class="min-w-0">
          <h2 class="line-clamp-2 text-xl font-bold leading-snug text-ink sm:text-2xl">
            {{ result.title }}
          </h2>
          <div class="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            <span v-if="result.uploader">{{ result.uploader }}</span>
            <span
              v-if="result.extractor"
              class="inline-flex items-center rounded-md border border-brand/20 bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand"
            >
              {{ result.extractor }}
            </span>
          </div>

          <div
            v-if="
              formatDuration(result.duration) ||
              formatCount(result.view_count) ||
              formatCount(result.like_count) ||
              result.upload_date
            "
            class="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted"
          >
            <span v-if="formatDuration(result.duration)">时长 {{ formatDuration(result.duration) }}</span>
            <span v-if="formatCount(result.view_count)">播放 {{ formatCount(result.view_count) }}</span>
            <span v-if="formatCount(result.like_count)">点赞 {{ formatCount(result.like_count) }}</span>
            <span v-if="result.upload_date">发布 {{ result.upload_date }}</span>
          </div>

          <p
            v-if="result.description"
            class="mt-2.5 line-clamp-2 text-sm leading-relaxed text-muted"
            :title="result.description"
          >
            {{ result.description }}
          </p>

          <div class="mt-5">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 class="text-sm font-semibold text-ink">选择清晰度和格式</h3>
              <p class="text-xs text-muted">
                免费可用 · <span class="font-medium text-vip-deep">VIP 优先队列</span>
              </p>
            </div>

            <!-- One card = clarity + format together (no separate steps) -->
            <div class="grid max-h-[320px] gap-2.5 overflow-y-auto pr-1 sm:grid-cols-2">
              <button
                v-for="opt in result.options || []"
                :key="opt.id"
                type="button"
                class="flex cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 text-left transition duration-200"
                :class="
                  selectedOptionId === opt.id
                    ? 'border-brand bg-brand-soft shadow-[var(--shadow-elev-1)]'
                    : 'border-line bg-white hover:border-brand/50'
                "
                @click="emit('update:selectedOptionId', opt.id)"
              >
                <span
                  class="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg"
                  :class="selectedOptionId === opt.id ? 'bg-brand text-white' : 'bg-page text-muted'"
                  aria-hidden="true"
                >
                  <!-- filmstrip / audio icon -->
                  <svg
                    v-if="opt.media_type === 'audio'"
                    class="h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path
                      d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z"
                    />
                  </svg>
                  <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                    <path
                      d="M18 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM8 8h2v2H8V8zm0 4h2v2H8v-2zm0 4h2v2H8v-2zm4-8h6v2h-6V8zm0 4h6v2h-6v-2zm0 4h6v2h-6v-2z"
                    />
                  </svg>
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block text-sm font-semibold leading-snug text-ink">
                    {{ opt.label }}
                  </span>
                  <span class="mt-0.5 block text-xs text-muted">{{ opt.sublabel }}</span>
                </span>
              </button>
            </div>
          </div>

          <div class="mt-5 flex flex-col gap-3 border-t border-line/80 pt-5 sm:flex-row sm:items-center">
            <button
              type="button"
              class="flex min-h-12 flex-1 cursor-pointer items-center justify-center rounded-xl bg-brand px-4 text-base font-semibold text-white shadow-[var(--shadow-elev-2)] transition duration-200 hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="downloading || summarizing || !selectedOptionId"
              @click="emit('download')"
            >
              {{ downloading ? '下载中…' : '下载到本地' }}
            </button>
            <button
              type="button"
              class="inline-flex min-h-12 cursor-pointer items-center justify-center rounded-xl border border-brand/35 bg-brand-soft px-5 text-sm font-semibold text-brand transition duration-200 hover:border-brand/55 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-[140px]"
              :disabled="downloading || summarizing"
              @click="emit('summarize')"
            >
              {{ summarizing ? '总结中…' : 'AI 总结' }}
            </button>
            <a
              href="#features"
              class="inline-flex min-h-12 items-center justify-center rounded-xl border border-vip/35 bg-vip-soft px-5 text-sm font-semibold text-vip-deep transition duration-200 hover:border-vip/55 sm:min-w-[160px]"
            >
              想更快？开通 VIP
            </a>
          </div>
          <p v-if="downloading" class="mt-2 text-xs text-muted">大文件请耐心等待…</p>
          <p v-if="summarizing" class="mt-2 text-xs text-muted">
            正在拉取字幕并调用 AI，长视频可能需要一两分钟…
          </p>
          <p v-if="downloadMessage" class="mt-2 text-xs font-medium text-emerald-600">
            {{ downloadMessage }}
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
