import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Transaction } from '@/models/Transaction'
import { distributorApi } from '@/api/Api'

export const useInflightChangesStore = defineStore('inflightChanges', () => {
	const inflightChanges = ref<Transaction[]>([])
	const isLoading = ref(false)

	async function loadInflightChanges(npn: string = '12345678') {
		isLoading.value = true
		try {
			const result = await distributorApi.getAgentRequests(npn)
			inflightChanges.value = result.requests
		} catch (error) {
			console.error('Failed to load transactions:', error)
		} finally {
			isLoading.value = false
		}
	}

	function getChangesByClientId(clientId: string): Transaction[] {
		return inflightChanges.value.filter(c => c.clientId === clientId)
	}

	return {
		inflightChanges,
		isLoading,
		loadInflightChanges,
		getChangesByClientId
	}
})
