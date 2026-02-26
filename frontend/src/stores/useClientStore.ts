import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Client } from '@/models/Client'
import { distributorApi } from '@/api/Api'

export const useClientStore = defineStore('client', () => {
	const clients = ref<Client[]>([])
	const isLoading = ref(false)

	async function loadClients() {
		isLoading.value = true
		try {
			const result = (await distributorApi.getAgentClients('12345678')).clients
			console.log(result)
			clients.value = result
		} catch (error) {
			console.error('Failed to load clients:', error)
		} finally {
			isLoading.value = false
		}
	}

	function getClientById(clientId: string): Client | undefined {
		return clients.value.find(c => c.clientId === clientId)
	}

	return {
		clients,
		isLoading,
		loadClients,
		getClientById
	}
})
