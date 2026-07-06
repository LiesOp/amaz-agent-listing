import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { runAudit as runAuditApi } from '../api/audits'
import {
  type BriefUpsertPayload,
  createBrief as createBriefApi,
  updateBrief as updateBriefApi,
} from '../api/briefs'
import {
  aggregateCompetitorAnalysisByBrief as aggregateCompetitorAnalysisByBriefApi,
  analyzeCompetitor as analyzeCompetitorApi,
  getCompetitorSummary as getCompetitorSummaryApi,
  importCompetitors as importCompetitorsApi,
  type CompetitorImportItem,
} from '../api/competitors'
import { createConversation as createConversationApi } from '../api/conversations'
import { generateDraft as generateDraftApi, rewriteDraft as rewriteDraftApi } from '../api/drafts'
import type {
  AuditResultResponse,
  AggregatedCompetitorAnalysisResponse,
  BriefResponse,
  CompetitorInputResponse,
  CompetitorSummaryResponse,
  ConversationResponse,
  DraftResponse,
} from '../api/types'
import { useTasksStore } from './tasks'

export type WorkflowStep =
  | 'idle'
  | 'collect_brief'
  | 'import_competitors'
  | 'analyze_competitors'
  | 'generate_draft'
  | 'review_audit'

type WorkflowAction =
  | 'createConversation'
  | 'saveBrief'
  | 'importCompetitors'
  | 'analyzeCompetitor'
  | 'aggregateCompetitorAnalysis'
  | 'generateDraft'
  | 'runAudit'
  | 'rewriteDraft'

export const useWorkflowStore = defineStore('workflow', () => {
  const currentStep = ref<WorkflowStep>('idle')
  const conversation = ref<ConversationResponse | null>(null)
  const brief = ref<BriefResponse | null>(null)
  const competitorInputs = ref<CompetitorInputResponse[]>([])
  const competitorSummariesByInputId = ref<Record<string, CompetitorSummaryResponse>>({})
  const aggregatedCompetitorAnalysis = ref<AggregatedCompetitorAnalysisResponse | null>(null)
  const currentDraft = ref<DraftResponse | null>(null)
  const currentAudit = ref<AuditResultResponse | null>(null)
  const rewriteInstructions = ref('')
  const lastError = ref<string | null>(null)
  const lastSuccess = ref<string | null>(null)
  const busyActions = ref<WorkflowAction[]>([])
  const competitorAnalysisJobIds = ref<Record<string, string>>({})

  const conversationId = computed(() => conversation.value?.id ?? null)
  const briefId = computed(() => brief.value?.id ?? null)
  const draftId = computed(() => currentDraft.value?.id ?? null)
  const hasCompletedAnalysis = computed(() => {
    return competitorInputs.value.some((item) => item.status === 'completed')
  })

  function isBusy(action: WorkflowAction) {
    return busyActions.value.includes(action)
  }

  async function runWithBusy<T>(action: WorkflowAction, task: () => Promise<T>): Promise<T | null> {
    lastError.value = null
    lastSuccess.value = null
    busyActions.value = [...new Set([...busyActions.value, action])]
    try {
      return await task()
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '请求失败'
      return null
    } finally {
      busyActions.value = busyActions.value.filter((item) => item !== action)
    }
  }

  function applyStep(step: string | null | undefined, fallback: WorkflowStep) {
    if (step === 'audit_draft') {
      currentStep.value = 'review_audit'
      return
    }

    const allowed = new Set<WorkflowStep>([
      'idle',
      'collect_brief',
      'import_competitors',
      'analyze_competitors',
      'generate_draft',
      'review_audit',
    ])
    currentStep.value = allowed.has(step as WorkflowStep) ? (step as WorkflowStep) : fallback
  }

  async function createConversation(payload = { marketplace: 'US', language: 'en-US' }) {
    return runWithBusy('createConversation', async () => {
      const response = await createConversationApi(payload)
      conversation.value = response
      applyStep(response.current_step, 'collect_brief')
      lastSuccess.value = '会话已创建。'
      return response
    })
  }

  async function saveBrief(payload: BriefUpsertPayload) {
    return runWithBusy('saveBrief', async () => {
      if (!conversationId.value) {
        throw new Error('请先创建会话，再保存产品简报。')
      }

      const requestPayload = {
        ...payload,
        conversation_id: conversationId.value,
        marketplace: payload.marketplace ?? conversation.value?.marketplace ?? 'US',
        language: payload.language ?? conversation.value?.language ?? 'en-US',
      }
      const response = briefId.value
        ? await updateBriefApi(briefId.value, requestPayload)
        : await createBriefApi(requestPayload)

      brief.value = response
      currentStep.value = response.is_ready_for_generation ? 'import_competitors' : 'collect_brief'
      lastSuccess.value = response.is_ready_for_generation
        ? '产品简报已保存，可以导入竞品。'
        : '产品简报已保存，请补全缺失字段后再生成。'
      return response
    })
  }

  async function importCompetitors(items: CompetitorImportItem[]) {
    return runWithBusy('importCompetitors', async () => {
      if (!conversationId.value || !briefId.value) {
        throw new Error('请先保存完整产品简报，再导入竞品。')
      }

      const response = await importCompetitorsApi({
        conversation_id: conversationId.value,
        brief_id: briefId.value,
        items,
      })
      competitorInputs.value = [...response.items, ...competitorInputs.value]
      currentStep.value = 'analyze_competitors'
      const tasks = useTasksStore()
      response.analysis_jobs.forEach((job) => {
        competitorAnalysisJobIds.value[job.competitor_input_id] = job.job_id
        tasks.addJob(job.job_id)
        registerCompetitorSummaryFetch(job.job_id, job.competitor_input_id)
        tasks.pollJob(job.job_id)
      })
      lastSuccess.value = `已导入 ${response.imported_count} 个竞品输入。`
      return response
    })
  }

  async function analyzeCompetitor(competitorInputId: string) {
    return runWithBusy('analyzeCompetitor', async () => {
      const existingJobId = competitorAnalysisJobIds.value[competitorInputId]
      const tasks = useTasksStore()
      if (existingJobId) {
        const existingJob = await tasks.fetchJob(existingJobId)
        if (existingJob?.status === 'queued' || existingJob?.status === 'running') {
          registerCompetitorSummaryFetch(existingJobId, competitorInputId)
          tasks.pollJob(existingJobId)
          lastSuccess.value = '已刷新现有竞品分析任务。'
          return null
        }
        delete competitorAnalysisJobIds.value[competitorInputId]
      }

      const response = await analyzeCompetitorApi(competitorInputId)
      competitorAnalysisJobIds.value[competitorInputId] = response.job_id
      if (response.summary) {
        competitorSummariesByInputId.value[competitorInputId] = response.summary
        competitorInputs.value = competitorInputs.value.map((item) =>
          item.id === competitorInputId ? { ...item, status: 'completed' } : item,
        )
      }
      tasks.addJob(response.job_id)
      if (response.status === 'completed' || response.summary) {
        lastSuccess.value = '已加载竞品分析内容。'
      } else {
        registerCompetitorSummaryFetch(response.job_id, competitorInputId)
        tasks.pollJob(response.job_id)
        lastSuccess.value = '竞品分析任务已排队。'
      }
      return response
    })
  }

  function getCompetitorAnalysisJobId(competitorInputId: string) {
    return competitorAnalysisJobIds.value[competitorInputId] ?? null
  }

  async function fetchCompetitorSummary(competitorInputId: string) {
    const summary = await getCompetitorSummaryApi(competitorInputId)
    competitorSummariesByInputId.value = {
      ...competitorSummariesByInputId.value,
      [competitorInputId]: summary,
    }
    competitorInputs.value = competitorInputs.value.map((item) =>
      item.id === competitorInputId ? { ...item, status: 'completed' } : item,
    )
    return summary
  }

  async function aggregateCompetitorAnalysis() {
    return runWithBusy('aggregateCompetitorAnalysis', async () => {
      if (!briefId.value) {
        throw new Error('请先保存完整产品 Brief，再进行聚合竞品分析。')
      }
      const completedCount = Object.keys(competitorSummariesByInputId.value).length
      if (!completedCount) {
        throw new Error('请先完成至少一个单品竞品分析，再进行聚合分析。')
      }
      if (completedCount < competitorInputs.value.length) {
        throw new Error('Please wait until every competitor analysis has finished before aggregating.')
      }
      const response = await aggregateCompetitorAnalysisByBriefApi(briefId.value)
      aggregatedCompetitorAnalysis.value = response
      lastSuccess.value = '聚合竞品分析已完成。'
      return response
    })
  }

  function registerCompetitorSummaryFetch(jobId: string, competitorInputId: string) {
    useTasksStore().onJobCompleted(jobId, async (job) => {
      if (job.status === 'completed') {
        await fetchCompetitorSummary(competitorInputId)
      }
    })
  }

  async function generateDraft(customPrompt = '') {
    return runWithBusy('generateDraft', async () => {
      if (!briefId.value) {
        throw new Error('请先保存完整产品简报，再生成文案。')
      }

      const response = await generateDraftApi(briefId.value, customPrompt)
      currentDraft.value = response.draft
      currentAudit.value = response.audit
      currentStep.value = 'review_audit'
      lastSuccess.value = '文案已生成并完成审核。'
      return response
    })
  }

  async function runAudit() {
    return runWithBusy('runAudit', async () => {
      if (!draftId.value) {
        throw new Error('请先生成文案，再运行审核。')
      }

      const response = await runAuditApi(draftId.value)
      currentAudit.value = response.audit
      currentStep.value = 'review_audit'
      lastSuccess.value = '审核结果已刷新。'
      return response
    })
  }

  async function rewriteDraft() {
    return runWithBusy('rewriteDraft', async () => {
      if (!draftId.value) {
        throw new Error('请先生成文案，再进行改写。')
      }
      if (!rewriteInstructions.value.trim()) {
        throw new Error('请填写改写要求。')
      }

      const response = await rewriteDraftApi(draftId.value, rewriteInstructions.value.trim())
      currentDraft.value = response.draft
      currentAudit.value = response.audit
      currentStep.value = 'review_audit'
      lastSuccess.value = '文案已改写并完成审核。'
      return response
    })
  }

  function resetWorkflow() {
    currentStep.value = 'idle'
    conversation.value = null
    brief.value = null
    competitorInputs.value = []
    competitorSummariesByInputId.value = {}
    aggregatedCompetitorAnalysis.value = null
    competitorAnalysisJobIds.value = {}
    currentDraft.value = null
    currentAudit.value = null
    rewriteInstructions.value = ''
    lastError.value = null
    lastSuccess.value = null
  }

  return {
    currentStep,
    conversation,
    brief,
    competitorInputs,
    competitorSummariesByInputId,
    aggregatedCompetitorAnalysis,
    currentDraft,
    currentAudit,
    rewriteInstructions,
    lastError,
    lastSuccess,
    busyActions,
    competitorAnalysisJobIds,
    conversationId,
    briefId,
    draftId,
    hasCompletedAnalysis,
    isBusy,
    createConversation,
    saveBrief,
    importCompetitors,
    analyzeCompetitor,
    aggregateCompetitorAnalysis,
    getCompetitorAnalysisJobId,
    fetchCompetitorSummary,
    generateDraft,
    runAudit,
    rewriteDraft,
    resetWorkflow,
  }
})
