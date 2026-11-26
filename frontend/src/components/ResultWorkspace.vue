<script setup>
import ParseResult from './ParseResult.vue'
import SummaryPanel from './SummaryPanel.vue'

defineProps({
  result: { type: Object, default: null },
  selectedOptionId: { type: String, default: '' },
  downloading: { type: Boolean, default: false },
  downloadMessage: { type: String, default: '' },
  summarizing: { type: Boolean, default: false },
  summary: { type: Object, default: null },
  summaryStreaming: { type: Boolean, default: false },
  summaryStage: { type: String, default: '' },
  summaryError: { type: String, default: '' },
})

const emit = defineEmits([
  'update:selectedOptionId',
  'download',
  'summarize',
])
</script>

<template>
  <section
    v-if="result"
    id="result"
    class="anim-rise mx-auto max-w-6xl scroll-mt-28 px-4 pb-10 sm:px-6"
  >
    <div
      id="result-workspace"
      class="overflow-hidden rounded-3xl border border-line/80 bg-white shadow-[var(--shadow-elev-3)]"
    >
      <div
        class="grid items-start lg:grid-cols-[minmax(280px,2fr)_minmax(0,3fr)] lg:divide-x lg:divide-line/70"
      >
        <aside
          class="min-w-0 self-stretch border-b border-line/70 p-4 sm:p-5 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:border-b-0"
        >
          <ParseResult
            :result="result"
            :selected-option-id="selectedOptionId"
            :downloading="downloading"
            :download-message="downloadMessage"
            :summarizing="summarizing"
            @update:selected-option-id="emit('update:selectedOptionId', $event)"
            @download="emit('download')"
            @summarize="emit('summarize')"
          />
        </aside>

        <div
          id="summary"
          class="flex min-h-0 min-w-0 flex-col self-stretch lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto"
        >
          <SummaryPanel
            :summary="summary"
            :loading="summarizing"
            :streaming="summaryStreaming"
            :stage="summaryStage"
            :error="summaryError"
            embedded
          />
        </div>
      </div>
    </div>
  </section>
</template>
