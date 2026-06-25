import { defineStore } from 'pinia'
import { computed } from 'vue'

import { apiRequestState } from '../api/client'

export const useRequestStatusStore = defineStore('requestStatus', () => {
  const loading = computed(() => apiRequestState.loading)
  const lastRequestId = computed(() => apiRequestState.lastRequestId)
  const lastError = computed(() => apiRequestState.lastError)

  return {
    loading,
    lastRequestId,
    lastError,
  }
})
