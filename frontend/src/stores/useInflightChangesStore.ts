import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { InflightChange } from '@/models/InflightChange'

function generateContractNumber(): string {
	const prefixes = ['POL', 'CNT', 'AGR', 'ANT']
	const prefix = prefixes[Math.floor(Math.random() * prefixes.length)]
	const number = Math.floor(Math.random() * 9000000) + 1000000
	return `${prefix}-${number}`
}

function generateRandomDate(daysBack: number): string {
	const date = new Date()
	date.setDate(date.getDate() - Math.floor(Math.random() * daysBack))
	return date.toISOString()
}

function generateMockInflightChanges(clientIds: string[], count: number): InflightChange[] {
	const changes: InflightChange[] = []
	for (let i = 0; i < count; i++) {
		const clientId = clientIds.length > 0
			? clientIds[Math.floor(Math.random() * clientIds.length)]!
			: crypto.randomUUID()

		changes.push({
			id: crypto.randomUUID(),
			clientId,
			contractNumber: generateContractNumber(),
			completionPercentage: Math.floor(Math.random() * 100),
			lastUpdatedDate: generateRandomDate(30)
		})
	}
	return changes
}

export const useInflightChangesStore = defineStore('inflightChanges', () => {
	const inflightChanges = ref<InflightChange[]>([])
	const isLoading = ref(false)

	async function loadInflightChanges(clientIds: string[] = []) {
		isLoading.value = true
		try {
			// Simulate API call with mock data
			await new Promise(resolve => setTimeout(resolve, 300))
			inflightChanges.value = generateMockInflightChanges(clientIds, 12)
		} finally {
			isLoading.value = false
		}
	}

	function getChangesByClientId(clientId: string): InflightChange[] {
		return inflightChanges.value.filter(c => c.clientId === clientId)
	}

	return {
		inflightChanges,
		isLoading,
		loadInflightChanges,
		getChangesByClientId
	}
})
