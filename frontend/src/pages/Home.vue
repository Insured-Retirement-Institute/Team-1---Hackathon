<script setup lang="ts">
import { onMounted } from 'vue'
import ClientsTable from '@/components/ClientsTable.vue'
import InflightChangesTable from '@/components/InflightChangesTable.vue'
import { useClientStore } from '@/stores/useClientStore'
import { useInflightChangesStore } from '@/stores/useInflightChangesStore'

const clientStore = useClientStore()
const inflightChangesStore = useInflightChangesStore()

onMounted(async () => {
	await clientStore.loadClients()
	const clientIds = clientStore.clients.map(c => c.id)
	await inflightChangesStore.loadInflightChanges(clientIds)
})
</script>

<template>
	<div class="w-full space-y-6">
		<InflightChangesTable :changes="inflightChangesStore.inflightChanges" :clients="clientStore.clients" />

		<ClientsTable :clients="clientStore.clients" />
	</div>
</template>
