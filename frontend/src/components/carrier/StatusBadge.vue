<script setup lang="ts">
defineProps<{
  status: string
}>()

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  MANIFEST_REQUESTED: { bg: 'bg-gray-100', text: 'text-gray-700', label: 'Manifest Requested' },
  MANIFEST_RECEIVED: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Manifest Received' },
  DUE_DILIGENCE_COMPLETE: { bg: 'bg-indigo-100', text: 'text-indigo-700', label: 'Due Diligence Complete' },
  CARRIER_VALIDATION_PENDING: { bg: 'bg-yellow-100', text: 'text-yellow-700', label: 'Validation Pending' },
  CARRIER_APPROVED: { bg: 'bg-green-100', text: 'text-green-700', label: 'Approved' },
  CARRIER_REJECTED: { bg: 'bg-red-100', text: 'text-red-700', label: 'Rejected' },
  TRANSFER_INITIATED: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Transfer Initiated' },
  TRANSFER_PROCESSING: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Processing' },
  TRANSFER_CONFIRMED: { bg: 'bg-teal-100', text: 'text-teal-700', label: 'Confirmed' },
  COMPLETE: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Complete' },
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
