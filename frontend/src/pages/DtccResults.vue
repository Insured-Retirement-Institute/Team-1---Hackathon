<script setup lang="ts">
import { computed } from 'vue';
import { FwbHeading } from 'flowbite-vue';
import ContractResultsTable from '@/components/ContractResultsTable.vue';
import ManualContractDetailsCard from '@/components/ManualContractDetailsCard.vue';
import { useContractResultsStore } from '@/stores/useContractResultsStore';

const contractResultsStore = useContractResultsStore()

const resolvedRecords = computed(() =>
	contractResultsStore.dtccContractResults.filter(r => r.dtccResolved === true)
)

const unresolvedRecords = computed(() =>
	contractResultsStore.dtccContractResults.filter(r => r.dtccResolved !== true)
)

function getRecordIndex(id: string | number): number {
	return contractResultsStore.dtccContractResults.findIndex(r => r.id === id)
}
</script>

<template>
	<div class="w-full">
		<ContractResultsTable
			v-if="resolvedRecords.length > 0"
			:records="resolvedRecords"
			:show-actions="false"
			class="mb-4"
		/>

		<div class="flex flex-wrap *:p-4">
			<div
				v-for="record in unresolvedRecords"
				:key="record.id"
				class="w-1/2"
			>
				<ManualContractDetailsCard
					v-model="contractResultsStore.dtccContractResults[getRecordIndex(record.id)]!"
				/>
			</div>
		</div>

	</div>
</template>

