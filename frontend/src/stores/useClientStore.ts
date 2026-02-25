import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Client } from '@/models/Client'

const FIRST_NAMES = [
	'John', 'Mary', 'Robert', 'Patricia', 'Michael', 'Jennifer',
	'William', 'Elizabeth', 'David', 'Barbara', 'James', 'Susan',
	'Richard', 'Jessica', 'Joseph', 'Sarah', 'Thomas', 'Karen',
	'Charles', 'Nancy', 'Christopher', 'Lisa', 'Daniel', 'Betty'
]

const LAST_NAMES = [
	'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia',
	'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez',
	'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore',
	'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White'
]

function randomElement<T>(arr: T[]): T {
	return arr[Math.floor(Math.random() * arr.length)]!
}

function generateAccountNumber(): string {
	const prefix = Math.random() > 0.5 ? 'ACC' : 'CLT'
	const number = Math.floor(Math.random() * 900000000) + 100000000
	return `${prefix}-${number}`
}

function generateRandomDate(daysBack: number): string {
	const date = new Date()
	date.setDate(date.getDate() - Math.floor(Math.random() * daysBack))
	return date.toISOString()
}

function generateMockClients(count: number): Client[] {
	const clients: Client[] = []
	for (let i = 0; i < count; i++) {
		const firstName = randomElement(FIRST_NAMES)
		const lastName = randomElement(LAST_NAMES)
		const email = `${firstName.toLowerCase()}.${lastName.toLowerCase()}@email.com`
		clients.push({
			id: crypto.randomUUID(),
			firstName,
			lastName,
			email,
			accountNumber: generateAccountNumber(),
			updatedDate: generateRandomDate(90),
			numberOfContracts: Math.floor(Math.random() * 10) + 1
		})
	}
	return clients
}

export const useClientStore = defineStore('client', () => {
	const clients = ref<Client[]>([])
	const isLoading = ref(false)

	async function loadClients() {
		isLoading.value = true
		try {
			// Simulate API call with mock data
			await new Promise(resolve => setTimeout(resolve, 300))
			clients.value = generateMockClients(15)
		} finally {
			isLoading.value = false
		}
	}

	function getClientById(id: string): Client | undefined {
		return clients.value.find(c => c.id === id)
	}

	return {
		clients,
		isLoading,
		loadClients,
		getClientById
	}
})
