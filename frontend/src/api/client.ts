import { reactive } from 'vue'

export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue>

export interface ApiRequestState {
  loading: boolean
  lastRequestId: string | null
  lastError: string | null
}

export class ApiError extends Error {
  status: number
  requestId: string | null
  details: unknown

  constructor(message: string, status: number, requestId: string | null, details: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
    this.details = details
  }
}

const baseUrl = import.meta.env.VITE_API_BASE_URL || ''

export const apiRequestState = reactive<ApiRequestState>({
  loading: false,
  lastRequestId: null,
  lastError: null,
})

export interface ApiClientOptions extends RequestInit {
  query?: QueryParams
}

function resolveUrl(path: string, query?: QueryParams) {
  if (/^https?:\/\//.test(path)) {
    const url = new URL(path)
    appendQuery(url.searchParams, query)
    return url.toString()
  }

  const resolvedPath = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
  if (!query) {
    return resolvedPath
  }

  const url = new URL(resolvedPath, window.location.origin)
  appendQuery(url.searchParams, query)
  return baseUrl ? url.toString() : `${url.pathname}${url.search}`
}

function appendQuery(searchParams: URLSearchParams, query?: QueryParams) {
  if (!query) {
    return
  }

  Object.entries(query).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') {
      return
    }
    searchParams.set(key, String(value))
  })
}

function getErrorMessage(payload: unknown, fallback: string) {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
    return JSON.stringify(detail)
  }

  return fallback
}

export async function apiClient<T>(path: string, init: ApiClientOptions = {}): Promise<T> {
  apiRequestState.loading = true
  apiRequestState.lastError = null
  const { query, ...requestInit } = init as ApiClientOptions
  const hasBody = requestInit.body !== undefined && requestInit.body !== null

  try {
    const response = await fetch(resolveUrl(path, query), {
      ...requestInit,
      headers: {
        Accept: 'application/json',
        ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
        ...requestInit.headers,
      },
    })

    const requestId = response.headers.get('X-Request-ID')
    apiRequestState.lastRequestId = requestId

    const text = await response.text()
    const payload = parseResponseBody(text)

    if (!response.ok) {
      const message = getErrorMessage(payload, `请求失败，状态码 ${response.status}`)
      apiRequestState.lastError = message
      throw new ApiError(message, response.status, requestId, payload)
    }

    return payload as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    const message = error instanceof Error ? error.message : '网络请求失败'
    apiRequestState.lastError = message
    throw new ApiError(message, 0, apiRequestState.lastRequestId, null)
  } finally {
    apiRequestState.loading = false
  }
}

function parseResponseBody(text: string) {
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}
