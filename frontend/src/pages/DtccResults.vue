<script setup lang="ts">
import { computed } from 'vue';
import ContractResultsTable from '@/components/ContractResultsTable.vue';
import ManualContractDetailsCard from '@/components/ManualContractDetailsCard.vue';
import { useContractResultsStore } from '@/stores/useContractResultsStore';
import QuestionCircleIcon from '@/icons/QuestionCircle.svg'
import FingerPrintIcon from '@/icons/FingerPrintIcon.svg'

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

		<div class="rounded-xl bg-[#f8f8f8] p-6">
			<div class="flex items-center gap-2 pl-4 mb-1">
				<FingerPrintIcon />
				<p class="font-bold text-2xl">Qualified Contracts</p>
			</div>

			<p class="text-l pl-4 mb-1">The following contract(s) had no electronic records. If you would like to transfer them, further information is required.</p>

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

		<div class="rounded-xl bg-[#f8f8f8] p-6 mt-4">
			<div class="flex items-center gap-2 pl-4 mb-1">
				<QuestionCircleIcon />
				<p class="font-bold text-2xl">No Electronic Records found</p>
			</div>

			<p class="text-l pl-4 mb-1">Because the contract is custodially owned, updated ownership and beneficiary information is required to continue the transfer.</p>

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
	</div>
</template>

