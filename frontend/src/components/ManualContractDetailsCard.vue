<script setup lang="ts">
import { FwbInput, FwbSelect, FwbCheckbox } from 'flowbite-vue'
import { PlanType, AccountType, OwnershipType, type ContractRecord } from '@/models/ContractRecord'

const record = defineModel<ContractRecord>({ required: true })

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
				<FwbCheckbox v-model="record.selected" />

				<p class="text-gray-900 text-lg font-bold">Contract {{ record.contractNumber }}</p>
			</div>
		</div>

		<div class="grid grid-cols-3 gap-4">
			<FwbInput v-model="record.carrierName" label="Carrier Name" />
			<FwbInput v-model="record.productName" label="Product Name" />
			<FwbInput v-model="record.contractNumber" label="Contract Number" />
			<FwbInput v-model="record.cusipNumber" label="CUSIP" />
			<FwbSelect v-model="record.planType" :options="planTypeOptions" label="Plan Type" />
			<FwbSelect v-model="record.accountType" :options="accountTypeOptions" label="Account Type" />
			<FwbSelect v-model="record.ownership" :options="ownershipOptions" label="Ownership" />
			<FwbInput v-model="record.ownerName" label="Owner Name" />
		</div>
	</div>
</template>
