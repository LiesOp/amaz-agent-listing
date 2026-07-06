<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">Copywriting</p>
        <h2>文案记录</h2>
      </div>
      <button type="button" class="secondary-button" :disabled="loading" @click="loadRecords">刷新</button>
    </div>

    <div v-if="loading" class="empty-panel">
      <strong>正在加载文案记录</strong>
      <span>请稍候。</span>
    </div>
    <div v-else-if="!records.length" class="empty-panel">
      <strong>暂无会话记录</strong>
      <span>创建会话并生成文案后，这里会展示对应记录。</span>
    </div>

    <div v-else class="data-table">
      <div class="data-table-head copywriting-grid">
        <span>会话信息</span>
        <span>产品名称</span>
        <span>竞品 ASIN</span>
        <span>聚合分析 ID</span>
        <span>创建时间</span>
        <span>操作</span>
      </div>
      <div v-for="item in records" :key="item.conversation.id" class="data-table-row copywriting-grid">
        <div>
          <strong>{{ item.conversation.id }}</strong>
          <span class="muted">{{ item.conversation.status }} / {{ item.conversation.current_step }}</span>
        </div>
        <button type="button" class="text-link" :disabled="!item.product" @click="openProduct(item)">
          {{ item.product_name || '未填写产品名称' }}
        </button>
        <span>{{ item.competitor_asins.length ? item.competitor_asins.join(', ') : '暂无' }}</span>
        <RouterLink
          v-if="item.competitor_analysis_id"
          class="source-link"
          :to="{ name: 'competitor-analyses', query: { analysis_id: item.competitor_analysis_id } }"
        >
          {{ item.competitor_analysis_id }}
        </RouterLink>
        <span v-else class="muted">暂无</span>
        <span>{{ formatDate(item.created_at) }}</span>
        <button type="button" class="secondary-button compact-button" @click="openDetails(item)">详情</button>
      </div>
    </div>

    <div class="pagination-bar">
      <span>共 {{ total }} 条，第 {{ page }} / {{ totalPages }} 页</span>
      <div class="button-group">
        <button type="button" class="secondary-button" :disabled="page <= 1 || loading" @click="changePage(page - 1)">
          上一页
        </button>
        <button type="button" class="secondary-button" :disabled="page >= totalPages || loading" @click="changePage(page + 1)">
          下一页
        </button>
      </div>
    </div>
  </section>

  <div v-if="productRecord?.product" class="modal-overlay" @click.self="closeProduct">
    <section class="modal-panel">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Product</p>
          <h2>{{ productRecord.product.product_name || '产品明细' }}</h2>
        </div>
        <button type="button" class="secondary-button compact-button" @click="closeProduct">关闭</button>
      </div>
      <dl class="meta-list">
        <div><dt>产品 ID</dt><dd>{{ productRecord.product.id }}</dd></div>
        <div><dt>品牌</dt><dd>{{ productRecord.product.brand || '暂无' }}</dd></div>
        <div><dt>类目</dt><dd>{{ productRecord.product.category || '暂无' }}</dd></div>
        <div><dt>颜色</dt><dd>{{ productRecord.product.color || '暂无' }}</dd></div>
        <div><dt>数量</dt><dd>{{ productRecord.product.quantity || '暂无' }}</dd></div>
        <div><dt>站点 / 语言</dt><dd>{{ productRecord.product.marketplace }} / {{ productRecord.product.language }}</dd></div>
        <div><dt>核心卖点</dt><dd>{{ listText(productRecord.product.core_features) }}</dd></div>
        <div><dt>材质</dt><dd>{{ listText(productRecord.product.materials) }}</dd></div>
        <div><dt>尺寸信息</dt><dd>{{ productRecord.product.size_info || '暂无' }}</dd></div>
        <div><dt>目标人群</dt><dd>{{ productRecord.product.target_audience || '暂无' }}</dd></div>
        <div><dt>种子关键词</dt><dd>{{ listText(productRecord.product.keywords_seed) }}</dd></div>
        <div><dt>完整度</dt><dd>{{ productRecord.product.completeness_score }}</dd></div>
      </dl>
    </section>
  </div>

  <div v-if="detailRecord" class="modal-overlay" @click.self="closeDetails">
    <section class="modal-panel copywriting-detail-modal">
      <div class="panel-header">
        <div>
          <p class="eyebrow">Draft audit</p>
          <h2>{{ detailRecord.product_name || detailRecord.conversation.id }}</h2>
        </div>
        <button type="button" class="secondary-button compact-button" @click="closeDetails">关闭</button>
      </div>

      <div v-if="detailLoading" class="empty-panel">
        <strong>正在加载文案详情</strong>
        <span>请稍候。</span>
      </div>
      <template v-else>
        <div v-if="!draftAuditPage?.draft" class="empty-panel">
          <strong>暂无文案信息</strong>
          <span>当前会话还没有生成文案。</span>
        </div>
        <div v-else class="copywriting-detail-grid">
          <section class="inset-panel">
            <h3>文案信息</h3>
            <dl class="strategy-list">
              <div><dt>文案 ID</dt><dd>{{ draftAuditPage.draft.id }}</dd></div>
              <div><dt>版本</dt><dd>{{ draftAuditPage.draft.version_no }}</dd></div>
              <div><dt>标题</dt><dd>{{ draftAuditPage.draft.title || '暂无' }}</dd></div>
              <div>
                <dt>五点描述</dt>
                <dd>
                  <ul v-if="draftAuditPage.draft.bullets?.length" class="content-list">
                    <li v-for="(bullet, index) in draftAuditPage.draft.bullets" :key="index">{{ bullet }}</li>
                  </ul>
                  <span v-else class="muted">暂无</span>
                </dd>
              </div>
              <div class="long-description-field">
                <dt>长描述</dt>
                <dd>
                  <pre v-if="draftAuditPage.draft.description_text" class="long-description-text">
                    {{ formatLongDescription(draftAuditPage.draft.description_text) }}
                  </pre>
                  <span v-else class="muted">暂无</span>
                </dd>
              </div>
              <div>
                <dt>Search Terms</dt>
                <dd>
                  <pre v-if="draftAuditPage.draft.search_terms?.length" class="line-list-text">
                    {{ formatLines(draftAuditPage.draft.search_terms) }}
                  </pre>
                  <span v-else class="muted">暂无</span>
                </dd>
              </div>
              <div><dt>创建时间</dt><dd>{{ formatDate(draftAuditPage.draft.created_at) }}</dd></div>
            </dl>
          </section>

          <section class="inset-panel">
            <h3>审核信息</h3>
            <div v-if="!draftAuditPage.audits.length" class="empty-panel">
              <strong>暂无审核结果</strong>
              <span>当前文案没有关联审核记录。</span>
            </div>
            <div v-else class="stack-sm">
              <article v-for="audit in draftAuditPage.audits" :key="audit.id" class="audit-card">
                <div class="status-heading">
                  <strong>{{ audit.id }}</strong>
                  <span :class="['status-pill', auditStatusClass(audit.status)]">
                    {{ displayAuditStatus(audit.status) }}
                  </span>
                </div>
                <dl class="strategy-list">
                  <div><dt>风险分</dt><dd>{{ audit.risk_score }}</dd></div>
                  <div>
                    <dt>问题</dt>
                    <dd>
                      <ul v-if="audit.findings?.length" class="content-list">
                        <li v-for="(finding, index) in audit.findings" :key="index">
                          {{ formatFinding(finding) }}
                        </li>
                      </ul>
                      <span v-else class="muted">未发现明显风险。</span>
                    </dd>
                  </div>
                  <div>
                    <dt>建议</dt>
                    <dd>
                      <ul v-if="audit.suggestions?.length" class="content-list">
                        <li v-for="suggestion in audit.suggestions" :key="suggestion">{{ suggestion }}</li>
                      </ul>
                      <span v-else class="muted">暂无建议。</span>
                    </dd>
                  </div>
                  <div><dt>规则 ID</dt><dd>{{ listText(audit.used_rule_ids) }}</dd></div>
                  <div><dt>审核时间</dt><dd>{{ formatDate(audit.created_at) }}</dd></div>
                </dl>
              </article>
            </div>
          </section>
        </div>

        <div class="pagination-bar">
          <span>共 {{ draftAuditPage?.total ?? 0 }} 次文案，第 {{ detailPage }} / {{ detailTotalPages }} 页</span>
          <div class="button-group">
            <button type="button" class="secondary-button" :disabled="detailPage <= 1 || detailLoading" @click="changeDetailPage(detailPage - 1)">
              上一页
            </button>
            <button type="button" class="secondary-button" :disabled="detailPage >= detailTotalPages || detailLoading" @click="changeDetailPage(detailPage + 1)">
              下一页
            </button>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { getCopywritingDraftAudits, listCopywritingRecords } from '../api/copywriting'
import type { CopywritingDraftAuditPageResponse, CopywritingRecordResponse, JsonObject } from '../api/types'
import { formatDateTime } from '../utils/datetime'

const pageSize = 10
const records = ref<CopywritingRecordResponse[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const productRecord = ref<CopywritingRecordResponse | null>(null)
const detailRecord = ref<CopywritingRecordResponse | null>(null)
const draftAuditPage = ref<CopywritingDraftAuditPageResponse | null>(null)
const detailPage = ref(1)
const detailLoading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const detailTotalPages = computed(() => Math.max(1, draftAuditPage.value?.total ?? 0))

onActivated(() => {
  void loadRecords()
})

watch(page, () => {
  void loadRecords()
})

async function loadRecords() {
  loading.value = true
  try {
    const response = await listCopywritingRecords(page.value, pageSize)
    records.value = response.items
    total.value = response.total
  } finally {
    loading.value = false
  }
}

function changePage(nextPage: number) {
  page.value = nextPage
}

function openProduct(item: CopywritingRecordResponse) {
  productRecord.value = item
}

function closeProduct() {
  productRecord.value = null
}

function openDetails(item: CopywritingRecordResponse) {
  detailRecord.value = item
  detailPage.value = 1
  void loadDraftAudits()
}

function closeDetails() {
  detailRecord.value = null
  draftAuditPage.value = null
}

function changeDetailPage(nextPage: number) {
  detailPage.value = nextPage
  void loadDraftAudits()
}

async function loadDraftAudits() {
  if (!detailRecord.value) {
    return
  }
  detailLoading.value = true
  try {
    draftAuditPage.value = await getCopywritingDraftAudits(detailRecord.value.conversation.id, detailPage.value)
  } finally {
    detailLoading.value = false
  }
}

function formatDate(value: string) {
  return formatDateTime(value)
}

function listText(value?: unknown[] | null) {
  const items = Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : []
  return items.length ? items.join(', ') : '暂无'
}

function formatLongDescription(value: string): string {
  return value
    .replace(/\r?\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s*(<p>|&lt;p&gt;)/gi, '\n$1')
    .trim()
}

function formatLines(value: unknown[] | null | undefined): string {
  const items = Array.isArray(value) ? value : []
  return items
    .flatMap((item) => String(item).split(/[,，]/))
    .map((item) => item.trim())
    .filter(Boolean)
    .join('\n')
}

function formatFinding(finding: JsonObject) {
  return Object.entries(finding)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' - ')
}

function formatTrace(value: unknown) {
  if (!value || typeof value !== 'object') {
    return '暂无'
  }
  return JSON.stringify(value, null, 2)
}

function auditStatusClass(status: string) {
  if (status === 'pass' || status === 'passed') {
    return 'status-success'
  }
  if (status === 'fail' || status === 'failed') {
    return 'status-danger'
  }
  return 'status-warning'
}

function displayAuditStatus(status: string) {
  const labels: Record<string, string> = {
    pass: '通过',
    warning: '需注意',
    fail: '未通过',
    passed: '通过',
    failed: '未通过',
  }
  return labels[status] ?? status
}
</script>
