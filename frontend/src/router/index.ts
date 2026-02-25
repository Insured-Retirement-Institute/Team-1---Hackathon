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
		}
	],
})

export default router
