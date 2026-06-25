import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getJob } from '../api/jobs'
import type { JobResponse } from '../api/types'

const RECENT_JOB_LIMIT = 10

export const useTasksStore = defineStore('tasks', () => {
  const recentJobIds = ref<string[]>([])
  const jobsById = ref<Record<string, JobResponse>>({})
  const loadingJobIds = ref<string[]>([])
  const pollingJobIds = ref<string[]>([])
  const pollTimers = new Map<string, number>()
  const completionHandlers = new Map<string, (job: JobResponse) => void | Promise<void>>()

  const recentJobs = computed(() => {
    return recentJobIds.value
      .map((id) => jobsById.value[id])
      .filter((job): job is JobResponse => Boolean(job))
  })

  function persistRecentJobs() {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem('listing-agent:recent-job-ids', JSON.stringify(recentJobIds.value))
  }

  function pruneJobsCache() {
    const retainedIds = new Set(recentJobIds.value)
    jobsById.value = Object.fromEntries(
      Object.entries(jobsById.value).filter(([jobId]) => retainedIds.has(jobId)),
    )
  }

  function restoreRecentJobs() {
    if (typeof window === 'undefined') {
      return
    }
    const raw = window.localStorage.getItem('listing-agent:recent-job-ids')
    if (!raw) {
      return
    }
    try {
      const ids = JSON.parse(raw)
      if (Array.isArray(ids)) {
        recentJobIds.value = ids
          .filter((id): id is string => typeof id === 'string')
          .slice(0, RECENT_JOB_LIMIT)
        pruneJobsCache()
      }
    } catch {
      recentJobIds.value = []
      pruneJobsCache()
    }
  }

  function addJob(jobId: string) {
    recentJobIds.value = [jobId, ...recentJobIds.value.filter((id) => id !== jobId)].slice(
      0,
      RECENT_JOB_LIMIT,
    )
    pruneJobsCache()
    persistRecentJobs()
  }

  async function fetchJob(jobId: string) {
    if (!jobId) {
      return null
    }

    loadingJobIds.value = [...new Set([...loadingJobIds.value, jobId])]
    try {
      const job = await getJob(jobId)
      jobsById.value[job.id] = job
      addJob(job.id)
      if (['completed', 'failed'].includes(job.status)) {
        stopPollingJob(job.id)
        const handler = completionHandlers.get(job.id)
        completionHandlers.delete(job.id)
        if (handler) {
          void handler(job)
        }
      }
      return job
    } finally {
      loadingJobIds.value = loadingJobIds.value.filter((id) => id !== jobId)
    }
  }

  function pollJob(jobId: string, intervalMs = 3000) {
    if (!jobId || pollTimers.has(jobId) || typeof window === 'undefined') {
      return
    }

    pollingJobIds.value = [...new Set([...pollingJobIds.value, jobId])]
    void fetchJob(jobId)
    const timerId = window.setInterval(() => {
      void fetchJob(jobId)
    }, intervalMs)
    pollTimers.set(jobId, timerId)
  }

  function onJobCompleted(jobId: string, handler: (job: JobResponse) => void | Promise<void>) {
    completionHandlers.set(jobId, handler)
  }

  function stopPollingJob(jobId: string) {
    const timerId = pollTimers.get(jobId)
    if (timerId !== undefined) {
      window.clearInterval(timerId)
      pollTimers.delete(jobId)
    }
    pollingJobIds.value = pollingJobIds.value.filter((id) => id !== jobId)
  }

  function stopAllPolling() {
    pollingJobIds.value.forEach((jobId) => stopPollingJob(jobId))
  }

  function clearCompletedJobs() {
    recentJobIds.value = recentJobIds.value.filter((id) => {
      const status = jobsById.value[id]?.status
      return status !== 'completed' && status !== 'failed'
    })
    pruneJobsCache()
    persistRecentJobs()
  }

  restoreRecentJobs()

  return {
    recentJobIds,
    recentJobs,
    jobsById,
    loadingJobIds,
    pollingJobIds,
    addJob,
    fetchJob,
    pollJob,
    onJobCompleted,
    stopPollingJob,
    stopAllPolling,
    clearCompletedJobs,
  }
})
