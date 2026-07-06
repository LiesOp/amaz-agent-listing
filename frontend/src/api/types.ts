export type IsoDateTime = string
export type JsonObject = Record<string, unknown>

export interface ConversationResponse {
  id: string
  status: string
  current_step: string
  marketplace: string
  language: string
  active_brief_id: string | null
  active_draft_id: string | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface MessageResponse {
  id: string
  role: string
  content: string
  created_at: IsoDateTime
}

export interface ConversationDetailResponse extends ConversationResponse {
  messages: MessageResponse[]
}

export interface BriefResponse {
  id: string
  conversation_id: string
  product_name: string | null
  brand: string | null
  category: string | null
  marketplace: string
  language: string
  core_features: string[] | null
  materials: string[] | null
  color: string | null
  quantity: string | null
  size_info: string | null
  target_audience: string | null
  keywords_seed: string[] | null
  completeness_score: number
  missing_required_fields: string[]
  is_ready_for_generation: boolean
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface CompetitorInputResponse {
  id: string
  conversation_id: string
  brief_id: string | null
  input_type: string
  input_value: string
  normalized_url: string | null
  asin: string | null
  status: string
  created_at: IsoDateTime
}

export interface CompetitorImportResponse {
  job_id: string
  status: string
  imported_count: number
  items: CompetitorInputResponse[]
  analysis_jobs: Array<{
    competitor_input_id: string
    job_id: string
    status: string
  }>
}

export interface CompetitorSummaryResponse {
  id: string
  competitor_input_id: string
  brief_id: string | null
  title: string | null
  bullets: string[] | null
  description_text: string | null
  search_terms: string[] | null
  feature_summary: string[] | null
  keyword_summary: string[] | null
  risk_summary: string[] | null
  raw_content_snapshot: string | null
  extraction_result: JsonObject | null
  analysis_result: JsonObject | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface CompetitorAnalysisResponse {
  job_id: string
  status: string
  competitor_input_id: string
  summary: CompetitorSummaryResponse | null
  error_message: string | null
}

export interface AggregatedCompetitorAnalysisResponse {
  id: string
  brief_id: string
  conversation_id: string | null
  status: string
  competitor_count: number
  report: JsonObject | null
  action_brief: JsonObject | null
  constraints: JsonObject | null
  error_message: string | null
  model_name: string | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface CompetitorAnalysisListResponse {
  items: AggregatedCompetitorAnalysisResponse[]
}

export interface RuleItemResponse {
  id: string
  rule_category: string
  rule_title: string
  rule_content: string
  rule_schema: Record<string, unknown> | null
  rule_scope: string
  rule_level: string
  priority: number
  is_active: boolean
  source_note: string | null
  version_no: number
  created_by: string | null
  updated_by: string | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface RuleListResponse {
  items: RuleItemResponse[]
}

export interface RuleGroupedResponse {
  groups: Array<{
    category: string
    items: RuleItemResponse[]
  }>
}

export interface RuleCreateRequest {
  rule_category: string
  rule_title: string
  rule_content: string
  rule_schema?: Record<string, unknown> | null
  rule_scope?: string
  rule_level?: string
  priority?: number
  is_active?: boolean
  source_note?: string | null
  created_by?: string | null
  updated_by?: string | null
}

export interface RuleUpdateRequest extends RuleCreateRequest {
  updated_by?: string | null
}

export interface RuleStatusUpdateRequest {
  is_active: boolean
  updated_by?: string | null
}

export interface DraftResponse {
  id: string
  conversation_id: string
  brief_id: string | null
  title: string | null
  bullets: string[] | null
  description_fields: DescriptionFieldsResponse | null
  description_text: string | null
  search_terms: string[] | null
  generation_context: JsonObject | null
  version_no: number
  created_at: IsoDateTime
}

export interface DescriptionSpecificationResponse {
  brand: string
  name: string
  color: string
  material: string
  size: string
  applicable: string
}

export interface DescriptionFieldsResponse {
  description_title: string
  specification: DescriptionSpecificationResponse
  features: string[]
}

export interface AuditResultResponse {
  id: string
  draft_id: string
  status: string
  risk_score: number
  findings: JsonObject[] | null
  suggestions: string[] | null
  used_rule_ids: string[] | null
  rule_trace: JsonObject | null
  competitor_strategy_trace: JsonObject | null
  validation_trace: JsonObject | null
  created_at: IsoDateTime
}

export interface DraftGenerateResponse {
  draft: DraftResponse
  audit: AuditResultResponse
}

export interface DraftRewriteResponse {
  draft: DraftResponse
  audit: AuditResultResponse
}

export interface AuditCreateResponse {
  audit: AuditResultResponse
}

export interface JobResponse {
  id: string
  job_type: string
  related_id: string | null
  status: string
  payload: JsonObject | unknown[] | null
  result_summary: string | null
  error_message: string | null
  started_at: IsoDateTime | null
  finished_at: IsoDateTime | null
  created_at: IsoDateTime
}

export interface ModelConfigResponse {
  id: string
  display_name: string
  provider: string
  model_name: string
  base_url: string | null
  thinking_config: string
  is_active: boolean
  has_api_key: boolean
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface ModelConfigListResponse {
  items: ModelConfigResponse[]
}

export interface ModelConfigCreateRequest {
  display_name: string
  provider: string
  model_name: string
  api_key: string
  base_url?: string | null
  thinking_config?: string
  is_active?: boolean
}

export interface ModelConfigUpdateRequest {
  display_name: string
  provider: string
  model_name: string
  api_key?: string | null
  base_url?: string | null
  thinking_config?: string
}

export interface ModelInvocationLogResponse {
  id: string
  model_config_id: string
  feature_name: string
  api_endpoint: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  created_at: IsoDateTime
}

export interface ModelInvocationLogListResponse {
  items: ModelInvocationLogResponse[]
  total: number
  page: number
  page_size: number
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
  database: {
    status: string
    error: string | null
  }
  langchain: {
    installed: boolean
    provider_configured: boolean
    model: string
  }
}

export interface CopywritingConversationInfo {
  id: string
  status: string
  current_step: string
  marketplace: string
  language: string
  active_brief_id: string | null
  active_draft_id: string | null
  created_at: IsoDateTime
  updated_at: IsoDateTime
}

export interface CopywritingRecordResponse {
  conversation: CopywritingConversationInfo
  product: BriefResponse | null
  product_name: string | null
  competitor_asins: string[]
  competitor_analysis_id: string | null
  created_at: IsoDateTime
}

export interface CopywritingRecordListResponse {
  items: CopywritingRecordResponse[]
  total: number
  page: number
  page_size: number
}

export interface CopywritingDraftAuditPageResponse {
  draft: DraftResponse | null
  audits: AuditResultResponse[]
  total: number
  page: number
  page_size: number
}
