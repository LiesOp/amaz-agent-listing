import { apiClient } from './client'
import type { ConversationDetailResponse, ConversationResponse, MessageResponse } from './types'

export interface CreateConversationPayload {
  marketplace?: string
  language?: string
}

export interface SendMessagePayload {
  role?: 'user'
  content: string
}

export interface SendMessageResponse {
  reply: string
  current_step: string
  user_message: MessageResponse
  assistant_message: MessageResponse
}

export function createConversation(payload: CreateConversationPayload = {}) {
  return apiClient<ConversationResponse>('/api/v1/conversations', {
    method: 'POST',
    body: JSON.stringify({
      marketplace: payload.marketplace ?? 'US',
      language: payload.language ?? 'en-US',
    }),
  })
}

export function getConversation(conversationId: string) {
  return apiClient<ConversationDetailResponse>(`/api/v1/conversations/${conversationId}`)
}

export function sendMessage(conversationId: string, payload: SendMessagePayload) {
  return apiClient<SendMessageResponse>(`/api/v1/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      role: payload.role ?? 'user',
      content: payload.content,
    }),
  })
}
