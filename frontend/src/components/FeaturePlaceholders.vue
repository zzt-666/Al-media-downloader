<script setup>
import { ref } from 'vue'

const tip = ref('')

function onPlanClick(plan) {
  if (plan.id === 'free') {
    tip.value = '免费版已可用，直接在上方粘贴链接即可下载。'
    return
  }
  tip.value = `${plan.name}支付尚未接入，权益即将上线，敬请期待。`
}

const plans = [
  {
    id: 'free',
    name: '免费版',
    price: '¥0',
    period: '永久',
    badge: null,
    highlight: false,
    cta: '当前可用',
    features: ['单链接解析下载', '常见清晰度选择', '本机临时文件', '基础站点支持'],
  },
  {
    id: 'vip',
    name: 'VIP 会员',
    price: '¥19',
    period: '/月',
    badge: '最受欢迎',
    highlight: true,
    cta: '立即开通 VIP',
    features: [
      '批量下载加速队列',
      '高清优先处理',
      'AI 视频总结',
      '字幕翻译多语言',
      '更大并发额度',
    ],
  },
  {
    id: 'pro',
    name: '专业版',
    price: '¥49',
    period: '/月',
    badge: '团队',
    highlight: false,
    cta: '咨询专业版',
    features: ['VIP 全部权益', '专属客服通道', '更高并发与配额', '后续企业能力优先'],
  },
]

const extras = [
  {
    title: 'AI 视频总结',
    desc: '自动提炼要点与章节，复习效率翻倍。',
  },
  {
    title: '字幕翻译',
    desc: '多语言字幕生成与翻译，跨语种无压力。',
  },
  {
    title: '批量加速',
    desc: '排队优先、并发提升，多任务一次搞定。',
  },
]
</script>

<template>
  <section id="features" class="mx-auto max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
    <div class="mx-auto max-w-2xl text-center">
      <p class="text-sm font-semibold tracking-wide text-vip">会员特权</p>
      <h2 class="mt-2 text-2xl font-bold text-ink sm:text-3xl">升级 VIP，下载更快更聪明</h2>
      <p class="mt-3 text-muted">
        免费已够用；想要批量、高清优先和 AI 能力，一键升级。以下为产品占位，支付尚未接入。
      </p>
    </div>

    <div class="mt-10 grid gap-4 lg:grid-cols-3">
      <article
        v-for="plan in plans"
        :key="plan.id"
        class="relative flex flex-col rounded-3xl border bg-white p-6 transition duration-200"
        :class="
          plan.highlight
            ? 'border-vip/40 shadow-[var(--shadow-elev-3)] ring-1 ring-vip/20 lg:-translate-y-1'
            : 'border-line shadow-[var(--shadow-elev-1)] hover:shadow-[var(--shadow-elev-2)]'
        "
      >
        <div
          v-if="plan.badge"
          class="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full px-3 py-1 text-xs font-semibold text-white"
          :class="plan.highlight ? 'bg-gradient-to-r from-vip to-[#d4a017]' : 'bg-ink'"
        >
          {{ plan.badge }}
        </div>

        <h3 class="text-lg font-bold text-ink">{{ plan.name }}</h3>
        <p class="mt-3 flex items-baseline gap-1">
          <span class="text-3xl font-bold tracking-tight text-ink">{{ plan.price }}</span>
          <span class="text-sm text-muted">{{ plan.period }}</span>
        </p>

        <ul class="mt-5 flex-1 space-y-2.5">
          <li
            v-for="item in plan.features"
            :key="item"
            class="flex items-start gap-2 text-sm text-ink/90"
          >
            <span
              class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold"
              :class="plan.highlight ? 'bg-vip-soft text-vip-deep' : 'bg-brand-soft text-brand'"
              aria-hidden="true"
            >
              ✓
            </span>
            <span>{{ item }}</span>
          </li>
        </ul>

        <button
          type="button"
          class="mt-6 min-h-12 w-full cursor-pointer rounded-xl text-sm font-semibold transition duration-200"
          :class="
            plan.highlight
              ? 'bg-gradient-to-r from-vip to-[#d4a017] text-white shadow-[var(--shadow-elev-2)] hover:brightness-105'
              : 'border border-line bg-page text-ink hover:border-brand/30 hover:bg-brand-soft/50'
          "
          @click="onPlanClick(plan)"
        >
          {{ plan.cta }}
          <span v-if="plan.id !== 'free'" class="ml-1 text-xs font-normal opacity-80">· 即将上线</span>
        </button>
      </article>
    </div>

    <p
      v-if="tip"
      role="status"
      class="mx-auto mt-4 max-w-xl rounded-xl border border-vip/20 bg-vip-soft px-4 py-3 text-center text-sm text-vip-deep"
    >
      {{ tip }}
    </p>

    <div class="mt-8 grid gap-3 sm:grid-cols-3">
      <div
        v-for="item in extras"
        :key="item.title"
        class="rounded-2xl border border-line/80 bg-white/80 p-4 shadow-[var(--shadow-elev-1)]"
      >
        <h4 class="font-semibold text-ink">{{ item.title }}</h4>
        <p class="mt-1.5 text-sm leading-relaxed text-muted">{{ item.desc }}</p>
        <span class="mt-3 inline-block text-xs font-medium text-vip">VIP 专属 · 即将上线</span>
      </div>
    </div>
  </section>
</template>
