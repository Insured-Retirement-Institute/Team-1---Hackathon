<script setup lang="ts">
import type { BdChangeRequest } from '@/types/carrier'
import StatusBadge from './StatusBadge.vue'

defineProps<{
  policy: BdChangeRequest
}>()

function formatDateTime(dateString: string) {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatAccountType(accountType: string) {
  const labels: Record<string, string> = {
    individual: 'Individual',
    joint: 'Joint',
    trust: 'Trust',
    custodial: 'Custodial',
    entity: 'Entity'
  }
  return labels[accountType] || accountType
}

function formatPlanType(planType: string) {
  const labels: Record<string, string> = {
    nonQualified: 'Non-Qualified',
    rothIra: 'Roth IRA',
    traditionalIra: 'Traditional IRA',
    sep: 'SEP',
    simple: 'SIMPLE'
  }
  return labels[planType] || planType
}

function formatOwnership(ownership: string) {
  const labels: Record<string, string> = {
    single: 'Single',
    joint: 'Joint',
    trust: 'Trust',
    corporate: 'Corporate'
  }
  return labels[ownership] || ownership
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="bg-white shadow-sm rounded-lg p-6">
      <div class="flex items-start justify-between">
        <div>
          <h2 class="text-2xl font-bold text-gray-900">{{ policy.policyNumber }}</h2>
          <p class="mt-1 text-sm text-gray-500">
            Transaction ID: {{ policy.requestId }}
          </p>
        </div>
        <StatusBadge :status="policy.currentStatus" />
      </div>
      <div class="mt-4 grid grid-cols-3 gap-4">
        <div>
          <p class="text-xs font-medium text-gray-500">Created</p>
          <p class="text-sm text-gray-900">{{ formatDateTime(policy.createdAt) }}</p>
        </div>
        <div>
          <p class="text-xs font-medium text-gray-500">Last Updated</p>
          <p class="text-sm text-gray-900">{{ formatDateTime(policy.updatedAt) }}</p>
        </div>
        <div>
          <p class="text-xs font-medium text-gray-500">Carrier</p>
          <p class="text-sm text-gray-900">{{ policy.carrierName }}</p>
        </div>
      </div>
    </div>

    <!-- Client Information -->
    <div class="bg-white shadow-sm rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Client Information</h3>
      </div>
      <div class="px-4 py-4">
        <div class="grid grid-cols-2 gap-x-8 gap-y-3">
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Client Name</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ policy.clientName }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">SSN (Last 4)</dt>
            <dd class="mt-1 text-sm text-gray-900">***-**-{{ policy.ssnLast4 }}</dd>
          </div>
        </div>
      </div>
    </div>

    <!-- Servicing Agent -->
    <div class="bg-white shadow-sm rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Servicing Agent</h3>
      </div>
      <div class="px-4 py-4">
        <div class="grid grid-cols-2 gap-x-8 gap-y-3">
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Agent Name</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ policy.servicingAgent?.agentName || 'N/A' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">NPN</dt>
            <dd class="mt-1 text-sm text-gray-900 font-mono">{{ policy.servicingAgent?.npn || 'N/A' }}</dd>
          </div>
        </div>
      </div>
    </div>

    <!-- Policy Details -->
    <div class="bg-white shadow-sm rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Policy Details</h3>
      </div>
      <div class="px-4 py-4">
        <div class="grid grid-cols-2 gap-x-8 gap-y-3">
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Product</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ policy.productName }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">CUSIP</dt>
            <dd class="mt-1 text-sm text-gray-900 font-mono">{{ policy.cusip }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Account Type</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ formatAccountType(policy.accountType) }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Plan Type</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ formatPlanType(policy.planType) }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Ownership</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ formatOwnership(policy.ownership) }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Contract Status</dt>
            <dd class="mt-1">
              <span
                :class="[
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                  policy.contractStatus === 'active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                ]"
              >
                {{ policy.contractStatus.charAt(0).toUpperCase() + policy.contractStatus.slice(1) }}
              </span>
            </dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Trailing Commission</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ policy.trailingCommission ? 'Yes' : 'No' }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium text-gray-500 uppercase">Systematic Withdrawal</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ policy.withdrawalStructure.systematicInPlace ? 'In Place' : 'None' }}</dd>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
