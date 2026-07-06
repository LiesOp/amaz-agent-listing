<template>
  <section class="workspace-page">
    <div class="workspace-left">
      <StepNav />
      <ConversationPanel />
      <BriefForm />
      <CompetitorImportPanel />
      <CompetitorAnalysisPanel />
    </div>

    <div class="workspace-right">
      <DraftGeneratorPanel />
      <DraftResultPanel />
      <AuditResultPanel />
      <RewritePanel />
    </div>

    <div v-if="workflow.lastError" class="workspace-error alert alert-error">
      {{ workflow.lastError }}
    </div>
    <div v-else-if="workflow.lastSuccess" class="workspace-error alert alert-success">
      {{ workflow.lastSuccess }}
    </div>
  </section>
</template>

<script setup lang="ts">
import AuditResultPanel from '../components/AuditResultPanel.vue'
import BriefForm from '../components/BriefForm.vue'
import CompetitorAnalysisPanel from '../components/CompetitorAnalysisPanel.vue'
import CompetitorImportPanel from '../components/CompetitorImportPanel.vue'
import ConversationPanel from '../components/ConversationPanel.vue'
import DraftGeneratorPanel from '../components/DraftGeneratorPanel.vue'
import DraftResultPanel from '../components/DraftResultPanel.vue'
import RewritePanel from '../components/RewritePanel.vue'
import StepNav from '../components/StepNav.vue'
import { useWorkflowStore } from '../stores/workflow'

const workflow = useWorkflowStore()
</script>
