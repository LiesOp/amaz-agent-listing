import { apiClient } from './client'
import type {
  AggregatedCompetitorAnalysisResponse,
  CompetitorAnalysisResponse,
  CompetitorAnalysisListResponse,
  CompetitorImportResponse,
  CompetitorSummaryResponse,
} from './types'

export interface CompetitorImportItem {
  input_type: 'url' | 'asin'
  input_value: string
}

export interface CompetitorImportPayload {
  conversation_id: string
  brief_id: string
  items: CompetitorImportItem[]
}

export function importCompetitors(payload: CompetitorImportPayload) {
  return apiClient<CompetitorImportResponse>('/api/v1/competitors/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function analyzeCompetitor(competitorInputId: string) {
  return apiClient<CompetitorAnalysisResponse>(`/api/v1/competitors/${competitorInputId}/analyze`, {
    method: 'POST',
  })
}

export function getCompetitorSummary(competitorInputId: string) {
  return apiClient<CompetitorSummaryResponse>(`/api/v1/competitors/${competitorInputId}/summary`)
}

export function listCompetitorAnalyses() {
  return apiClient<CompetitorAnalysisListResponse>('/api/v1/competitors/analyses')
}

export function getCompetitorAnalysis(analysisId: string) {
  return apiClient<AggregatedCompetitorAnalysisResponse>(
    `/api/v1/competitors/analyses/${analysisId}`,
  )
}

export function getCompetitorAnalysisByBrief(briefId: string) {
  return apiClient<AggregatedCompetitorAnalysisResponse>(
    `/api/v1/competitors/by-brief/${briefId}/analysis`,
  )
}

export function aggregateCompetitorAnalysisByBrief(briefId: string) {
  return apiClient<AggregatedCompetitorAnalysisResponse>(
    `/api/v1/competitors/by-brief/${briefId}/aggregate-analysis`,
    {
      method: 'POST',
    },
  )
}
