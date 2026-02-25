<script setup lang="ts" generic="T extends { id: string | number }">
import { ref, computed } from 'vue'
import SortIcon from '@/icons/SortIcon.svg'
import CirclePlusIcon from '@/icons/CirclePlusIcon.svg'
import { FwbButton } from 'flowbite-vue'

export interface Column<T> {
	key: keyof T
	label: string
	sortable?: boolean
	formatter?: (value: T[keyof T], record: T) => string
}

const props = defineProps<{
	records: T[]
	columns: Column<T>[]
	title?: string
	createRecord: () => T
}>()

const emit = defineEmits<{
	save: [record: T]
	delete: [record: T]
	update: [records: T[]]
}>()

type SortDirection = 'asc' | 'desc'

const sortColumnKey = ref<string | null>(null)
const sortDirection = ref<SortDirection>('asc')
const editingRecord = ref<T | null>(null)
const isNewRecord = ref(false)

function toggleSort(column: keyof T) {
	if (sortColumnKey.value === column) {
		sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumnKey.value = column as string
		sortDirection.value = 'asc'
	}
}

const sortedRecords = computed(() => {
	const col = sortColumnKey.value as keyof T | null
	if (!col) return props.records

	return [...props.records].sort((a, b) => {
		const aVal = a[col]
		const bVal = b[col]

		if (typeof aVal === 'number' && typeof bVal === 'number') {
			const comparison = aVal - bVal
			return sortDirection.value === 'asc' ? comparison : -comparison
		}

		const comparison = String(aVal).localeCompare(String(bVal))
		return sortDirection.value === 'asc' ? comparison : -comparison
	})
})

const editingId = computed(() => editingRecord.value?.id ?? null)

function getCellValue(record: T, column: Column<T>): string {
	const value = record[column.key]
	if (column.formatter) {
		return column.formatter(value, record)
	}
	return String(value ?? '')
}

function startEdit(record: T) {
	editingRecord.value = { ...record }
	isNewRecord.value = false
}

function startAdd() {
	editingRecord.value = props.createRecord()
	isNewRecord.value = true
}

function cancelEdit() {
	editingRecord.value = null
	isNewRecord.value = false
}

function saveRecord() {
	if (!editingRecord.value) return

	if (isNewRecord.value) {
		const newRecords = [...props.records, editingRecord.value]
		emit('update', newRecords)
	} else {
		const newRecords = props.records.map(r =>
			r.id === editingRecord.value!.id ? editingRecord.value! : r
		)
		emit('update', newRecords)
	}

	emit('save', editingRecord.value)
	editingRecord.value = null
	isNewRecord.value = false
}

function deleteRecord(record: T) {
	const newRecords = props.records.filter(r => r.id !== record.id)
	emit('update', newRecords)
	emit('delete', record)

	if (editingId.value === record.id) {
		editingRecord.value = null
		isNewRecord.value = false
	}
}
</script>

<template>
	<div class="bg-[#f8f8f8] rounded-xl">
		<div class="flex items-center justify-between p-4">
			<p v-if="title" class="text-gray-900 text-xl font-bold">{{ title }}</p>
			<div v-else></div>

			<FwbButton color="default" class="cursor-pointer" @click="startAdd">
				<div class="flex items-center gap-2">
					<CirclePlusIcon />
					Add Entry
				</div>
			</FwbButton>
		</div>

		<!-- Edit Form -->
		<div v-if="editingRecord" class="p-4 mx-4 mb-4 bg-white rounded-lg border border-gray-200">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-semibold text-gray-900">
					{{ isNewRecord ? 'Add New Entry' : 'Edit Entry' }}
				</h3>
				<div class="flex items-center gap-2">
					<FwbButton color="light" size="sm" class="cursor-pointer" @click="cancelEdit">
						Cancel
					</FwbButton>
					<FwbButton color="default" size="sm" class="cursor-pointer" @click="saveRecord">
						Save
					</FwbButton>
				</div>
			</div>

			<slot name="edit-form" :record="editingRecord" :is-new="isNewRecord" />
		</div>

		<div class="relative overflow-x-auto rounded-xl">
			<table class="w-full text-sm text-left rtl:text-right text-gray-500 dark:text-gray-400 border-t-gray-300 border-t">
				<thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
					<tr>
						<th
							v-for="column in columns"
							:key="String(column.key)"
							scope="col"
							class="px-6 py-3"
						>
							<div class="flex items-center">
								{{ column.label }}
								<button
									v-if="column.sortable !== false"
									type="button"
									@click="toggleSort(column.key)"
									class="cursor-pointer"
								>
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
						v-for="(record, index) in sortedRecords"
						:key="record.id"
						:class="[
							'bg-[#f8f8f8]',
							index < sortedRecords.length - 1 ? 'border-b dark:border-gray-700 border-gray-200' : '',
							editingId === record.id ? 'bg-blue-50' : ''
						]"
					>
						<td
							v-for="column in columns"
							:key="String(column.key)"
							class="px-6 py-4"
						>
							<slot
								:name="`cell-${String(column.key)}`"
								:record="record"
								:value="record[column.key]"
								:column="column"
							>
								{{ getCellValue(record, column) }}
							</slot>
						</td>
						<td class="px-6 py-4">
							<div class="flex items-center gap-2">
								<FwbButton
									color="light"
									size="xs"
									class="cursor-pointer"
									@click="startEdit(record)"
								>
									Edit
								</FwbButton>
								<FwbButton
									color="red"
									size="xs"
									class="cursor-pointer"
									@click="deleteRecord(record)"
								>
									Delete
								</FwbButton>
							</div>
						</td>
					</tr>
					<tr v-if="sortedRecords.length === 0">
						<td
							:colspan="columns.length + 1"
							class="px-6 py-8 text-center text-gray-500"
						>
							No records found
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>
