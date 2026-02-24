<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FwbHeading, FwbSpinner, FwbTabs, FwbTab } from 'flowbite-vue'
import type { BdChangeRequest, CarrierTable } from '@/types/carrier'
import { fetchCarrierRequests } from '@/api/carrierApi'
import PolicyList from '@/components/carrier/PolicyList.vue'
import PolicyDetail from '@/components/carrier/PolicyDetail.vue'

const route = useRoute()

const activeTab = ref<CarrierTable>('carrier')
const policies = ref<BdChangeRequest[]>([])
const selectedPolicy = ref<BdChangeRequest | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function loadPolicies() {
  try {
    loading.value = true
    error.value = null
    selectedPolicy.value = null
    policies.value = await fetchCarrierRequests(activeTab.value)
  } catch (e) {
    error.value = 'Failed to load BD change requests. Please try again.'
    console.error('Error loading policies:', e)
  } finally {
    loading.value = false
  }
}

function handleSelectPolicy(policy: BdChangeRequest) {
  selectedPolicy.value = policy
}

function handleTabChange(tab: string) {
  activeTab.value = tab as CarrierTable
}

watch(activeTab, () => {
  loadPolicies()
})

onMounted(() => {
  // Check if route has a carrier param
  if (route.params.carrier) {
    activeTab.value = route.params.carrier as CarrierTable
  }
  loadPolicies()
})
</script>

<template>
  <div class="w-full">
    <!-- Header -->
    <div class="mb-6">
      <FwbHeading tag="h1" class="text-center mb-2">Carrier Admin System</FwbHeading>
      <p class="text-center text-gray-500 text-sm">BD Change Management Portal</p>
    </div>

    <!-- Carrier Tabs -->
    <div class="mb-6">
      <FwbTabs variant="underline" class="justify-center">
        <FwbTab
          name="carrier"
          title="Athene Annuity"
          :active="activeTab === 'carrier'"
          @click="handleTabChange('carrier')"
        />
        <FwbTab
          name="carrier-2"
          title="Nationwide Insurance"
          :active="activeTab === 'carrier-2'"
          @click="handleTabChange('carrier-2')"
        />
      </FwbTabs>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center h-64">
      <div class="text-center">
        <FwbSpinner size="10" />
        <p class="mt-4 text-gray-500">Loading BD change requests...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <svg class="h-12 w-12 text-red-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <p class="text-red-700">{{ error }}</p>
      <button
        @click="loadPolicies"
        class="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
      >
        Retry
      </button>
    </div>

    <!-- Main Content -->
    <div v-else class="grid grid-cols-12 gap-6">
      <!-- Left Panel - Policy List -->
      <div class="col-span-12 lg:col-span-4">
        <PolicyList
          :policies="policies"
          :selected-id="selectedPolicy?.transactionId"
          @select="handleSelectPolicy"
        />
      </div>

      <!-- Right Panel - Policy Detail -->
      <div class="col-span-12 lg:col-span-8">
        <PolicyDetail v-if="selectedPolicy" :policy="selectedPolicy" />
        <div v-else class="bg-white shadow-sm rounded-lg p-12 text-center">
          <svg class="h-16 w-16 text-gray-300 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 class="text-lg font-medium text-gray-900 mb-2">No Policy Selected</h3>
          <p class="text-gray-500">
            Select a BD change request from the list to view its details.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
