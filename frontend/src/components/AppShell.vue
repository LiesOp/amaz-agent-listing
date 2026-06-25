<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">AL</span>
        <div>
          <strong>Listing Agent</strong>
          <span>V1 工作台</span>
        </div>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>

    <div class="app-main">
      <header class="topbar">
        <div>
          <p class="eyebrow">Amazon Listing Agent</p>
          <h1>{{ routeTitle }}</h1>
        </div>
        <RequestStatusBar />
      </header>

      <main class="content">
        <RouterView v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" />
          </KeepAlive>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import RequestStatusBar from './RequestStatusBar.vue'

const navItems = [
  { path: '/copywriting', label: '文案' },
  { path: '/workspace', label: '工作台' },
  { path: '/competitor-analyses', label: '竞品分析' },
  { path: '/rules', label: '规则' },
  { path: '/jobs', label: '任务' },
  { path: '/admin', label: '模型管理' },
  { path: '/health', label: '健康检查' },
]

const route = useRoute()

const routeTitle = computed(() => {
  const current = navItems.find((item) => item.path === route.path)
  return current?.label ?? '工作台'
})
</script>
