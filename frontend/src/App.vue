<script setup>
import { nextTick, ref } from 'vue'
import AppHeader from './components/AppHeader.vue'
import HeroSearch from './components/HeroSearch.vue'
import PlatformPills from './components/PlatformPills.vue'
import ParseResult from './components/ParseResult.vue'
import FeaturePlaceholders from './components/FeaturePlaceholders.vue'
import AppFooter from './components/AppFooter.vue'
import { downloadVideo, parseVideo, saveFile } from './api/client'

const url = ref('')
const parsing = ref(false)
const downloading = ref(false)
const error = ref('')
const result = ref(null)
const selectedOptionId = ref('')
const downloadMessage = ref('')

async function onParse() {
  error.value = ''
  downloadMessage.value = ''
  result.value = null
  selectedOptionId.value = ''
  parsing.value = true
  try {
    const data = await parseVideo(url.value.trim())
    result.value = data
    const preferred =
      data.options?.find((o) => o.recommended) || data.options?.[0] || null
    selectedOptionId.value = preferred?.id || ''
    await nextTick()
    document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (e) {
    error.value = e?.message || '解析失败，请稍后重试'
  } finally {
    parsing.value = false
  }
}

async function onDownload() {
  if (!result.value) return
  const option =
    result.value.options?.find((o) => o.id === selectedOptionId.value) ||
    result.value.options?.[0]
  if (!option) {
    error.value = '请选择一个下载选项'
    return
  }
  error.value = ''
  downloadMessage.value = ''
  downloading.value = true
  try {
    const info = await downloadVideo(url.value.trim(), option)
    await saveFile(info.file_id, info.filename)
    downloadMessage.value = '下载完成，文件已开始保存到本地'
  } catch (e) {
    error.value = e?.message || '下载失败，请稍后重试'
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen">
    <AppHeader />
    <main>
      <HeroSearch v-model="url" :loading="parsing" @parse="onParse" />
      <PlatformPills />

      <div v-if="error" class="mx-auto max-w-6xl px-4 pb-4 sm:px-6">
        <div
          role="alert"
          class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-[var(--shadow-elev-1)]"
        >
          {{ error }}
        </div>
      </div>

      <div id="result">
        <ParseResult
          :result="result"
          v-model:selected-option-id="selectedOptionId"
          :downloading="downloading"
          :download-message="downloadMessage"
          @download="onDownload"
        />
      </div>

      <FeaturePlaceholders />
    </main>
    <AppFooter />
  </div>
</template>
