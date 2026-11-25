<script setup>
</script>

<template>
  <footer class="border-t border-line/80 bg-white/70">
    <div class="mx-auto max-w-6xl px-4 py-10 text-sm leading-relaxed text-muted sm:px-6">
      <div class="grid gap-6 sm:grid-cols-[1.2fr_1fr]">
        <div>
          <p class="text-base font-semibold text-ink">版权与使用声明</p>
          <p class="mt-2">
            本工具仅供学习与个人备份辅助。请尊重版权，禁止下载未授权内容用于商用或传播。
            请勿尝试绕过 DRM、破解会员或盗取账号。
          </p>
          <p class="mt-2">
            公网部署可能面临限流、封禁与合规风险；当前按本机学习场景设计。
          </p>
        </div>
        <div class="rounded-2xl border border-vip/20 bg-vip-soft/60 p-4">
          <p class="font-semibold text-vip-deep">想解锁更多？</p>
          <p class="mt-1.5 text-sm text-muted">
            AI 总结已可用（需本机配置 API Key）；字幕翻译与 VIP 支付即将上线。
          </p>
          <a
            href="#features"
            class="mt-3 inline-flex min-h-11 items-center rounded-xl bg-gradient-to-r from-vip to-[#d4a017] px-4 text-sm font-semibold text-white transition duration-200 hover:brightness-105"
          >
            查看会员方案
          </a>
        </div>
      </div>
      <p class="mt-8 text-xs text-muted/80">
        © {{ new Date().getFullYear() }} 万能视频下载器 · 基于 yt-dlp
      </p>
    </div>
  </footer>
</template>
