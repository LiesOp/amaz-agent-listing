<template>
  <section class="request-status" aria-label="请求状态">
    <span :class="['status-dot', requestStatus.loading ? 'is-loading' : '']" />
    <span>{{ requestStatus.loading ? '请求中' : '空闲' }}</span>
    <span v-if="requestStatus.lastRequestId" class="request-id">请求 ID：{{ requestStatus.lastRequestId }}</span>
    <span v-if="requestStatus.lastError" class="request-error">{{ requestStatus.lastError }}</span>
  </section>
</template>

<script setup lang="ts">
import { useRequestStatusStore } from '../stores/requestStatus'

const requestStatus = useRequestStatusStore()
</script>
