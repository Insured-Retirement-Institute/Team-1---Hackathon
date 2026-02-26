<script setup lang="ts">
import { ref, computed } from 'vue'
import SortIcon from '@/icons/SortIcon.svg'
import type { Transaction } from '@/models/Transaction'
import type { Client } from '@/models/Client'
import { FwbBadge, FwbButton, FwbDropdown, FwbListGroup, FwbListGroupItem } from 'flowbite-vue'

type BadgeType = 'default' | 'dark' | 'red' | 'green' | 'yellow' | 'indigo' | 'purple' | 'pink'
type SortableColumn = keyof Transaction
type SortDirection = 'asc' | 'desc'

const props = defineProps<{
	changes: Transaction[]
	clients: Client[]
}>()

const sortColumn = ref<SortableColumn | null>(null)
const sortDirection = ref<SortDirection>('asc')

function toggleSort(column: SortableColumn) {
	if (sortColumn.value === column) {
		sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumn.value = column
		sortDirection.value = 'asc'
	}
}

function getClientSsnLast4(clientId: string): string {
	const client = props.clients.find(c => c.clientId === clientId)
	return client?.ssnLast4 ?? ''
}

const sortedChanges = computed(() => {
	if (!sortColumn.value) return props.changes

	return [...props.changes].sort((a, b) => {
		const aVal = a[sortColumn.value!]
		const bVal = b[sortColumn.value!]

		// Handle date sorting
		if (sortColumn.value === 'updatedAt' || sortColumn.value === 'createdAt') {
			const comparison = new Date(aVal as string).getTime() - new Date(bVal as string).getTime()
			return sortDirection.value === 'asc' ? comparison : -comparison
		}

		const comparison = String(aVal).localeCompare(String(bVal))
		return sortDirection.value === 'asc' ? comparison : -comparison
	})
})

function formatDate(dateString: string): string {
	return new Date(dateString).toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	})
}

const statusColors: Record<string, BadgeType> = {
	'PENDING': 'yellow',
	'CARRIER_APPROVED': 'green',
	'CARRIER_REJECTED': 'red',
	'COMPLETED': 'green',
	'CANCELLED': 'dark'
}

function getStatusColor(status: string): BadgeType {
	return statusColors[status] ?? 'default'
}
</script>

<template>
	<div class="bg-[#f8f8f8] rounded-xl">
		<p class="justify-center text-gray-900 text-xl font-bold p-4">Inflight Changes</p>

		<div class="relative overflow-x-auto rounded-xl">
			<table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 border-t-gray-300 border-t">
				<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
					<tr>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Client Name
								<button type="button" @click="toggleSort('clientName')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Contracts
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Status
								<button type="button" @click="toggleSort('status')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Last Updated
								<button type="button" @click="toggleSort('updatedAt')" class="cursor-pointer">
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
						v-for="(change, index) in sortedChanges"
						:key="change.requestId"
						:class="[
							'bg-[#f8f8f8]',
							index < sortedChanges.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : ''
						]"
					>
						<th scope="row" class="px-6 py-4 whitespace-nowrap dark:text-white">
							<div class="font-bold text-gray-900">{{ change.clientName }}</div>
							<div class="font-normal text-gray-500">SSN: ***-**-{{ getClientSsnLast4(change.clientId) }}</div>
						</th>
						<td class="px-6 py-4">
							<div v-for="contract in change.contracts" :key="contract">
								{{ contract }}
							</div>
						</td>
						<td class="px-6 py-4">
							<!-- <FwbBadge :type="getStatusColor(change.status)">{{ change.status }}</FwbBadge> -->
						</td>
						<td class="px-6 py-4">
							{{ formatDate(change.updatedAt) }}
						</td>
						<td class="px-6 py-4">
							<RouterLink to="/carrier-results">
								<FwbButton class="cursor-pointer">Open Transfer</FwbButton>
							</RouterLink>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
