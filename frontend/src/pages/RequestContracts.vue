<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useInflightChangesStore } from '@/stores/useInflightChangesStore'
import { distributorApi } from '@/api/Api'
import { FwbButton, FwbBadge } from 'flowbite-vue'
import type { Contract } from '@/models/Contract'
import SortIcon from '@/icons/SortIcon.svg'

const props = defineProps<{
	requestId: string
}>()

const inflightChangesStore = useInflightChangesStore()
const contracts = ref<Contract[]>([])
const isLoading = ref(false)

type SortableColumn = keyof Contract
type SortDirection = 'asc' | 'desc'

const sortColumn = ref<SortableColumn | null>(null)
const sortDirection = ref<SortDirection>('asc')

const transaction = computed(() => {
	return inflightChangesStore.inflightChanges.find(t => t.requestId === props.requestId)
})

const filteredContracts = computed(() => {
	if (!transaction.value) return []
	const transactionContracts = new Set(transaction.value.contracts)
	return contracts.value.filter(c => transactionContracts.has(c.policyNumber))
})

const sortedContracts = computed(() => {
	if (!sortColumn.value) return filteredContracts.value

	return [...filteredContracts.value].sort((a, b) => {
		const aVal = a[sortColumn.value!]
		const bVal = b[sortColumn.value!]
		const comparison = String(aVal).localeCompare(String(bVal))
		return sortDirection.value === 'asc' ? comparison : -comparison
	})
})

function toggleSort(column: SortableColumn) {
	if (sortColumn.value === column) {
		sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumn.value = column
		sortDirection.value = 'asc'
	}
}

function getStatusColor(status: string): 'green' | 'yellow' | 'red' | 'default' {
	switch (status.toLowerCase()) {
		case 'active': return 'green'
		case 'pending': return 'yellow'
		case 'inactive': return 'red'
		default: return 'default'
	}
}

onMounted(async () => {
	if (!inflightChangesStore.inflightChanges.length) {
		await inflightChangesStore.loadInflightChanges()
	}

	if (transaction.value?.clientId) {
		isLoading.value = true
		try {
			const result = await distributorApi.getClientContracts(transaction.value.clientId)
			contracts.value = result.contracts
		} catch (error) {
			console.error('Failed to load contracts:', error)
		} finally {
			isLoading.value = false
		}
	}
})
</script>

<template>
	<div class="w-full">
		<div class="bg-[#F1F1F1] border border-[#CCCCCC] rounded-xl">
			<div class="p-4">
				<h1 class="text-xl font-bold text-gray-900">Request Contracts</h1>
				<p v-if="transaction" class="text-sm text-gray-500">
					Client: {{ transaction.clientName }} | Request: {{ requestId }}
				</p>
			</div>

			<div v-if="isLoading" class="p-8 text-center text-gray-500">
				Loading contracts...
			</div>

			<div v-else class="relative overflow-x-auto rounded-xl">
				<table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 border-t-gray-300 border-t">
					<thead class="text-xs text-gray-700 uppercase bg-[#F1F1F1] dark:bg-gray-700 dark:text-gray-400">
						<tr class="border-b border-gray-200">
							<th scope="col" class="px-6 py-3">
								<div class="flex items-center">
									Carrier Name
									<button type="button" @click="toggleSort('carrierName')" class="cursor-pointer">
										<SortIcon class="w-3 h-3 ms-1.5" />
									</button>
								</div>
							</th>
							<th scope="col" class="px-6 py-3">
								<div class="flex items-center">
									Contract #
									<button type="button" @click="toggleSort('policyNumber')" class="cursor-pointer">
										<SortIcon class="w-3 h-3 ms-1.5" />
									</button>
								</div>
							</th>
							<th scope="col" class="px-6 py-3">
								<div class="flex items-center">
									Ownership
									<button type="button" @click="toggleSort('planType')" class="cursor-pointer">
										<SortIcon class="w-3 h-3 ms-1.5" />
									</button>
								</div>
							</th>
							<th scope="col" class="px-6 py-3">
								<div class="flex items-center">
									Contract Status
									<button type="button" @click="toggleSort('status')" class="cursor-pointer">
										<SortIcon class="w-3 h-3 ms-1.5" />
									</button>
								</div>
							</th>
							<th scope="col" class="px-6 py-3">
								<span>Actions</span>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="(contract, index) in sortedContracts"
							:key="contract.policyNumber"
							:class="[
								'bg-[#F1F1F1]',
								index < sortedContracts.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : ''
							]"
						>
							<td class="px-6 py-4 font-medium text-gray-900">
								{{ contract.carrierName }}
							</td>
							<td class="px-6 py-4">
								{{ contract.policyNumber }}
							</td>
							<td class="px-6 py-4">
								{{ contract.planType }}
							</td>
							<td class="px-6 py-4">
								<FwbBadge :type="getStatusColor(contract.status)">{{ contract.status }}</FwbBadge>
							</td>
							<td class="px-6 py-4">
								<FwbButton size="sm" class="cursor-pointer">View Details</FwbButton>
							</td>
						</tr>
						<tr v-if="sortedContracts.length === 0">
							<td colspan="5" class="px-6 py-8 text-center text-gray-500">
								No contracts found for this request.
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>
