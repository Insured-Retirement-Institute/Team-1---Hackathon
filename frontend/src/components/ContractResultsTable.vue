<script setup lang="ts">
import { ref, computed } from 'vue'
import { FwbCheckbox, FwbBadge, FwbButton } from 'flowbite-vue'
import SortIcon from '@/icons/SortIcon.svg'
import { ContractStatus, type ContractRecord } from '@/models/ContractRecord'

type SortableColumn = keyof Omit<ContractRecord, 'id'>
type SortDirection = 'asc' | 'desc'

const props = withDefaults(defineProps<{
	records: ContractRecord[]
	showActions?: boolean
}>(), {
	showActions: true
})

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

const sortedRecords = computed(() => {
	if (!sortColumn.value) return props.records

	return [...props.records].sort((a, b) => {
		const aVal = a[sortColumn.value!]
		const bVal = b[sortColumn.value!]
		const comparison = String(aVal).localeCompare(String(bVal))
		return sortDirection.value === 'asc' ? comparison : -comparison
	})
})

const allSelected = computed(() => {
	return props.records.length > 0 && props.records.every(r => r.selected)
})

const someSelected = computed(() => {
	const selectedCount = props.records.filter(r => r.selected).length
	return selectedCount > 0 && selectedCount < props.records.length
})

function toggleSelectAll() {
	const newValue = !allSelected.value
	props.records.forEach(r => r.selected = newValue)
}

function toggleSelect(record: ContractRecord) {
	record.selected = !record.selected
}

function getStatusBadgeType(status: ContractStatus): 'green' | 'yellow' | 'red' {
	if (status === ContractStatus.Active) return 'green'
	if (status === ContractStatus.ActiveRestricted || status === ContractStatus.OwnershipIssue || status === ContractStatus.Unappointed) return 'yellow'
	return 'red'
}
</script>

<template>
	<div class="bg-[#F1F1F1] border border-[#CCCCCC] rounded-xl">
		<p class="justify-center text-gray-900 text-sm font-bold p-4">Contracts</p>

		<div class="relative overflow-x-auto">
			<table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 border-t-gray-300 border-t">
				<thead class="text-xs text-gray-700 uppercase bg-[#F1F1F1] dark:bg-gray-700 dark:text-gray-400">
					<tr class="border-b border-gray-200">
						<th scope="col" class="px-6 py-3">
							<FwbCheckbox
								:model-value="allSelected"
								:indeterminate="someSelected"
								@update:model-value="toggleSelectAll"
							/>
						</th>
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
								Product Name
								<button type="button" @click="toggleSort('productName')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Contract #
								<button type="button" @click="toggleSort('contractNumber')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Ownership
								<button type="button" @click="toggleSort('ownership')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Trailing?
								<button type="button" @click="toggleSort('trailing')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Withdrawal Program
								<button type="button" @click="toggleSort('withdrawalProgram')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th scope="col" class="px-6 py-3">
							<div class="flex items-center">
								Contract Status
								<button type="button" @click="toggleSort('contractStatus')" class="cursor-pointer">
									<SortIcon class="w-3 h-3 ms-1.5" />
								</button>
							</div>
						</th>
						<th v-if="showActions" scope="col" class="px-6 py-3">
							<span class="sr-only">Actions</span>
						</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="(record, index) in sortedRecords"
						:key="record.id"
						:class="[
							'bg-[#F1F1F1]',
							index < sortedRecords.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : ''
						]"
					>
						<td class="px-6 py-4">
							<FwbCheckbox
								:model-value="record.selected"
								@update:model-value="toggleSelect(record)"
							/>
						</td>
						<th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white">
							{{ record.carrierName }}
						</th>
						<td class="px-6 py-4">
							{{ record.productName }}
						</td>
						<td class="px-6 py-4">
							{{ record.contractNumber }}
						</td>
						<td class="px-6 py-4">
							{{ record.ownership }}
						</td>
						<td class="px-6 py-4">
							<span class="flex items-center">
								<span :class="['flex w-3 h-3 me-3 rounded-full', record.trailing ? 'bg-green-500' : 'bg-red-500']"></span>
								{{ record.trailing ? 'Yes' : 'No' }}
							</span>
						</td>
						<td class="px-6 py-4">
							<span class="flex items-center">
								<span :class="['flex w-3 h-3 me-3 rounded-full', record.withdrawalProgram ? 'bg-green-500' : 'bg-red-500']"></span>
								{{ record.withdrawalProgram ? 'Yes' : 'No' }}
							</span>
						</td>
						<td class="px-6 py-4">
							<FwbBadge :type="getStatusBadgeType(record.contractStatus)" class="inline-flex rounded">
								{{ record.contractStatus }}
							</FwbBadge>
						</td>
						<td v-if="showActions" class="px-6 py-4 text-right">
							<FwbButton v-if="record.contractStatus === ContractStatus.Unappointed" color="default" class="cursor-pointer">
								Complete Training
							</FwbButton>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
