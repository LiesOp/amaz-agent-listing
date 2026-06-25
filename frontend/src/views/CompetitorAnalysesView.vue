<template>
  <section class="analysis-page">
    <div class="panel analysis-list-panel">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Read only</p>
          <h2>竞品分析</h2>
        </div>
        <button type="button" class="secondary-button" :disabled="loading" @click="loadAnalyses">
          刷新
        </button>
      </div>

      <div v-if="loading" class="empty-panel">
        <strong>正在加载竞品分析</strong>
        <span>请稍候。</span>
      </div>

      <div v-else-if="!analyses.length" class="empty-panel">
        <strong>暂无完成的竞品分析</strong>
        <span>完成竞品分析并点击聚合分析后，这里会展示最终报告。</span>
      </div>

      <div v-else class="analysis-report-list">
        <button
          v-for="item in analyses"
          :key="item.id"
          type="button"
          :class="['analysis-report-row', { selected: item.id === selectedId }]"
          @click="selectAnalysis(item.id)"
        >
          <strong>{{ reportTitle(item) }}</strong>
          <span>{{ item.competitor_count }} 个竞品 · {{ displayStatus(item.status) }}</span>
          <span class="muted">{{ formatDate(item.updated_at) }}</span>
        </button>
      </div>
    </div>

    <div class="panel analysis-detail-panel">
      <template v-if="selectedAnalysis">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Analysis report</p>
            <h2>{{ reportTitle(selectedAnalysis) }}</h2>
          </div>
          <span :class="['status-pill', selectedAnalysis.status === 'completed' ? 'status-success' : 'status-warning']">
            {{ displayStatus(selectedAnalysis.status) }}
          </span>
        </div>

        <dl class="meta-list compact">
          <div>
            <dt>Brief ID</dt>
            <dd>{{ selectedAnalysis.brief_id }}</dd>
          </div>
          <div>
            <dt>竞品数量</dt>
            <dd>{{ selectedAnalysis.competitor_count }}</dd>
          </div>
          <div>
            <dt>生成方式</dt>
            <dd>{{ selectedAnalysis.model_name || 'unknown' }}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{{ formatDate(selectedAnalysis.updated_at) }}</dd>
          </div>
        </dl>

        <section class="report-section">
          <h3>市场共性洞察</h3>
          <div class="tag-grid">
            <span v-for="item in marketPatternItems" :key="item">{{ item }}</span>
          </div>
          <p v-if="!marketPatternItems.length" class="muted">暂无市场共性数据。</p>
        </section>

        <section class="report-section">
          <h3>关键词分析</h3>
          <div class="tag-grid">
            <span v-for="item in keywordItems" :key="item">{{ item }}</span>
          </div>
          <p v-if="!keywordItems.length" class="muted">暂无关键词数据。</p>
        </section>

        <section class="report-section">
          <h3>竞品对比矩阵</h3>
          <div v-if="comparisonRows.length" class="data-table">
            <div class="data-table-head competitor-analysis-grid">
              <span>竞品</span>
              <span>卖点</span>
              <span>关键词</span>
              <span>风险</span>
            </div>
            <div
              v-for="row in comparisonRows"
              :key="String(row.competitor_input_id || row.title)"
              class="data-table-row competitor-analysis-grid"
            >
              <strong>{{ row.title || row.competitor_input_id || 'unknown' }}</strong>
              <span>{{ listText(row.features) }}</span>
              <span>{{ listText(row.keywords) }}</span>
              <span>{{ listText(row.risk_terms) }}</span>
            </div>
          </div>
          <p v-else class="muted">暂无对比矩阵。</p>
        </section>

        <section class="report-section">
          <h3>差异化机会</h3>
          <ul v-if="differentiationOpportunities.length" class="content-list">
            <li v-for="item in differentiationOpportunities" :key="item">{{ item }}</li>
          </ul>
          <p v-else class="muted">暂无差异化机会。</p>
        </section>

        <section class="report-section">
          <h3>风险与合规提示</h3>
          <div class="tag-grid danger-tags">
            <span v-for="item in riskItems" :key="item">{{ item }}</span>
          </div>
          <p v-if="!riskItems.length" class="muted">暂无风险提示。</p>
        </section>

        <section class="report-section">
          <h3>Listing 生成策略</h3>
          <dl class="strategy-list">
            <div>
              <dt>定位策略</dt>
              <dd>{{ listingStrategy.positioning || '暂无' }}</dd>
            </div>
            <div>
              <dt>标题策略</dt>
              <dd>{{ listText(listingStrategy.title_strategy) }}</dd>
            </div>
            <div>
              <dt>五点策略</dt>
              <dd>{{ listText(listingStrategy.bullet_strategy) }}</dd>
            </div>
            <div>
              <dt>描述策略</dt>
              <dd>{{ listText(listingStrategy.description_strategy) }}</dd>
            </div>
            <div>
              <dt>搜索词策略</dt>
              <dd>{{ listText(listingStrategy.keyword_strategy) }}</dd>
            </div>
            <div>
              <dt>规避策略</dt>
              <dd>{{ listText(listingStrategy.avoid_strategy) }}</dd>
            </div>
          </dl>
        </section>
      </template>

      <div v-else class="empty-panel">
        <strong>请选择一份竞品分析</strong>
        <span>这里仅展示已经完成的聚合竞品分析报告。</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listCompetitorAnalyses } from '../api/competitors'
import type { AggregatedCompetitorAnalysisResponse, JsonObject } from '../api/types'
import { formatDateTime } from '../utils/datetime'

type ReportRecord = Record<string, unknown>
type MatrixRow = {
  competitor_input_id?: string | null
  title?: string | null
  features?: unknown
  keywords?: unknown
  risk_terms?: unknown
}
type ListingStrategy = {
  positioning?: string | null
  title_strategy?: unknown
  bullet_strategy?: unknown
  description_strategy?: unknown
  keyword_strategy?: unknown
  avoid_strategy?: unknown
}

const analyses = ref<AggregatedCompetitorAnalysisResponse[]>([])
const selectedId = ref<string | null>(null)
const loading = ref(false)
const route = useRoute()
const router = useRouter()

const selectedAnalysis = computed(() =>
  analyses.value.find((item) => item.id === selectedId.value) ?? analyses.value[0] ?? null,
)

const report = computed<ReportRecord>(() => asRecord(selectedAnalysis.value?.report))
const marketPatterns = computed(() => asRecord(report.value.market_patterns))
const keywordInsights = computed(() => asRecord(report.value.keyword_insights))
const listingStrategy = computed<ListingStrategy>(() =>
  asRecord(report.value.recommended_listing_strategy) as ListingStrategy,
)

const marketPatternItems = computed(() =>
  textList([
    ...toArray(marketPatterns.value.common_features),
    ...toArray(marketPatterns.value.common_benefits),
    ...toArray(marketPatterns.value.common_scenarios),
    ...toArray(marketPatterns.value.common_audiences),
    ...toArray(marketPatterns.value.common_keywords),
    ...toArray(marketPatterns.value.common_title_patterns),
    ...toArray(marketPatterns.value.common_bullet_patterns),
  ]),
)

const keywordItems = computed(() =>
  textList([
    ...toArray(keywordInsights.value.primary),
    ...toArray(keywordInsights.value.long_tail),
    ...toArray(keywordInsights.value.attributes),
  ]),
)

const comparisonRows = computed<MatrixRow[]>(() =>
  toArray(report.value.comparison_matrix).filter((item): item is MatrixRow => isRecord(item)),
)

const differentiationOpportunities = computed(() =>
  textList(toArray(report.value.differentiation_opportunities)),
)

const riskItems = computed(() =>
  textList([...toArray(report.value.risk_summary), ...toArray(keywordInsights.value.risk_terms)]),
)

onActivated(() => {
  void loadAnalyses()
})

watch(
  () => route.query.analysis_id,
  (analysisId) => {
    if (!selectAnalysisFromQuery(analysisId)) {
      void loadAnalyses()
    }
  },
)

async function loadAnalyses() {
  loading.value = true
  try {
    const response = await listCompetitorAnalyses()
    analyses.value = response.items
    const querySelected = selectAnalysisFromQuery(route.query.analysis_id)
    if (!querySelected && !selectedId.value && response.items.length) {
      selectedId.value = response.items[0].id
    }
  } finally {
    loading.value = false
  }
}

function selectAnalysis(id: string) {
  selectedId.value = id
  void router.replace({
    name: 'competitor-analyses',
    query: { ...route.query, analysis_id: id },
  })
}

function selectAnalysisFromQuery(analysisId: unknown) {
  const id = Array.isArray(analysisId) ? analysisId[0] : analysisId
  if (typeof id !== 'string' || !id) {
    return false
  }
  if (!analyses.value.some((item) => item.id === id)) {
    return false
  }
  selectedId.value = id
  return true
}

function reportTitle(item: AggregatedCompetitorAnalysisResponse) {
  const itemReport = asRecord(item.report)
  const brief = asRecord(itemReport.brief)
  const productName = typeof brief.product_name === 'string' ? brief.product_name : null
  return productName || `竞品分析 ${item.id}`
}

function displayStatus(status: string) {
  const labels: Record<string, string> = {
    completed: '已完成',
    failed: '失败',
    running: '分析中',
  }
  return labels[status] ?? status
}

function formatDate(value: string) {
  return formatDateTime(value)
}

function listText(value: unknown) {
  const values = textList(toArray(value))
  return values.length ? values.join(', ') : '暂无'
}

function asRecord(value: unknown): ReportRecord {
  return isRecord(value) ? value : {}
}

function isRecord(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function toArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function textList(values: unknown[]) {
  return values
    .filter((item): item is string | number => typeof item === 'string' || typeof item === 'number')
    .map((item) => String(item).trim())
    .filter(Boolean)
}
</script>
