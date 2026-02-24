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
            Transaction ID: {{ policy.transactionId }}
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

    <!-- Errors -->
    <div v-if="policy.errors && policy.errors.length > 0" class="bg-red-50 border border-red-200 rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-red-200 bg-red-100">
        <h3 class="text-sm font-semibold text-red-800 uppercase tracking-wider">Policy Errors</h3>
      </div>
      <div class="px-4 py-4 space-y-2">
        <div v-for="(error, idx) in policy.errors" :key="idx" class="flex items-start gap-2">
          <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          <div>
            <p class="text-sm font-medium text-red-800">{{ error.errorCode }}</p>
            <p class="text-sm text-red-700">{{ error.message }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Validation Details -->
    <div v-if="policy.carrierValidationDetails" class="bg-white shadow-sm rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Carrier Validation</h3>
      </div>
      <div class="px-4 py-4 space-y-4">
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium text-gray-700">Result:</span>
          <span
            :class="[
              'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium',
              policy.carrierValidationDetails.validationResult === 'approved'
                ? 'bg-green-100 text-green-800'
                : 'bg-red-100 text-red-800'
            ]"
          >
            {{ policy.carrierValidationDetails.validationResult.toUpperCase() }}
          </span>
          <span v-if="policy.carrierValidationDetails.validatedAt" class="text-xs text-gray-500">
            {{ formatDateTime(policy.carrierValidationDetails.validatedAt) }}
          </span>
        </div>

        <div v-if="policy.carrierValidationDetails.rejectionReason" class="bg-red-50 border border-red-200 rounded-lg p-3">
          <p class="text-sm text-red-700">
            <span class="font-medium">Rejection Reason:</span>
            {{ policy.carrierValidationDetails.rejectionReason }}
          </p>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
            <span class="text-sm text-gray-700">Licensing</span>
            <span :class="policy.carrierValidationDetails.licensingCheck === 'passed' ? 'text-green-500' : 'text-red-500'">
              <svg v-if="policy.carrierValidationDetails.licensingCheck === 'passed'" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </span>
          </div>
          <div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
            <span class="text-sm text-gray-700">Appointment</span>
            <span :class="policy.carrierValidationDetails.appointmentCheck === 'passed' ? 'text-green-500' : 'text-red-500'">
              <svg v-if="policy.carrierValidationDetails.appointmentCheck === 'passed'" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </span>
          </div>
          <div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
            <span class="text-sm text-gray-700">Suitability</span>
            <span :class="policy.carrierValidationDetails.suitabilityCheck === 'passed' ? 'text-green-500' : 'text-red-500'">
              <svg v-if="policy.carrierValidationDetails.suitabilityCheck === 'passed'" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </span>
          </div>
          <div class="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
            <span class="text-sm text-gray-700">Policy Rules</span>
            <span :class="policy.carrierValidationDetails.policyRulesCheck === 'passed' ? 'text-green-500' : 'text-red-500'">
              <svg v-if="policy.carrierValidationDetails.policyRulesCheck === 'passed'" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Status History -->
    <div class="bg-white shadow-sm rounded-lg overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wider">Status History</h3>
      </div>
      <div class="px-4 py-4">
        <ul class="-mb-8">
          <li v-for="(item, idx) in policy.statusHistory" :key="idx" class="relative pb-8">
            <span
              v-if="idx !== policy.statusHistory.length - 1"
              class="absolute left-4 top-4 -ml-px h-full w-0.5 bg-gray-200"
            />
            <div class="relative flex space-x-3">
              <div>
                <span
                  :class="[
                    'h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white',
                    item.status === 'COMPLETE' ? 'bg-green-500' :
                    item.status === 'CARRIER_REJECTED' ? 'bg-red-500' :
                    item.status === 'CARRIER_APPROVED' ? 'bg-green-400' :
                    'bg-blue-500'
                  ]"
                >
                  <svg class="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path v-if="item.status === 'COMPLETE' || item.status === 'CARRIER_APPROVED'" fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    <path v-else-if="item.status === 'CARRIER_REJECTED'" fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    <path v-else fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
                  </svg>
                </span>
              </div>
              <div class="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                <div>
                  <p class="text-sm text-gray-900 font-medium">
                    {{ item.status.replace(/_/g, ' ') }}
                  </p>
                  <p v-if="item.notes" class="mt-0.5 text-xs text-gray-500">{{ item.notes }}</p>
                </div>
                <div class="whitespace-nowrap text-right text-xs text-gray-500">
                  {{ formatDateTime(item.timestamp) }}
                </div>
              </div>
            </div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
