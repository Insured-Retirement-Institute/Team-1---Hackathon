<script setup lang="ts">
import ContractResultsTable from '@/components/ContractResultsTable.vue';
import { useContractResultsStore } from '@/stores/useContractResultsStore';

const contractResultsStore = useContractResultsStore()

</script>

<template>
	<div class="w-full">
		<ContractResultsTable :records="contractResultsStore.carrierContractResults" />

	</div>
</template>
