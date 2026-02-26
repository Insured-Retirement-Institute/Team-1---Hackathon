import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Request } from '@/models/Transaction'
import { distributorApi } from '@/api/Api'

export const useInflightChangesStore = defineStore('inflightChanges', () => {
	const inflightChanges = ref<Request[]>([])
	const isLoading = ref(false)

	async function loadInflightChanges(npn: string = '12345678') {
		isLoading.value = true
		try {
			const result = await distributorApi.getAgentRequests(npn)
			inflightChanges.value = result.requests
		} catch (error) {
			console.error('Failed to load requests:', error)
		} finally {
			isLoading.value = false
		}
	}

	function getChangesByClientId(clientId: string): Request[] {
		return inflightChanges.value.filter(c => c.clientId === clientId)
	}

	return {
		inflightChanges,
		isLoading,
		loadInflightChanges,
		getChangesByClientId
	}
})
