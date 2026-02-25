<script setup lang="ts">
import { ref, computed } from 'vue'
import SortIcon from '@/icons/SortIcon.svg'
import CirclePlusIcon from '@/icons/CirclePlusIcon.svg'
import type { Client } from '@/models/Client'
import { FwbButton, FwbDropdown, FwbInput, FwbListGroup, FwbListGroupItem } from 'flowbite-vue'

type SortableColumn = keyof Client
type SortDirection = 'asc' | 'desc'

const props = defineProps<{
	clients: Client[]
}>()

const sortColumn = ref<SortableColumn | null>(null)
const sortDirection = ref<SortDirection>('asc')
const searchQuery = ref('')

function toggleSort(column: SortableColumn) {
	if (sortColumn.value === column) {
		sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumn.value = column
		sortDirection.value = 'asc'
	}
}

const filteredClients = computed(() => {
	const query = searchQuery.value.toLowerCase().trim()
	if (!query) return props.clients

	return props.clients.filter(client => {
		const fullName = `${client.firstName} ${client.lastName}`.toLowerCase()
		return fullName.includes(query) ||
			client.email.toLowerCase().includes(query) ||
			client.accountNumber.toLowerCase().includes(query)
	})
})

const sortedClients = computed(() => {
	if (!sortColumn.value) return filteredClients.value

	return [...filteredClients.value].sort((a, b) => {
		const aVal = a[sortColumn.value!]
		const bVal = b[sortColumn.value!]

		// Handle numeric sorting for numberOfContracts
		if (sortColumn.value === 'numberOfContracts') {
			const comparison = (aVal as number) - (bVal as number)
			return sortDirection.value === 'asc' ? comparison : -comparison
		}

		// Handle date sorting
		if (sortColumn.value === 'updatedDate') {
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
</script>

<template>
	<div class="bg-[#f8f8f8] rounded-xl">
		<p class="justify-center text-gray-900 text-xl font-bold p-4">My Book of Business</p>

		<div class="flex items-center justify-between p-4">
			<div class="w-1/3">
				<FwbInput v-model="searchQuery" placeholder="Search for client" />
			</div>

			<div class="flex items-center gap-2">
				<FwbButton color="default">
					<div class="flex items-center gap-2">
						<CirclePlusIcon />
						Add Client
					</div>
				</FwbButton>

				<FwbDropdown text="Filters" color="light">Filters</FwbDropdown>
				<FwbDropdown text="Actions" color="light">Actions</FwbDropdown>
			</div>
		</div>

		<div class="relative overflow-x-auto rounded-xl">
			<table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 border-t-gray-300 border-t rounded-xl">
				<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
					<tr>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Name
								<button type="button" @click="toggleSort('lastName')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Account Number
								<button type="button" @click="toggleSort('accountNumber')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								# of Contracts
								<button type="button" @click="toggleSort('numberOfContracts')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Last Updated
								<button type="button" @click="toggleSort('updatedDate')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<span >Actions</span>
						</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="(client, index) in sortedClients"
						:key="client.id"
						:class="[
							'bg-[#f8f8f8]',
							index < sortedClients.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : ''
						]"
					>
						<th scope="row" class="px-6 py-4 whitespace-nowrap dark:text-white">
							<div class="font-bold text-gray-900">{{ client.firstName }} {{ client.lastName }}</div>
							<div class="font-normal text-gray-500">{{ client.email }}</div>
						</th>
						<td class="px-6 py-4">
							{{ client.accountNumber }}
						</td>
						<td class="px-6 py-4">
							{{ client.numberOfContracts }}
						</td>
						<td class="px-6 py-4">
							{{ formatDate(client.updatedDate) }}
						</td>
						<td class="px-6 py-4">
							<FwbDropdown text="Actions" color="light">
								<FwbListGroup>
									<FwbListGroupItem>View Details</FwbListGroupItem>
									<FwbListGroupItem>Edit</FwbListGroupItem>
									<FwbListGroupItem>Delete</FwbListGroupItem>
								</FwbListGroup>
							</FwbDropdown>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
