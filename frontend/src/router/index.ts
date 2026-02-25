import { createRouter, createWebHistory } from 'vue-router'
import { useContractResultsStore } from '@/stores/useContractResultsStore'

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
			path: '/initiate-exchange',
			component: () => import('@/pages/InitiateExchange.vue'),
			meta: {
				title: 'Lookup Contracts',
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
				title: 'DTCC Results',
				next: {
					route: '/carrier-results',
					handler: async () => {
						const contractResultsStore = useContractResultsStore()
						await contractResultsStore.initiateCarrierSearch()
					}
				},
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
				}
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
		}
	],
})

export default router
