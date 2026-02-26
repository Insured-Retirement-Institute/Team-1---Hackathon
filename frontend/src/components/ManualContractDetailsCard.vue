<script setup lang="ts">
import { computed } from 'vue'
import { FwbInput, FwbSelect, FwbCheckbox, FwbButton } from 'flowbite-vue'
import { PlanType, AccountType, OwnershipType, type ContractRecord } from '@/models/ContractRecord'
import CustodialInfoCard from '@/components/CustodialInfoCard.vue'
import { brokerDealerApi } from '@/api/Api'
import { ulid } from 'ulid'
import { useLoaderStore } from '@/stores/useLoaderStore'
import DownloadIcon from '@/icons/DownloadIcon.svg'
import { useContractResultsStore } from '@/stores/useContractResultsStore'

const record = defineModel<ContractRecord>({ required: true })
const loaderStore = useLoaderStore()

const props = withDefaults(defineProps<{
	displayContractData?: boolean
	showCheckbox?: boolean
	showDownloadCarrierLetter?: boolean
}>(), {
	displayContractData: true,
	showCheckbox: true,
	showDownloadCarrierLetter: false
})

async function downloadCarrierLetter() {
	try {
		const { clientSearch } = useContractResultsStore()
		await brokerDealerApi.generateCarrierLetter({
			requestId: ulid(),
			carrierName: record.value.carrierName ?? '',
			carrierDepartment: 'Annuity Operations',
			carrierAddress: {
				line1: '700 Newport Center Drive',
				city: 'Newport Beach',
				state: 'CA',
				zip: '92660'
			},
			client: {
				name: clientSearch.clientName,
				last4Ssn: clientSearch.ssnLast4
			},
			policyNumbers: [record.value.contractNumber],
			currentAgent: {
				name: 'Test Agent',
				npn: '234543'
			},
			newAgent: {
				name: 'Sarah Mitchell',
				npn: '99887766',
				bdName: 'IRI Brokerage Inc',
				bdDtccId: 'BD-1001'
			},
			reasonForChange: 'Client-requested advisor transition',
			trailingCommission: 'no',
			requestingFirm: {
				name: 'Firm One',
				contact: 'Operations Dept',
				phone: '555-123-4567'
			}
		})
	} catch (e) {
		console.error(e)
	} finally {
	}
}

// Initialize custodialInfo if not present
if (!record.value.custodialInfo) {
	record.value.custodialInfo = {}
}

const isCustodial = computed(() => record.value.ownership === OwnershipType.Custodial)

const planTypeOptions = [
	{ value: PlanType.NonQualified, name: PlanType.NonQualified },
	{ value: PlanType.RothIRA, name: PlanType.RothIRA },
	{ value: PlanType.TraditionalIRA, name: PlanType.TraditionalIRA },
	{ value: PlanType.SepIRA, name: PlanType.SepIRA },
	{ value: PlanType.SimpleIRA, name: PlanType.SimpleIRA }
]

const accountTypeOptions = [
	{ value: AccountType.Individual, name: AccountType.Individual },
	{ value: AccountType.JointOwned, name: AccountType.JointOwned },
	{ value: AccountType.Trust, name: AccountType.Trust },
	{ value: AccountType.Entity, name: AccountType.Entity }
]

const ownershipOptions = [
	{ value: OwnershipType.Individual, name: OwnershipType.Individual },
	{ value: OwnershipType.JointOwned, name: OwnershipType.JointOwned },
	{ value: OwnershipType.TrustOwned, name: OwnershipType.TrustOwned },
	{ value: OwnershipType.EntityOwned, name: OwnershipType.EntityOwned },
	{ value: OwnershipType.Custodial, name: OwnershipType.Custodial },
	{ value: OwnershipType.JointOwnedAccount, name: OwnershipType.JointOwnedAccount },
	{ value: OwnershipType.TrustAccount, name: OwnershipType.TrustAccount },
	{ value: OwnershipType.EntityAccount, name: OwnershipType.EntityAccount }
]
</script>

<template>
	<div
		class="bg-white rounded-xl p-6 mb-4"
		:class="{ 'outline-blue-600 outline-2': record.selected }"
	>
		<div class="flex items-center justify-between mb-4">
			<div class="flex items-center gap-2">
				<FwbCheckbox v-if="props.showCheckbox" v-model="record.selected" />

				<p class="text-gray-900 text-lg font-bold">Contract {{ record.contractNumber }}</p>
			</div>
			<FwbButton v-if="props.showDownloadCarrierLetter" color="light" @click="downloadCarrierLetter" class="cursor-pointer">
				Download Carrier Letter
				<template #prefix>
					<DownloadIcon />
				</template>
			</FwbButton>
		</div>

		<!-- Contract Data Section -->
		<div v-if="displayContractData" class="grid grid-cols-3 gap-4">
			<FwbInput v-model="record.carrierName" label="Carrier Name" />
			<FwbInput v-model="record.productName" label="Product Name" />
			<FwbInput v-model="record.contractNumber" label="Contract Number" />
			<FwbInput v-model="record.cusipNumber" label="CUSIP" />
			<FwbSelect v-model="record.planType" :options="planTypeOptions" label="Plan Type" />
			<FwbSelect v-model="record.accountType" :options="accountTypeOptions" label="Account Type" />
			<FwbSelect v-model="record.ownership" :options="ownershipOptions" label="Ownership" />
			<FwbInput v-model="record.ownerName" label="Owner Name" />
		</div>

		<!-- Custodial Data Section -->
		<div v-if="isCustodial" :class="{ 'mt-6': displayContractData }">
			<CustodialInfoCard v-model="record.custodialInfo!" />
		</div>
	</div>
</template>
