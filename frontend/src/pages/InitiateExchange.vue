<script setup lang="ts">
import { FwbButton, FwbHeading, FwbInput } from 'flowbite-vue';
import BarcodeIcon from '@/icons/BarcodeIcon.svg'
import UserIcon from '@/icons/UserIcon.svg'
import ProfileCardIcon from '@/icons/ProfileCardIcon.svg'
import CloseIcon from '@/icons/CloseIcon.svg'
import CirclePlusIcon from '@/icons/CirclePlusIcon.svg'
import { useContractResultsStore } from '@/stores/useContractResultsStore';
import { storeToRefs } from 'pinia';

const contractResultsStore = useContractResultsStore()

const { searchContracts, clientSearch } = storeToRefs(contractResultsStore)

if (searchContracts.value.length === 0) {
	contractResultsStore.addSearchContract()
}
</script>

<template>
	<div class="w-full">

		<div class="p-10 bg-[#f8f8f8] rounded-xl mb-4">
			<div class="flex flex-wrap *:p-4 items-center">
				<div class="w-1/3">
					<FwbInput v-model="clientSearch.firstName" label="First Name">
						<template #prefix>
							<UserIcon />
						</template>
					</FwbInput>
				</div>

				<div class="w-1/3">
					<FwbInput v-model="clientSearch.lastName" label="Last Name">
						<template #prefix>
							<UserIcon />
						</template>
					</FwbInput>
				</div>

				<div class="w-1/3">
					<FwbInput v-model="clientSearch.ssn" label="SSN">
						<template #prefix>
							<ProfileCardIcon />
						</template>
					</FwbInput>
				</div>

				<div v-for="contract in searchContracts" :key="contract.id" class="w-1/3">
					<FwbInput v-model="contract.contractNumber" label="Contract Number">
						<template #prefix>
							<BarcodeIcon />
						</template>

						<template #suffix>
							<button class="cursor-pointer" @click="contractResultsStore.removeSearchContract(contract.id)"><CloseIcon /></button>
						</template>
					</FwbInput>
				</div>


			</div>

			<div class="p-4">
				<div class="w-1/3">
					<FwbButton color="default" @click="contractResultsStore.addSearchContract" class="cursor-pointer">
						<div class="flex items-center gap-2 ">
							<CirclePlusIcon />
							Add Additional Contract
						</div>
					</FwbButton>
				</div>
			</div>
		</div>
	</div>
</template>
