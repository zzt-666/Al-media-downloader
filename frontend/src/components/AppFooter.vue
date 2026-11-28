<script setup>
import { scrollToId } from '../utils/scrollToId'

function goFeatures(e) {
  e.preventDefault()
  scrollToId('features')
}
</script>

<template>
  <footer class="border-t border-line/80 bg-white/70">
    <div class="mx-auto max-w-6xl px-4 py-10 text-sm leading-relaxed text-muted sm:px-6">
      <div class="grid gap-6 sm:grid-cols-[1.2fr_1fr]">
        <div>
          <p class="text-base font-semibold text-ink">版权与使用声明</p>
          <p class="mt-2">
            请仅将本工具用于学习与个人备份。请尊重版权，禁止下载未授权内容用于商用或传播；请勿尝试绕过
            DRM、破解会员或盗取账号。使用本服务即表示你理解并遵守上述约定。
          </p>
        </div>
        <div class="rounded-2xl border border-vip/20 bg-vip-soft/60 p-4">
          <p class="font-semibold text-vip-deep">想解锁更多？</p>
          <p class="mt-1.5 text-sm text-muted">
            视频解析与下载免费可用；普通用户可体验 AI 总结 3 次，开通 VIP（¥9.9/月）可无限次使用。
          </p>
          <a
            href="#features"
            class="mt-3 inline-flex min-h-11 items-center rounded-xl bg-gradient-to-r from-vip to-[#d4a017] px-4 text-sm font-semibold text-white transition duration-200 hover:brightness-105"
            @click="goFeatures"
          >
            查看会员方案
          </a>
        </div>
      </div>
      <p class="mt-8 text-xs text-muted/80">
        © {{ new Date().getFullYear() }} Linkora · 基于 yt-dlp
      </p>
    </div>
  </footer>
</template>
