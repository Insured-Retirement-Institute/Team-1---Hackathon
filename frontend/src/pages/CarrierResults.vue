<script setup lang="ts">
import ContractResultsTable from '@/components/ContractResultsTable.vue';
import { useContractResultsStore } from '@/stores/useContractResultsStore';
import { FwbButton } from 'flowbite-vue';
import DownloadIcon from '@/icons/DownloadIcon.svg'

const contractResultsStore = useContractResultsStore()

</script>

<template>
	<div class="w-full">
		<ContractResultsTable :records="contractResultsStore.carrierContractResults" />

		<div class="rounded-xl bg-[#f8f8f8] p-6 flex flex-col items-center justify-center mt-4">
			<div class="flex items-center justify-center">
				<FwbButton>
					Download Carrier Letter

					<template #prefix>
						<DownloadIcon />
					</template>
				</FwbButton>
			</div>
		</div>
	</div>
</template>
