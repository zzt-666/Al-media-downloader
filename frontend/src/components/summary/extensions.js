/**
 * Summary panel extension registry (Open/Closed).
 * Core tabs stay in SummaryPanel; new features register here.
 */
import SummaryMindMapTab from './SummaryMindMapTab.vue'
import SummaryChatTab from './SummaryChatTab.vue'

/** @type {{ id: string, label: string, component: object }[]} */
export const SUMMARY_EXTENSION_TABS = [
  { id: 'mindmap', label: '思维导图', component: SummaryMindMapTab },
  { id: 'chat', label: 'AI 对话', component: SummaryChatTab },
]
