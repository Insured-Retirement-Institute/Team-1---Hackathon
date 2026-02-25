<script setup lang="ts">
defineProps<{
  status: string
}>()

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  ACTIVE: { bg: 'bg-green-100', text: 'text-green-700', label: 'Active' },
  DEATH_CLAIM_PENDING: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Death Claim Pending' },
  TERMINATED: { bg: 'bg-red-100', text: 'text-red-700', label: 'Terminated' },
}

function getConfig(status: string) {
  return statusConfig[status] || { bg: 'bg-gray-100', text: 'text-gray-700', label: status }
}
</script>

<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      getConfig(status).bg,
      getConfig(status).text
    ]"
  >
    {{ getConfig(status).label }}
  </span>
</template>
