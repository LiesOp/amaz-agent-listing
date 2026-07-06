<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">Competitor insight</p>
        <h2>竞品分析摘要</h2>
      </div>
      <button
        type="button"
        :disabled="!canAggregate || workflow.isBusy('aggregateCompetitorAnalysis')"
        @click="aggregate"
      >
        {{ workflow.isBusy('aggregateCompetitorAnalysis') ? '聚合中...' : '聚合分析' }}
      </button>
    </div>

    <div v-if="analysisItems.length" class="competitor-analysis-list">
      <article v-for="item in analysisItems" :key="item.input.id" class="analysis-card">
        <header class="analysis-card-header">
          <div>
            <strong>{{ item.input.asin || item.input.input_value }}</strong>
            <span class="muted">{{ displayInputType(item.input.input_type) }}</span>
          </div>
          <span :class="['status-pill', item.summary ? 'status-success' : statusClass(item.input.status)]">
            {{ item.summary ? '已生成' : displayCompetitorStatus(item.input.status) }}
          </span>
        </header>

        <template v-if="item.summary">
          <section>
            <h3>核心卖点</h3>
            <ul v-if="sellingPoints(item.summary).length" class="content-list">
              <li v-for="point in sellingPoints(item.summary)" :key="point">{{ point }}</li>
            </ul>
            <p v-else class="muted">暂无卖点分析。</p>
          </section>

          <section>
            <h3>关键词结构</h3>
            <p>{{ listText(primaryKeywords(item.summary)) }}</p>
          </section>

          <section>
            <h3>定位与场景</h3>
            <p>{{ listText(positioningItems(item.summary)) }}</p>
          </section>

          <section>
            <h3>风险提示</h3>
            <p>{{ listText(riskItems(item.summary)) }}</p>
          </section>

          <details class="raw-listing-details">
            <summary>查看原始 Listing 提取内容</summary>
            <section>
              <h3>标题</h3>
              <p>{{ item.summary.title || '暂无标题。' }}</p>
            </section>
            <section>
              <h3>五点描述</h3>
              <ul v-if="item.summary.bullets?.length" class="content-list">
                <li v-for="(bullet, index) in item.summary.bullets" :key="index">{{ bullet }}</li>
              </ul>
              <p v-else class="muted">暂无五点描述。</p>
            </section>
          </details>
        </template>

        <p v-else class="muted">
          分析完成后会在这里展示卖点、关键词、定位、风险等摘要；完成所有需要的单品分析后，点击“聚合分析”生成最终竞品分析报告。
        </p>
      </article>
    </div>

    <div v-else class="empty-panel">
      <strong>暂无竞品分析内容。</strong>
      <span>导入竞品并完成单品分析后，这里会展示摘要，并可手动执行聚合分析。</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { CompetitorSummaryResponse, JsonObject } from '../api/types'
import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()

const analysisItems = computed(() =>
  workflow.competitorInputs.map((input) => ({
    input,
    summary: workflow.competitorSummariesByInputId[input.id],
  })),
)

const canAggregate = computed(
  () =>
    Boolean(workflow.briefId) &&
    analysisItems.value.length > 0 &&
    analysisItems.value.every((item) => item.summary),
)

function aggregate() {
  void workflow.aggregateCompetitorAnalysis()
}

function sellingPoints(summary: CompetitorSummaryResponse) {
  const analysis = asRecord(summary.analysis_result)
  return textList(toArray(analysis.selling_points).length ? toArray(analysis.selling_points) : summary.feature_summary)
}

function primaryKeywords(summary: CompetitorSummaryResponse) {
  const analysis = asRecord(summary.analysis_result)
  const keywordAnalysis = asRecord(analysis.keyword_analysis)
  return textList(
    toArray(keywordAnalysis.primary).length ? toArray(keywordAnalysis.primary) : summary.keyword_summary,
  )
}

function positioningItems(summary: CompetitorSummaryResponse) {
  const analysis = asRecord(summary.analysis_result)
  const positioning = asRecord(analysis.positioning)
  return textList([...toArray(positioning.use_scenarios), ...toArray(positioning.target_audience)])
}

function riskItems(summary: CompetitorSummaryResponse) {
  const analysis = asRecord(summary.analysis_result)
  return textList(toArray(analysis.risk_notes).length ? toArray(analysis.risk_notes) : summary.risk_summary)
}

function displayCompetitorStatus(status: string) {
  const labels: Record<string, string> = {
    pending: '待处理',
    imported: '已导入',
    queued: '已排队',
    running: '分析中',
    completed: '已完成',
    failed: '失败',
  }
  return labels[status] ?? status
}

function statusClass(status: string) {
  if (status === 'failed') {
    return 'status-danger'
  }
  if (status === 'completed') {
    return 'status-success'
  }
  return 'status-warning'
}

function displayInputType(inputType: string) {
  const labels: Record<string, string> = {
    asin: 'ASIN',
    url: 'URL',
    auto: '自动',
  }
  return labels[inputType] ?? inputType
}

function listText(values: string[]) {
  return values.length ? values.join(', ') : '暂无'
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {}
}

function isRecord(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function textList(values: unknown[] | null | undefined) {
  return (values ?? [])
    .filter((item): item is string | number => typeof item === 'string' || typeof item === 'number')
    .map((item) => String(item).trim())
    .filter(Boolean)
}
</script>
