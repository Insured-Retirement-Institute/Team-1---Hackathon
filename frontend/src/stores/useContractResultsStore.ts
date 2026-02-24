import { ref } from 'vue'
import { defineStore } from 'pinia'
import { AccountType, ContractStatus, OwnershipType, PlanType, type ContractRecord } from '@/models/ContractRecord'
import { useLoaderStore } from '@/stores/useLoaderStore'
import { brokerDealerApi, insuranceCarrierApi } from '@/api/ClearinghouseApi'
import type { DetailedPolicyInfo, PolicyInquiryRequest } from '@/models/ClearinghouseApi'

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
	if (index === 3) {
		contractStatus = ContractStatus.Unappointed
	} else if (index === 4) {
		contractStatus = ContractStatus.Active
	} else {
		contractStatus = randomEnumValue(ContractStatus)
	}

	if (contractStatus === ContractStatus.Unappointed) {
		contractStatus = ContractStatus.Inactive
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
			ownership: randomEnumValue(OwnershipType),
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
	const clientSearch = ref<ClientSearchInfo>({
		firstName: '',
		lastName: '',
		ssn: ''
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
		clientSearch.value = { firstName: '', lastName: '', ssn: '' }
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

	function addSearchContract() {
		searchContracts.value.push(createEmptyContract())
	}

	function removeSearchContract(id: string | number) {
		if (searchContracts.value.length < 2) return
		searchContracts.value = searchContracts.value.filter(c => c.id !== id)
	}

	async function initiateDtccSearch(): Promise<void> {
		const loaderStore = useLoaderStore()
		loaderStore.open('Searching DTCC contracts...')

		const contractNumbers = searchContracts.value
			.filter(c => c.contractNumber.trim() !== '')
			.map(c => c.contractNumber)

		try {
			// Try API call
			const transactionId = crypto.randomUUID()
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
					clientName: `${clientSearch.value.firstName} ${clientSearch.value.lastName}`.trim(),
					ssn: clientSearch.value.ssn,
					policyNumbers: contractNumbers
				}
			}

			const response = await brokerDealerApi.queryPolicies(transactionId, request)

			if (response.client.policies && response.client.policies.length > 0) {
				// Map API response to ContractRecords
				dtccContractResults.value = response.client.policies.map((policy) => {
					const hasErrors = policy.errors && policy.errors.length > 0
					const resolved = !hasErrors && !!policy.carrierName
					return mapDetailedPolicyToContractRecord(policy, resolved)
				})
			} else {
				// Fallback to fake data
				dtccContractResults.value = searchContracts.value
					.filter(c => c.contractNumber.trim() !== '')
					.map((contract, index) => generateFakeDtccResult(contract, index))
			}
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
		loaderStore.open('Searching carrier contracts...')

		const selectedRecords = dtccContractResults.value.filter(r => r.selected)
		const policyNumbers = selectedRecords.map(r => r.contractNumber)

		try {
			// Try API call
			const transactionId = crypto.randomUUID()
			const response = await insuranceCarrierApi.validatePolicies(transactionId, {
				policies: policyNumbers
			})

			if (response.client.policies && response.client.policies.length > 0) {
				// Map API response to ContractRecords with additional carrier info
				carrierContractResults.value = response.client.policies.map(policy => {
					const record = mapDetailedPolicyToContractRecord(policy, true)
					// Try to find matching DTCC record to preserve owner name
					const matchingDtcc = selectedRecords.find(r => r.contractNumber === policy.policyNumber)
					if (matchingDtcc?.ownerName) {
						record.ownerName = matchingDtcc.ownerName
					}
					return record
				})
			} else {
				// Fallback to fake data
				carrierContractResults.value = selectedRecords.map(generateFakeCarrierResult)
			}
		} catch (error) {
			console.warn('API call failed, using fake data:', error)
			// Fallback to fake data on API error
			carrierContractResults.value = selectedRecords.map(generateFakeCarrierResult)
		}

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
