<script setup>
defineProps({
  modelValue: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'parse'])
</script>

<template>
  <section id="download" class="mx-auto max-w-6xl scroll-mt-28 px-4 pb-4 pt-10 sm:px-6 sm:pt-14">
    <div class="anim-rise mx-auto max-w-3xl text-center">
      <p
        class="mb-4 inline-flex items-center gap-2 rounded-full border border-brand/15 bg-white/80 px-3 py-1 text-xs font-medium text-brand shadow-[var(--shadow-elev-1)]"
      >
        <span class="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />
        更快 · 更清晰 · 千站可用
      </p>
      <h1 class="text-3xl font-bold leading-tight tracking-tight text-ink sm:text-5xl sm:leading-[1.15]">
        Linkora，
        <span class="bg-gradient-to-r from-brand to-[#3b9bff] bg-clip-text text-transparent">一键保存</span>
      </h1>
      <p class="mx-auto mt-4 max-w-3xl text-sm leading-snug text-muted sm:text-base">
        粘贴链接即可解析并免费下载；AI 总结免费 3 次，VIP 无限次。
      </p>
    </div>

    <form
      class="anim-rise mx-auto mt-8 max-w-3xl rounded-2xl border border-white/80 bg-white p-2 shadow-[var(--shadow-elev-3)]"
      style="animation-delay: 60ms"
      @submit.prevent="emit('parse')"
    >
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
        <label class="sr-only" for="video-url">视频链接</label>
        <input
          id="video-url"
          :value="modelValue"
          type="text"
          inputmode="url"
          autocomplete="off"
          placeholder="粘贴视频链接，例如 https://..."
          class="min-h-12 w-full flex-1 rounded-xl border-0 bg-page/60 px-4 text-base text-ink outline-none transition duration-200 placeholder:text-slate-400 focus:bg-brand-soft/40"
          :disabled="loading"
          @input="emit('update:modelValue', $event.target.value)"
        />
        <button
          type="submit"
          class="min-h-12 shrink-0 cursor-pointer rounded-xl bg-brand px-7 text-base font-semibold text-white shadow-[var(--shadow-elev-1)] transition duration-200 hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
        >
          {{ loading ? '解析中…' : '立即解析' }}
        </button>
      </div>
    </form>
  </section>
</template>
