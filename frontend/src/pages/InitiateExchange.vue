<script setup lang="ts">
import { FwbButton, FwbHeading, FwbInput } from 'flowbite-vue';
import BarcodeIcon from '@/icons/BarcodeIcon.svg'
import UserIcon from '@/icons/UserIcon.svg'
import ProfileCardIcon from '@/icons/ProfileCardIcon.svg'
import CloseIcon from '@/icons/CloseIcon.svg'
import UploadIcon from '@/icons/UploadIcon.svg'
import CirclePlusIcon from '@/icons/CirclePlusIcon.svg'
import { useContractResultsStore } from '@/stores/useContractResultsStore';
import { storeToRefs } from 'pinia';
import { useFileDialog } from '@vueuse/core';
import { useLoaderStore } from '@/stores/useLoaderStore';
import { brokerDealerApi } from '@/api/Api';
import { monotonicFactory } from 'ulid';
import { fileToBase64 } from '@/utils/fileUtils';
import { useClientStore } from '@/stores/useClientStore';
import { ref } from 'vue';
import type { PolicyInquiryResponse } from '@/models/ClearinghouseApi';

const ulid = monotonicFactory()

const props = defineProps<{
	clientId?: string
}>()

const clientStore = useClientStore()

const client = clientStore.clients.find(c => c.clientId === props.clientId)

const contractResultsStore = useContractResultsStore()

const { searchContracts, clientSearch } = storeToRefs(contractResultsStore)

if (client) {
	clientSearch.value = client
}

if (searchContracts.value.length === 0) {
	contractResultsStore.addSearchContract()
}

const { open, onChange } = useFileDialog({
	accept: 'application/pdf',
	multiple: false
})

onChange(async files => {
	if (!files || files.length === 0) return

	const file = files[0]
	if (!file) return

	const loader = useLoaderStore()
	loader.open('Processing Document')

	try {
		const pdfBase64 = await fileToBase64(file)

		const response = await brokerDealerApi.extractPolicyFromPdf({
			requestId: ulid(),
			pdfBase64
		})

		console.log('PDF extraction response:', response)

		const contractNumbers = ((response.payload as any).policyInquiryResponse as PolicyInquiryResponse).client.policies.map(p => p.policyNumber)

		searchContracts.value = []

		contractNumbers.forEach(c => contractResultsStore.addSearchContract({ contractNumber: c ?? '' }))

	} catch (error) {
		console.error('PDF extraction failed:', error)
	} finally {
		loader.close()
	}
})
</script>

<template>
	<div class="w-full">
		<div class="p-10 bg-[#f8f8f8] rounded-xl mb-4">
			<div class="flex items-center justify-end">
				<FwbButton class="cursor-pointer" @click="open">
					<div class="flex items-center gap-2">
						<UploadIcon />
						I have existing contract documents
					</div>
				</FwbButton>
			</div>
			<div class="flex flex-wrap *:p-4 items-center">
				<div class="w-1/3">
					<FwbInput v-model="clientSearch.clientName" label="Client Name" :disabled="!!clientId">
						<template #prefix>
							<UserIcon />
						</template>
					</FwbInput>
				</div>

				<div class="w-1/3">
					<FwbInput v-model="clientSearch.ssnLast4" label="SSN" :disabled="!!clientId">
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
