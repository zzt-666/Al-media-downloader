<script setup>
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-line/70 bg-white/85 backdrop-blur-md">
    <div class="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
      <a href="#download" class="group flex items-center gap-2.5 text-ink transition duration-200 hover:opacity-90">
        <span
          class="grid h-9 w-9 place-items-center rounded-xl bg-brand text-sm font-bold text-white shadow-[var(--shadow-elev-1)]"
          aria-hidden="true"
        >
          V
        </span>
        <span class="text-base font-bold tracking-tight sm:text-lg">万能视频下载器</span>
      </a>
      <nav class="flex items-center gap-1 sm:gap-2">
        <a
          href="#download"
          class="hidden min-h-11 items-center rounded-xl px-3 text-sm font-medium text-muted transition duration-200 hover:bg-brand-soft hover:text-brand sm:inline-flex"
        >
          下载
        </a>
        <a
          href="#features"
          class="hidden min-h-11 items-center rounded-xl px-3 text-sm font-medium text-muted transition duration-200 hover:bg-vip-soft hover:text-vip-deep sm:inline-flex"
        >
          会员
        </a>
        <a
          href="#features"
          class="inline-flex min-h-11 items-center rounded-xl bg-gradient-to-r from-vip to-[#d4a017] px-4 text-sm font-semibold text-white shadow-[var(--shadow-elev-1)] transition duration-200 hover:brightness-105"
        >
          开通 VIP
        </a>
      </nav>
    </div>
  </header>
</template>
