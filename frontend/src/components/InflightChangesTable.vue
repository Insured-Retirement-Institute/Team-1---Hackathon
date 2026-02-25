<script setup lang="ts">
import { ref, computed } from 'vue'
import SortIcon from '@/icons/SortIcon.svg'
import type { InflightChange } from '@/models/InflightChange'
import type { Client } from '@/models/Client'
import { FwbDropdown, FwbListGroup, FwbListGroupItem, FwbProgress } from 'flowbite-vue'

type SortableColumn = 'clientName' | keyof InflightChange
type SortDirection = 'asc' | 'desc'

const props = defineProps<{
	changes: InflightChange[]
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

function getClientName(clientId: string): string {
	const client = props.clients.find(c => c.id === clientId)
	return client ? `${client.firstName} ${client.lastName}` : 'Unknown'
}

function getClientEmail(clientId: string): string {
	const client = props.clients.find(c => c.id === clientId)
	return client?.email ?? ''
}

interface ChangeWithClientInfo extends InflightChange {
	clientName: string
	clientEmail: string
}

const changesWithClientName = computed<ChangeWithClientInfo[]>(() => {
	return props.changes.map(change => ({
		...change,
		clientName: getClientName(change.clientId),
		clientEmail: getClientEmail(change.clientId)
	}))
})

const sortedChanges = computed(() => {
	if (!sortColumn.value) return changesWithClientName.value

	return [...changesWithClientName.value].sort((a, b) => {
		const aVal = a[sortColumn.value as keyof ChangeWithClientInfo]
		const bVal = b[sortColumn.value as keyof ChangeWithClientInfo]

		// Handle numeric sorting for completionPercentage
		if (sortColumn.value === 'completionPercentage') {
			const comparison = (aVal as number) - (bVal as number)
			return sortDirection.value === 'asc' ? comparison : -comparison
		}

		// Handle date sorting
		if (sortColumn.value === 'lastUpdatedDate') {
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

function getProgressColor(percentage: number): 'green' | 'yellow' | 'red' {
	if (percentage >= 75) return 'green'
	if (percentage >= 50) return 'yellow'
	return 'red'
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
								Contract Number
								<button type="button" @click="toggleSort('contractNumber')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Completion
								<button type="button" @click="toggleSort('completionPercentage')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Last Updated
								<button type="button" @click="toggleSort('lastUpdatedDate')" class="cursor-pointer">
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
						:key="change.id"
						:class="[
							'bg-[#f8f8f8]',
							index < sortedChanges.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : ''
						]"
					>
						<th scope="row" class="px-6 py-4 whitespace-nowrap dark:text-white">
							<div class="font-bold text-gray-900">{{ change.clientName }}</div>
							<div class="font-normal text-gray-500">{{ change.clientEmail }}</div>
						</th>
						<td class="px-6 py-4">
							{{ change.contractNumber }}
						</td>
						<td class="px-6 py-4">
							<div class="flex items-center gap-2">
								<FwbProgress
									:progress="change.completionPercentage"
									:color="getProgressColor(change.completionPercentage)"
									size="sm"
									class="w-24"
								/>
								<span class="text-xs">{{ change.completionPercentage }}%</span>
							</div>
						</td>
						<td class="px-6 py-4">
							{{ formatDate(change.lastUpdatedDate) }}
						</td>
						<td class="px-6 py-4">
							<FwbDropdown text="Actions" color="light">
								<FwbListGroup>
									<FwbListGroupItem>View Details</FwbListGroupItem>
									<FwbListGroupItem>Resume</FwbListGroupItem>
									<FwbListGroupItem>Cancel</FwbListGroupItem>
								</FwbListGroup>
							</FwbDropdown>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
