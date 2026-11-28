<script setup>
import { ref } from 'vue'

const openFaq = ref(0)

const steps = [
  { title: '粘贴链接', desc: '公开链接或分享文案' },
  { title: '一键解析', desc: '封面、时长、清晰度' },
  { title: '免费下载', desc: '选格式，存到本机' },
  { title: 'VIP 总结', desc: '摘要、章节可导出' },
]

const scenes = [
  { title: '课程回顾', desc: '本地保存，摘要抓重点' },
  { title: '资料备份', desc: '公开教学视频离线复习' },
  { title: '要点摘录', desc: '先看章节再决定是否完整看' },
]

const faqs = [
  {
    q: 'Linkora 支持哪些视频网站？',
    a: '凡本机已安装的 yt-dlp 引擎能够解析的公开页面，均可尝试；实际可用性因站点策略变化而异，以解析结果为准。',
  },
  {
    q: 'Linkora 收费吗？下载和 AI 总结有什么区别？',
    a: '视频解析与下载免费可用，无需开通会员。AI 视频总结（摘要、章节、知识点等）需要开通 VIP 会员后使用。',
  },
  {
    q: '下载的内容可以商用或传播吗？',
    a: '不可以。Linkora 仅供学习与个人备份辅助，请尊重版权，禁止将未授权内容用于商用或传播，也请勿尝试绕过 DRM 或破解会员。',
  },
]

function toggleFaq(index) {
  openFaq.value = openFaq.value === index ? -1 : index
}
</script>

<template>
  <section id="about" class="mx-auto max-w-5xl scroll-mt-28 px-4 pb-6 pt-4 text-center sm:px-6 sm:pb-7 sm:pt-5">
    <!-- Intro -->
    <div class="mx-auto max-w-4xl">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">Linkora 是什么</h2>
      <p
        class="mt-1.5 overflow-x-auto whitespace-nowrap text-base leading-snug text-muted sm:text-lg"
      >
        面向学习与个人备份：粘贴公开链接即可解析并免费下载；开通 VIP 后可生成要点摘要与章节结构。
      </p>
      <div class="mt-2 flex flex-wrap justify-center gap-2">
        <span class="rounded-md bg-brand-soft px-2.5 py-1 text-xs font-medium text-brand">下载免费</span>
        <span class="rounded-md bg-vip-soft px-2.5 py-1 text-xs font-medium text-vip-deep">总结需 VIP</span>
        <span class="rounded-md bg-page px-2.5 py-1 text-xs font-medium text-muted">学习向 · 尊重版权</span>
      </div>
    </div>

    <!-- Steps -->
    <div class="mx-auto mt-9 max-w-4xl border-t border-line/70 pt-8">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">如何下载并总结</h2>
      <a
        href="#download"
        class="mt-1.5 inline-block text-xs font-medium text-brand hover:text-brand-dark sm:text-sm"
      >
        去顶部开始
      </a>
      <ol class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:gap-3">
        <li v-for="(step, index) in steps" :key="step.title" class="px-2">
          <span
            class="mx-auto grid h-7 w-7 place-items-center rounded-full bg-brand text-xs font-bold text-white"
            aria-hidden="true"
          >
            {{ index + 1 }}
          </span>
          <h3 class="mt-2 text-sm font-semibold text-ink">{{ step.title }}</h3>
          <p class="mt-0.5 text-xs leading-snug text-muted">{{ step.desc }}</p>
        </li>
      </ol>
    </div>

    <!-- Scenes -->
    <div class="mx-auto mt-9 max-w-3xl border-t border-line/70 pt-8">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">适合这些场景</h2>
      <ul class="mt-5 grid gap-4 sm:grid-cols-3 sm:gap-6">
        <li v-for="scene in scenes" :key="scene.title">
          <h3 class="text-sm font-semibold text-ink">{{ scene.title }}</h3>
          <p class="mt-0.5 text-xs leading-snug text-muted">{{ scene.desc }}</p>
        </li>
      </ul>
    </div>

    <!-- FAQ + boundary -->
    <div class="mx-auto mt-9 max-w-4xl border-t border-line/70 pt-8">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">常见问题</h2>
      <div class="mt-4 divide-y divide-line/70 text-left">
        <div v-for="(item, index) in faqs" :key="item.q">
          <button
            type="button"
            class="flex w-full cursor-pointer items-center justify-between gap-3 py-3 text-left"
            :aria-expanded="openFaq === index"
            :aria-controls="`geo-faq-${index}`"
            @click="toggleFaq(index)"
          >
            <h3 class="text-sm font-semibold text-ink">{{ item.q }}</h3>
            <span
              class="text-lg leading-none text-muted"
              :class="openFaq === index ? 'text-brand' : ''"
              aria-hidden="true"
            >
              {{ openFaq === index ? '−' : '+' }}
            </span>
          </button>
          <div
            :id="`geo-faq-${index}`"
            class="grid transition-[grid-template-rows] duration-200 ease-out"
            :class="openFaq === index ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
          >
            <div class="overflow-hidden">
              <p class="pb-3 pr-6 text-xs leading-relaxed text-muted sm:text-sm">{{ item.a }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="mt-5 border-t border-line/70 pt-4">
        <h2 class="text-base font-bold text-ink sm:text-lg">使用说明与边界</h2>
        <p
          class="mt-1 overflow-x-auto whitespace-nowrap text-sm leading-snug text-muted sm:text-base"
        >
          请仅处理你有权保存的公开内容。公网部署可能面临限流与合规风险；当前按本机学习场景设计。详细声明见页脚。
        </p>
        <a
          href="#features"
          class="mt-1.5 inline-flex text-sm font-semibold text-vip-deep underline-offset-2 hover:underline"
        >
          查看 VIP 方案
        </a>
      </div>
    </div>
  </section>
</template>
