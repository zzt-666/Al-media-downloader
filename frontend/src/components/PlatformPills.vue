<script setup>
const platforms = [
  'YouTube',
  'B站',
  'TikTok',
  '抖音',
  'Twitter/X',
  'Instagram',
  'Facebook',
  'Vimeo',
]
</script>

<template>
  <section class="mx-auto max-w-6xl px-4 pb-3 sm:px-6">
    <div
      class="rounded-2xl border border-line/80 bg-white/70 px-4 py-5 text-center shadow-[var(--shadow-elev-1)] backdrop-blur-sm sm:px-6"
    >
      <p class="text-sm font-medium text-muted">基于 yt-dlp · 支持千站 · 能力以引擎为准</p>
      <div class="mt-3 flex flex-wrap justify-center gap-2">
        <span
          v-for="name in platforms"
          :key="name"
          class="rounded-lg border border-brand/10 bg-brand-soft/70 px-3 py-1.5 text-sm font-medium text-brand"
        >
          {{ name }}
        </span>
      </div>
    </div>
  </section>
</template>
