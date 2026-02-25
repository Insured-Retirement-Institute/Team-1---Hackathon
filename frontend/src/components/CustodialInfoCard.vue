<script setup lang="ts">
import { computed } from 'vue'
import { FwbInput, FwbSelect, FwbButton, FwbCheckbox } from 'flowbite-vue'
import FormTable, { type Column } from '@/components/FormTable.vue'
import {
	CustodialOwnershipType,
	SigningOption,
	BeneficiaryType,
	TaxIdType,
	type CustodialInfo,
	type Beneficiary
} from '@/models/ContractRecord'
import { monotonicFactory } from 'ulid'

const ulid = monotonicFactory()

const custodialInfo = defineModel<CustodialInfo>({ required: true })

const ownershipTypeOptions = [
	{ value: CustodialOwnershipType.Person, name: CustodialOwnershipType.Person },
	{ value: CustodialOwnershipType.Entity, name: CustodialOwnershipType.Entity }
]

const signingOptions = [
	{ value: SigningOption.ESign, name: 'E-Sign' },
	{ value: SigningOption.WetSign, name: 'Wet-Sign' }
]

const beneficiaryTypeOptions = [
	{ value: BeneficiaryType.Person, name: BeneficiaryType.Person },
	{ value: BeneficiaryType.Trust, name: BeneficiaryType.Trust }
]

const taxTypeOptions = [
	{ value: TaxIdType.SSN, name: TaxIdType.SSN },
	{ value: TaxIdType.TIN, name: TaxIdType.TIN }
]

const isPerson = computed(() => custodialInfo.value.ownershipType === CustodialOwnershipType.Person)

const beneficiaryColumns: Column<Beneficiary>[] = [
	{ key: 'firstName', label: 'First Name' },
	{ key: 'lastName', label: 'Last Name' },
	{ key: 'beneficiaryType', label: 'Type' },
	{ key: 'allocationPercentage', label: 'Allocation %' }
]

function createBeneficiary(): Beneficiary {
	return {
		id: ulid(),
		beneficiaryType: BeneficiaryType.Person,
		firstName: '',
		lastName: '',
		taxType: TaxIdType.SSN,
		taxId: '',
		addressLine1: '',
		addressLine2: '',
		city: '',
		state: '',
		zip: '',
		dob: '',
		allocationPercentage: 0,
		revocable: false
	}
}

function handleBeneficiariesUpdate(records: Beneficiary[]) {
	custodialInfo.value.beneficiaries = records
}

function addSigner() {
	if (!custodialInfo.value.signers) {
		custodialInfo.value.signers = []
	}
	custodialInfo.value.signers.push({ email: '', phoneNumber: '' })
}

function removeSigner(index: number) {
	custodialInfo.value.signers?.splice(index, 1)
}
</script>

<template>
	<div class="space-y-6">
		<!-- Owner Information -->
		<div class="grid grid-cols-3 gap-4">
			<FwbSelect
				v-model="custodialInfo.ownershipType"
				:options="ownershipTypeOptions"
				label="Custodial Owner is..."
			/>

			<template v-if="isPerson">
				<FwbInput v-model="custodialInfo.ownerFirstName" label="Custodial First Name" />
				<FwbInput v-model="custodialInfo.ownerLastName" label="Custodial Last Name" />
				<FwbInput v-model="custodialInfo.ownerSsn" label="Custodial SSN" />
			</template>

			<template v-else>
				<FwbInput v-model="custodialInfo.ownerEntityName" label="Custodial Name" />
				<FwbInput v-model="custodialInfo.ownerEntityBeneficiaryName" label="Beneficiary Name" />
				<FwbInput v-model="custodialInfo.brokerageNumber" label="Brokerage Number" />
			</template>
		</div>

		<div class="grid grid-cols-3 gap-4">
			<FwbInput v-model="custodialInfo.addressLine1" label="Address 1" />
			<FwbInput v-model="custodialInfo.addressLine2" label="Address 2" />
			<FwbInput v-model="custodialInfo.addressCity" label="City" />
			<FwbSelect
				v-model="custodialInfo.addressState"
				:options="[{ value: '', name: 'Select State' }]"
				label="State"
			/>
			<FwbInput v-model="custodialInfo.addressZip" label="Zip" />
		</div>

		<div>
			<p class="text-sm font-medium text-gray-700 mb-2">Transfer Documents</p>
			<p class="text-sm text-gray-500 mb-2">Transfer docs and beneficiary documents will be needed.</p>
			<div class="grid grid-cols-3 gap-4">
				<FwbSelect
					v-model="custodialInfo.signingOption"
					:options="signingOptions"
					label="E-sign or Wet-Sign"
				/>
			</div>
		</div>

		<!-- E Signature Details (shown for e-sign) -->
		<div v-if="custodialInfo.signingOption === SigningOption.ESign">
			<p class="text-sm font-medium text-gray-700 mb-2">E Signature Details</p>
			<div
				v-for="(signer, index) in custodialInfo.signers"
				:key="index"
				class="grid grid-cols-3 gap-4 mb-4"
			>
				<FwbInput v-model="signer.email" label="Client Email" />
				<FwbInput v-model="signer.phoneNumber" label="Client Cell Phone" />
				<div class="flex items-end">
					<FwbButton
						v-if="index > 0"
						color="red"
						size="sm"
						class="cursor-pointer"
						@click="removeSigner(index)"
					>
						Remove
					</FwbButton>
				</div>
			</div>
			<FwbButton color="default" size="sm" class="cursor-pointer" @click="addSigner">
				+ Add Owner
			</FwbButton>
		</div>

		<!-- Document Details (shown for wet-sign) -->
		<div v-if="custodialInfo.signingOption === SigningOption.WetSign">
			<p class="text-sm font-medium text-gray-700 mb-2">Document Details</p>
			<div class="flex gap-2">
				<FwbButton color="default" size="sm" class="cursor-pointer">
					Print Docs
				</FwbButton>
				<FwbButton color="light" size="sm" class="cursor-pointer">
					Upload Docs
				</FwbButton>
			</div>
		</div>

		<!-- Custodial Details -->
		<div class="grid grid-cols-3 gap-4">
			<FwbInput v-model="custodialInfo.existingCustodialName" label="Existing Custodial Name" />
			<FwbInput v-model="custodialInfo.existingCustodialEmail" label="Existing Custodial Email" />
			<FwbInput v-model="custodialInfo.existingCustodialCell" label="Existing Custodial Cell" />
			<FwbInput v-model="custodialInfo.acceptingCustodialName" label="Accepting Custodial Name" />
			<FwbInput v-model="custodialInfo.acceptingCustodialEmail" label="Accepting Custodial Email" />
			<FwbInput v-model="custodialInfo.acceptingCustodialCell" label="Accepting Custodial Cell" />
		</div>

		<!-- Beneficiaries (only for Person ownership) -->
		<div v-if="isPerson" class="mt-6">
			<FormTable
				:records="custodialInfo.beneficiaries ?? []"
				:columns="beneficiaryColumns"
				:create-record="createBeneficiary"
				title="Beneficiaries"
				@update="handleBeneficiariesUpdate"
			>
				<template #edit-form="{ record }">
					<div class="grid grid-cols-3 gap-4">
						<FwbSelect
							v-model="record.beneficiaryType"
							:options="beneficiaryTypeOptions"
							label="Beneficiary is..."
						/>
						<FwbInput v-model="record.firstName" label="Person First Name" />
						<FwbInput v-model="record.lastName" label="Person Last Name" />
						<FwbSelect
							v-model="record.taxType"
							:options="taxTypeOptions"
							label="Tax Qualifier"
						/>
						<FwbInput v-model="record.taxId" label="SSN" />
						<FwbInput v-model="record.addressLine1" label="Address 1" />
						<FwbInput v-model="record.addressLine2" label="Address 2" />
						<FwbInput v-model="record.city" label="City" />
						<FwbSelect
							v-model="record.state"
							:options="[{ value: '', name: 'Select State' }]"
							label="State"
						/>
						<FwbInput v-model="record.zip" label="Zip" />
						<FwbInput v-model="record.dob" label="Date of Birth" type="date" />
						<FwbInput
							v-model="record.allocationPercentage"
							label="Allocation %"
							type="number"
						/>
						<div class="flex items-center gap-4 pt-6">
							<FwbCheckbox v-model="record.revocable" label="Irrevocable?" />
						</div>
					</div>
				</template>
			</FormTable>
		</div>
	</div>
</template>
