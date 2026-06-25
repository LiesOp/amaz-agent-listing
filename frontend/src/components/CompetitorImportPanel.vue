<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <p class="eyebrow">竞品</p>
        <h2>导入与分析</h2>
      </div>
      <button type="button" :disabled="!workflow.briefId || workflow.isBusy('importCompetitors')" @click="submit">
        {{ workflow.isBusy('importCompetitors') ? '导入中...' : '导入' }}
      </button>
    </div>

    <div class="competitor-input-list">
      <div v-for="(entry, index) in entries" :key="entry.id" class="competitor-input-row">
        <select v-model="entry.inputType" :disabled="!workflow.briefId">
          <option value="auto">自动</option>
          <option value="asin">ASIN</option>
          <option value="url">URL</option>
        </select>
        <input
          v-model="entry.value"
          :disabled="!workflow.briefId"
          :placeholder="index === 0 ? 'B0CJTFPSLM 或亚马逊链接' : 'ASIN 或亚马逊链接'"
          @input="ensureTrailingEmptyRow"
        />
        <button
          type="button"
          class="secondary-button icon-button"
          :disabled="entries.length === 1"
          @click="removeEntry(entry.id)"
        >
          -
        </button>
      </div>
    </div>

    <button type="button" class="secondary-button add-row-button" :disabled="!workflow.briefId" @click="addEntry">
      添加输入项
    </button>

    <div v-if="validationError" class="alert alert-warning">{{ validationError }}</div>

    <div v-if="workflow.competitorInputs.length" class="competitor-list">
      <div v-for="item in workflow.competitorInputs" :key="item.id" class="competitor-row">
        <div class="competitor-main">
          <strong>{{ item.asin || item.input_value }}</strong>
          <span class="muted">{{ displayCompetitorStatus(item.status) }} - {{ displayInputType(item.input_type) }}</span>
          <span v-if="analysisJobId(item.id)" class="muted">
            任务 {{ analysisJobId(item.id) }} - {{ displayStatus(analysisJobStatus(item.id)) }}
          </span>
        </div>
        <button
          type="button"
          class="compact-button"
          :disabled="workflow.isBusy('analyzeCompetitor') || isAnalysisLocked(item.id)"
          @click="analyze(item.id)"
        >
          {{ analyzeButtonLabel(item.id) }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'

import type { CompetitorImportItem } from '../api/competitors'
import { useTasksStore } from '../stores/tasks'
import { useWorkflowStore } from '../stores/workflow'

type InputType = 'auto' | 'asin' | 'url'

interface CompetitorEntry {
  id: number
  inputType: InputType
  value: string
}

let nextEntryId = 1
const workflow = useWorkflowStore()
const tasks = useTasksStore()
const entries = reactive<CompetitorEntry[]>([createEntry()])
const validationError = ref<string | null>(null)

function createEntry(): CompetitorEntry {
  const id = nextEntryId
  nextEntryId += 1
  return {
    id,
    inputType: 'auto',
    value: '',
  }
}

function addEntry() {
  entries.push(createEntry())
}

function removeEntry(entryId: number) {
  const index = entries.findIndex((entry) => entry.id === entryId)
  if (index >= 0) {
    entries.splice(index, 1)
  }
  if (!entries.length) {
    addEntry()
  }
}

function ensureTrailingEmptyRow() {
  const last = entries[entries.length - 1]
  if (last?.value.trim()) {
    addEntry()
  }
}

function parseItems(): CompetitorImportItem[] {
  return entries
    .map((entry) => ({
      inputType: entry.inputType,
      value: entry.value.trim(),
    }))
    .filter((entry) => Boolean(entry.value))
    .map(normalizeCompetitorInput)
}

function normalizeCompetitorInput(entry: { inputType: InputType; value: string }): CompetitorImportItem {
  const asin = extractAsin(entry.value)
  if (entry.inputType !== 'url' && asin) {
    return {
      input_type: 'asin',
      input_value: asin,
    }
  }

  return {
    input_type: entry.inputType === 'asin' ? 'asin' : 'url',
    input_value: entry.value,
  }
}

function extractAsin(value: string) {
  const normalized = value.trim().toUpperCase()
  const exactMatch = normalized.match(/^[A-Z0-9]{10}$/)
  if (exactMatch) {
    return exactMatch[0]
  }

  const pathMatch = normalized.match(/(?:\/|^)(?:DP|GP\/PRODUCT|PRODUCT)\/?([A-Z0-9]{10})(?:[^A-Z0-9]|$)/)
  if (pathMatch) {
    return pathMatch[1]
  }

  const gluedMatch = normalized.match(/DP([A-Z0-9]{10})(?:[^A-Z0-9]|$)/)
  return gluedMatch?.[1] ?? null
}

async function submit() {
  const items = parseItems()
  if (!items.length) {
    validationError.value = '请至少输入一个 ASIN 或亚马逊链接。'
    return
  }
  const invalid = items.find((item) => item.input_type === 'asin' && !/^[A-Z0-9]{10}$/.test(item.input_value))
  if (invalid) {
    validationError.value = `ASIN 格式不正确：${invalid.input_value}`
    return
  }
  validationError.value = null
  await workflow.importCompetitors(items)
  entries.splice(0, entries.length, createEntry())
}

function analyze(competitorInputId: string) {
  void workflow.analyzeCompetitor(competitorInputId)
}

function analysisJobId(competitorInputId: string) {
  return workflow.getCompetitorAnalysisJobId(competitorInputId)
}

function analysisJobStatus(competitorInputId: string) {
  const jobId = analysisJobId(competitorInputId)
  return jobId ? tasks.jobsById[jobId]?.status || 'queued' : 'none'
}

function isAnalysisLocked(competitorInputId: string) {
  return ['queued', 'running'].includes(analysisJobStatus(competitorInputId))
}

function analyzeButtonLabel(competitorInputId: string) {
  const status = analysisJobStatus(competitorInputId)
  if (status === 'completed') {
    return '已完成'
  }
  if (status === 'running') {
    return '运行中'
  }
  if (status === 'queued') {
    return '已排队'
  }
  if (status === 'failed') {
    return '重试'
  }
  return '分析'
}

function displayStatus(status: string) {
  const labels: Record<string, string> = {
    queued: '已排队',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    pending: '待处理',
    none: '无',
  }
  return labels[status] ?? status
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

function displayInputType(inputType: string) {
  const labels: Record<string, string> = {
    asin: 'ASIN',
    url: 'URL',
    auto: '自动',
  }
  return labels[inputType] ?? inputType
}
</script>
