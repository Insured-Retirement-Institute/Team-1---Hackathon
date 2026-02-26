import { createRouter, createWebHistory } from 'vue-router'
import { useContractResultsStore } from '@/stores/useContractResultsStore'
import { distributorApi } from '@/api/Api'
import { useLoaderStore } from '@/stores/useLoaderStore'

export interface RouteMeta {
	route: string
	handler?: () => Promise<void> | void
}

const router = createRouter({
	history: createWebHistory(import.meta.env.BASE_URL),
	routes: [
		{
			path: '/',
			component: () => import('@/pages/Home.vue')
		},
		{
			path: '/initiate-exchange/:clientId?',
			component: () => import('@/pages/InitiateExchange.vue'),
			props: true,
			meta: {
				title: 'Enter Contract Details for Client',
				next: {
					route: '/dtcc-results',
					handler: async () => {
						const contractResultsStore = useContractResultsStore()
						await contractResultsStore.initiateDtccSearch()
					}
				}
			}
		},
		{
			path: '/dtcc-results',
			component: () => import('@/pages/DtccResults.vue'),
			meta: {
				title: 'Contract Results from DTCC',
				// next: {
				// 	route: '/carrier-results',
				// 	handler: async () => {
				// 		const contractResultsStore = useContractResultsStore()
				// 		await contractResultsStore.initiateCarrierSearch()
				// 	}
				// },
				previous: {
					route: '/initiate-exchange'
				}
			}
		},
		{
			path: '/carrier-results',
			component: () => import('@/pages/CarrierResults.vue'),
			meta: {
				title: 'Carrier Check Result',
				previous: {
					route: '/dtcc-results'
				},
				nextLabel: 'Submit Transfer',
				next: {
					route: '/',
					handler: async () => {
						const loaderStore = useLoaderStore()
						try {
							const { clientSearch, carrierContractResults } = useContractResultsStore()

							loaderStore.open('Submitting Transfer')

							const result = await distributorApi.createRequest('12345678', {
								clientId: clientSearch.clientId,
								contracts: carrierContractResults.filter(r => r.dtccResolved).map(r => r.contractNumber),
								receivingBrokerId: 'BD002',
							})

						} catch(e) {
							console.error(e)
						} finally {
							loaderStore.close()
						}
					}
				},
			}
		},
		{
			path: '/carrier-admin',
			component: () => import('@/pages/carrier/CarrierAdmin.vue')
		},
		{
			path: '/carrier-admin/:carrier',
			component: () => import('@/pages/carrier/CarrierAdmin.vue')
		},
		{
			path: '/api-health',
			component: () => import('@/pages/ApiHealth.vue'),
			meta: {
				title: 'API Health'
			}
		},
		{
			path: '/event-source-health',
			component: () => import('@/pages/EventSourceHealth.vue'),
			meta: {
				title: 'EventSource Monitor'
			}
		},
		{
			path: '/request-contract/:requestId',
			component: () => import('@/pages/RequestContracts.vue'),
			props: true,
			meta: {
				title: 'Request Contracts'
			}
		}
	],
})

export default router
