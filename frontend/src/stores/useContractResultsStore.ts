import { ref } from 'vue'
import { defineStore } from 'pinia'
import { AccountType, ContractStatus, OwnershipType, PlanType, type ContractRecord } from '@/models/ContractRecord'
import { useLoaderStore } from '@/stores/useLoaderStore'
import { brokerDealerApi, distributorApi, insuranceCarrierApi } from '@/api/Api'
import { isClientResponse, type DetailedPolicyInfo, type PolicyInquiryRequest } from '@/models/ClearinghouseApi'
import { ulid } from 'ulid'
import { groupBy } from 'lodash'
import type { Client } from '@/models/Client'
import { useClientStore } from './useClientStore'
import { useEventSource } from '@/utils/useEventSource'
import type { Contract } from '@/models/Contract'

const CARRIER_PRODUCTS: Record<string, string> = {
	'Allianz Life': 'Allianz 222® Annuity',
	'Nationwide': 'Nationwide Peak® 10',
	'Lincoln Financial': 'Lincoln OptiBlend®',
	'MassMutual': 'MassMutual Stable Voyage℠',
	'Pacific Life': 'Pacific Index Foundation®',
	'Corebridge Financial': 'Power Series Index Annuity / Power Index Advisory®',
	'Jackson (Jackson National)': 'Perspective II®',
	'Brighthouse Financial': 'Shield® Level II Annuities',
	'Prudential': 'FlexGuard® Indexed Variable Annuity',
	'New York Life (NYLIAC)': 'Secure Term MVA Fixed Annuity II',
	'Athene': 'Athene Agility',
	'Global Atlantic': 'ForeIncome II',
	'F&G (Fidelity & Guaranty Life)': 'Safe Income Advantage®',
	'American Equity': 'IncomeShield',
	'EquiTrust Life Insurance Company': 'MarketMax Index™ Annuity',
	'Symetra': 'Symetra Trek Plus',
	'North American Company': 'NAC BenefitSolutions® 10',
	'Delaware Life': 'Target Growth 10®',
	'Securian Financial': 'AccumuLink™ Advance',
	'American National': 'Palladium® Multi-Year Guarantee Annuity (MYG)'
}

const CARRIER_NAMES = Object.keys(CARRIER_PRODUCTS)

const OWNER_NAMES = [
	'John Smith', 'Mary Johnson', 'Robert Williams', 'Patricia Brown',
	'Michael Davis', 'Jennifer Miller', 'William Wilson', 'Elizabeth Moore',
	'David Taylor', 'Barbara Anderson', 'James Thomas', 'Susan Jackson'
]

function randomElement<T>(arr: T[]): T {
	return arr[Math.floor(Math.random() * arr.length)]!
}

function randomEnumValue<T extends Record<string, string>>(enumObj: T): T[keyof T] {
	const values = Object.values(enumObj) as T[keyof T][]
	return values[Math.floor(Math.random() * values.length)]!
}

function generateCusipNumber(): string {
	const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
	let cusip = ''
	for (let i = 0; i < 6; i++) cusip += Math.floor(Math.random() * 10)
	for (let i = 0; i < 2; i++) cusip += chars[Math.floor(Math.random() * chars.length)]
	cusip += Math.floor(Math.random() * 10)
	return cusip
}

function mapDetailedPolicyToContractRecord(policy: DetailedPolicyInfo, resolved: boolean): ContractRecord {
	return {
		id: crypto.randomUUID(),
		contractNumber: policy.policyNumber ?? '',
		carrierName: policy.carrierName ?? '',
		productName: policy.productName ?? '',
		cusipNumber: policy.cusip ?? '',
		ownership: policy.ownership ?? '',
		planType: mapApiPlanType(policy.planType),
		accountType: mapApiAccountType(policy.accountType),
		trailing: policy.trailingCommission,
		withdrawalProgram: policy.withdrawalStructure?.systematicInPlace ?? false,
		withdrawalStructure: policy.withdrawalStructure,
		contractStatus: mapApiContractStatus(policy.contractStatus),
		errors: policy.errors,
		dtccResolved: resolved,
		selected: false
	}
}

function mapApiPlanType(apiPlanType: string | null | undefined): PlanType | undefined {
	if (!apiPlanType) return undefined
	const mapping: Record<string, PlanType> = {
		nonQualified: PlanType.NonQualified,
		rothIra: PlanType.RothIRA,
		traditionalIra: PlanType.TraditionalIRA,
		sep: PlanType.SepIRA,
		simple: PlanType.SimpleIRA
	}
	return mapping[apiPlanType]
}

function mapApiAccountType(apiAccountType: string | null | undefined): AccountType | undefined {
	if (!apiAccountType) return undefined
	const mapping: Record<string, AccountType> = {
		individual: AccountType.Individual,
		joint: AccountType.JointOwned,
		trust: AccountType.Trust,
		entity: AccountType.Entity
	}
	return mapping[apiAccountType]
}

function mapApiContractStatus(apiStatus: string | null | undefined): ContractStatus {
	if (!apiStatus) return ContractStatus.Inactive
	const mapping: Record<string, ContractStatus> = {
		active: ContractStatus.Active,
		inactive: ContractStatus.Inactive,
		distributionspecific: ContractStatus.DistributionSpecific,
		fullwithdrawalpending: ContractStatus.FullWithdrawalPending,
		carrierpending: ContractStatus.CarrierPending,
		carrierspecific: ContractStatus.CarrierSpecific,
		restricted: ContractStatus.ActiveRestricted,
		ownershipissue: ContractStatus.OwnershipIssue,
		notlicensed: ContractStatus.NotLicensed,
		unappointed: ContractStatus.Unappointed
	}

	return mapping[apiStatus.toLowerCase().replace(/[^a-z]/g, '')] ?? ContractStatus.Inactive
}

function generateFakeDtccResult(searchContract: ContractRecord, index: number): ContractRecord {
	const resolved = index > 1 // First record is unresolved, rest are resolved

	// Determine contract status based on index
	let contractStatus: ContractStatus
	let ownership : OwnershipType
	if (index === 2) {
		ownership = OwnershipType.Custodial
	} else {
		ownership = randomEnumValue(OwnershipType)
	}
	if (index === 3) {
		contractStatus = ContractStatus.Unappointed
	} else if (index === 4) {
		contractStatus = ContractStatus.Active
	} else {
		contractStatus = randomEnumValue(ContractStatus)
	}

	if (resolved) {
		const carrierName = randomElement(CARRIER_NAMES)
		const productName = CARRIER_PRODUCTS[carrierName]!
		return {
			id: crypto.randomUUID(),
			carrierName,
			productName,
			contractNumber: searchContract.contractNumber,
			cusipNumber: generateCusipNumber(),
			ownership,
			trailing: Math.random() > 0.5,
			withdrawalProgram: Math.random() > 0.5,
			contractStatus,
			dtccResolved: true,
			selected: false
		}
	}

	// Unresolved - return partial data
	return {
		id: crypto.randomUUID(),
		carrierName: '',
		productName: '',
		contractNumber: searchContract.contractNumber,
		cusipNumber: '',
		ownership: '',
		trailing: false,
		withdrawalProgram: false,
		contractStatus: ContractStatus.Inactive,
		dtccResolved: false,
		selected: false
	}
}

function generateFakeCarrierResult(dtccRecord: ContractRecord): ContractRecord {
	return {
		...dtccRecord,
		id: crypto.randomUUID(),
		planType: randomEnumValue(PlanType),
		accountType: randomEnumValue(AccountType),
		ownerName: randomElement(OWNER_NAMES),
		// Potentially update status based on carrier lookup
		contractStatus: Math.random() > 0.2 ? ContractStatus.Active : randomEnumValue(ContractStatus),
		selected: false
	}
}

export interface ClientSearchInfo {
	firstName: string
	lastName: string
	ssn: string
}

export const useContractResultsStore = defineStore('contractResults', () => {
	const searchContracts = ref<ContractRecord[]>([])
	const dtccContractResults = ref<ContractRecord[]>([])
	const carrierContractResults = ref<ContractRecord[]>([])
	const clientSearch = ref<Client>({
		clientName: '',
		ssnLast4: '',
		clientId: '',
		pk: '',
		sk: '',
		type: '',
		assignedAt: ''
	})

	function resetSearchContracts() {
		searchContracts.value = []
	}

	function resetDtccContractResults() {
		dtccContractResults.value = []
	}

	function resetCarrierContractResults() {
		carrierContractResults.value = []
	}

	function resetAll() {
		resetSearchContracts()
		resetDtccContractResults()
		resetCarrierContractResults()
		clientSearch.value = {
			clientId: '',
			clientName: '',
			ssnLast4: '',
			pk: '',
			sk: '',
			type: '',
			assignedAt: ''
		}
	}

	function createEmptyContract(): ContractRecord {
		return {
			id: crypto.randomUUID(),
			carrierName: '',
			productName: '',
			contractNumber: '',
			cusipNumber: '',
			ownership: '',
			trailing: false,
			withdrawalProgram: false,
			contractStatus: ContractStatus.Active
		}
	}

	function addSearchContract(options: Partial<ContractRecord> = {}) {
		const contract = createEmptyContract()
		searchContracts.value.push({
			...contract,
			...options
		})
	}

	function removeSearchContract(id: string | number) {
		if (searchContracts.value.length < 2) return
		searchContracts.value = searchContracts.value.filter(c => c.id !== id)
	}

	async function initiateDtccSearch(): Promise<void> {
		const loaderStore = useLoaderStore()
		loaderStore.open('Locating Contracts')

		if (!clientSearch.value.clientId) {
			await distributorApi.createClient({
				clientName: clientSearch.value.clientName,
				ssnLast4: clientSearch.value.ssnLast4
			})
		}

		const contractNumbers = searchContracts.value
			.filter(c => c.contractNumber.trim() !== '')
			.map(c => c.contractNumber)

		try {
			const request: PolicyInquiryRequest = {
				requestingFirm: {
					firmName: 'Demo Firm',
					firmId: 'DEMO001',
					servicingAgent: {
						agentName: 'Demo Agent',
						npn: '12345678'
					}
				},
				client: {
					clientName: clientSearch.value.clientName.trim(),
					ssn: clientSearch.value.ssnLast4,
					policyNumbers: contractNumbers
				}
			}

			const response = await brokerDealerApi.triggerPolicyInquiry(request)

			const result = await useEventSource().waitForEvent<any>(data => data.payload.detail.requestId === response.requestId)

			const policies = (result as any).payload.detail.body.payload.client.policies as Contract[]

			console.log(policies)

			dtccContractResults.value = policies.map(contract => ({
				id: crypto.randomUUID(),
				contractNumber: contract.policyNumber ?? '',
				carrierName: contract.carrierName ?? '',
				productName: contract.productName ?? '',
				cusipNumber: contract.cusip ?? '',
				ownership: contract.ownership === 'individual' ? OwnershipType.Individual :
					contract.ownership === 'trust' ? OwnershipType.TrustAccount :
					contract.ownership === 'custodian' ? OwnershipType.Custodial :
					OwnershipType.EntityAccount,
				planType: mapApiPlanType(contract.planType),
				accountType: undefined,
				trailing: contract.hasTrailingCommission ?? false,
				withdrawalProgram: contract.hasSystematicWithdrawal ?? false,
				contractStatus: mapApiContractStatus(contract.contractStatus),
				dtccResolved: !!contract.carrierName,
				selected: false
			}))

		} catch (error) {
			console.warn('API call failed, using fake data:', error)
			// Fallback to fake data on API error
			dtccContractResults.value = searchContracts.value
				.filter(c => c.contractNumber.trim() !== '')
				.map((contract, index) => generateFakeDtccResult(contract, index))
		}

		loaderStore.close()
	}

	async function initiateCarrierSearch(): Promise<void> {
		const loaderStore = useLoaderStore()

		const autoLookup = dtccContractResults.value.filter(r => r.dtccResolved)

		loaderStore.open('Validating')

		const selectedRecords = dtccContractResults.value.filter(r => r.selected)
		const policyNumbers = selectedRecords.map(r => r.contractNumber)

		carrierContractResults.value = [...dtccContractResults.value]

		if (autoLookup.length) {
			try {
				// Try API call
				const response = await insuranceCarrierApi.validatePolicies({
					carrier: {
						carrierName: selectedRecords[0]?.carrierName,
						carrierId: 'ATH1'
					},
					requestingFirm: {
						firmName: 'Firms',
						servicingAgent: {
							agentName: 'Agent Test',
							npn: '12345678'
						}
					},
					client: {
						clientName: clientSearch.value.clientName,
						policyNumbers,
					},

				})

				console.log('hey', response)

				await new Promise<void>((resolve) => {
					const id = setInterval(async () => {
						const result = await fetch(`https://sv4fyqvgj3vwuwflc5olwwa4xq0hcele.lambda-url.us-east-1.on.aws/v1/servicing-agent-changes/reply/${response.requestId}`)

						if (result.ok) {
							const data = await result.json()
							console.log('Servicing change reply:', data)

							if ((data.determination === 'approved' || data.determination === 'rejected') && data.response?.policies) {
								// Update carrier contract results with the new statuses
								for (const policy of data.response.policies) {
									const contractIndex = carrierContractResults.value.findIndex(
										c => c.contractNumber === policy.policyNumber
									)
									if (contractIndex !== -1) {
										const existing = carrierContractResults.value[contractIndex]!
										if (policy.status === 'approved') {
											existing.contractStatus = ContractStatus.Active
										} else if (policy.status === 'rejected') {
											existing.contractStatus = ContractStatus.CarrierSpecific
										} else {
											existing.contractStatus = mapApiContractStatus(policy.status)
										}
										existing.effectiveDate = policy.effectiveDate ?? undefined
										existing.errors = policy.errors
										existing.selected = false
									}
								}
								clearInterval(id)
								resolve()
							}
						}
					}, 2_000)
				})
				// const result = await useEventSource().waitForEvent<any>(data => data.payload.detail.requestId === response.requestId)


				// const policies = (result as any).payload.detail.body.payload.client.policies as Contract[]

				// console.log(policies)

				// if (response.client.policies && response.client.policies.length > 0) {
				// 	// Map API response to ContractRecords with additional carrier info
				// 	carrierContractResults.value = response.client.policies.map(policy => {
				// 		const record = mapDetailedPolicyToContractRecord(policy, true)
				// 		// Try to find matching DTCC record to preserve owner name
				// 		const matchingDtcc = selectedRecords.find(r => r.contractNumber === policy.policyNumber)
				// 		if (matchingDtcc?.ownerName) {
				// 			record.ownerName = matchingDtcc.ownerName
				// 		}
				// 		return record
				// 	})
				// } else {
				// 	// Fallback to fake data
				// 	carrierContractResults.value = selectedRecords.map(generateFakeCarrierResult)
				// }
			} catch (error) {
				console.warn('API call failed, using fake data:', error)
				// Fallback to fake data on API error
				carrierContractResults.value = selectedRecords.map(generateFakeCarrierResult)
			} finally {
			}
		}

		await new Promise(resolve => setTimeout(resolve, 500))

		loaderStore.close()
	}

	return {
		searchContracts,
		dtccContractResults,
		carrierContractResults,
		clientSearch,
		resetSearchContracts,
		resetDtccContractResults,
		resetCarrierContractResults,
		resetAll,
		createEmptyContract,
		addSearchContract,
		removeSearchContract,
		initiateDtccSearch,
		initiateCarrierSearch
	}
})
