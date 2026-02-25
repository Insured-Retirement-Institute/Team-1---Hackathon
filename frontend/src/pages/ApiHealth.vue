<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { checkBrokerDealerHealth, checkClearingHouseHealth, checkCarrierHealth } from '@/api/Api'

interface HealthStatus {
	name: string
	status: 'healthy' | 'unhealthy' | 'loading'
	responseTime?: number
	error?: string
}

const healthStatuses = ref<HealthStatus[]>([
	{ name: 'Broker-Dealer API', status: 'loading' },
	{ name: 'Clearinghouse API', status: 'loading' },
	{ name: 'Insurance Carrier API', status: 'loading' }
])

const isRefreshing = ref(false)

async function checkHealth(
	index: number,
	checkFn: () => Promise<Response>
) {
	const healthStatus = healthStatuses.value[index]
	if (!healthStatus) return

	healthStatus.status = 'loading'
	healthStatus.error = undefined

	const startTime = performance.now()
	try {
		const response = await checkFn()
		const endTime = performance.now()

		healthStatus.responseTime = Math.round(endTime - startTime)
		healthStatus.status = response.ok ? 'healthy' : 'unhealthy'

		if (!response.ok) {
			healthStatus.error = `HTTP ${response.status}`
		}
	} catch (error) {
		const endTime = performance.now()
		healthStatus.responseTime = Math.round(endTime - startTime)
		healthStatus.status = 'unhealthy'
		healthStatus.error = error instanceof Error ? error.message : 'Unknown error'
	}
}

async function refreshAllHealth() {
	isRefreshing.value = true
	await Promise.all([
		checkHealth(0, checkBrokerDealerHealth),
		checkHealth(1, checkClearingHouseHealth),
		checkHealth(2, checkCarrierHealth)
	])
	isRefreshing.value = false
}

onMounted(() => {
	refreshAllHealth()
})
</script>

<template>
	<div class="w-full max-w-3xl mx-auto space-y-6">
		<div class="flex items-center justify-between">
			<h1 class="text-2xl font-bold text-gray-900">API Health Status</h1>
			<button
				@click="refreshAllHealth"
				:disabled="isRefreshing"
				class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
			>
				<svg
					v-if="isRefreshing"
					class="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
				>
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
				</svg>
				{{ isRefreshing ? 'Refreshing...' : 'Refresh' }}
			</button>
		</div>

		<div class="bg-white shadow overflow-hidden sm:rounded-lg">
			<ul class="divide-y divide-gray-200">
				<li
					v-for="health in healthStatuses"
					:key="health.name"
					class="px-4 py-4 sm:px-6"
				>
					<div class="flex items-center justify-between">
						<div class="flex items-center space-x-3">
							<span
								class="shrink-0 h-3 w-3 rounded-full"
								:class="{
									'bg-green-500': health.status === 'healthy',
									'bg-red-500': health.status === 'unhealthy',
									'bg-gray-300 animate-pulse': health.status === 'loading'
								}"
							></span>
							<p class="text-sm font-medium text-gray-900">{{ health.name }}</p>
						</div>
						<div class="flex items-center space-x-4">
							<span
								v-if="health.responseTime !== undefined"
								class="text-sm text-gray-500"
							>
								{{ health.responseTime }}ms
							</span>
							<span
								class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
								:class="{
									'bg-green-100 text-green-800': health.status === 'healthy',
									'bg-red-100 text-red-800': health.status === 'unhealthy',
									'bg-gray-100 text-gray-800': health.status === 'loading'
								}"
							>
								{{ health.status === 'loading' ? 'Checking...' : health.status }}
							</span>
						</div>
					</div>
					<p
						v-if="health.error"
						class="mt-2 text-sm text-red-600"
					>
						{{ health.error }}
					</p>
				</li>
			</ul>
		</div>
	</div>
</template>
