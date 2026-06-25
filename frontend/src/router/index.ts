import { createRouter, createWebHistory } from 'vue-router'

import AdminView from '../views/AdminView.vue'
import CompetitorAnalysesView from '../views/CompetitorAnalysesView.vue'
import CopywritingView from '../views/CopywritingView.vue'
import HealthView from '../views/HealthView.vue'
import JobsView from '../views/JobsView.vue'
import RulesView from '../views/RulesView.vue'
import WorkspaceView from '../views/WorkspaceView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workspace' },
    { path: '/workspace', name: 'workspace', component: WorkspaceView },
    { path: '/copywriting', name: 'copywriting', component: CopywritingView },
    { path: '/competitor-analyses', name: 'competitor-analyses', component: CompetitorAnalysesView },
    { path: '/rules', name: 'rules', component: RulesView },
    { path: '/jobs', name: 'jobs', component: JobsView },
    { path: '/admin', name: 'admin', component: AdminView },
    { path: '/health', name: 'health', component: HealthView },
  ],
})
