import type {
	PolicyInquiryRequest,
	PolicyInquiryResponse,
	BdChangeRequest,
	CarrierResponse,
	TransferConfirmation,
	TransactionStatus,
	StandardResponse
} from '@/models/ClearinghouseApi'

const CLEARINGHOUSE_API = import.meta.env.VITE_CLEARINGHOUSE_API as string
const BROKER_DEALER_API = import.meta.env.VITE_BROKER_DEALER_API as string
const INSURANCE_CARRIER_API = import.meta.env.VITE_INSURANCE_CARRIER_API as string

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
	const response = await fetch(url, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options?.headers
		}
	})

	if (!response.ok) {
		throw new Error(`HTTP error! status: ${response.status}`)
	}

	return response.json() as Promise<T>
}

// Clearinghouse API endpoints
export const clearinghouseApi = {
	submitPolicyInquiryRequest: (
		transactionId: string,
		request: PolicyInquiryRequest
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/submit-policy-inquiry-request`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(request)
		}),

	submitPolicyInquiryResponse: (
		transactionId: string,
		response: PolicyInquiryResponse
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/submit-policy-inquiry-response`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(response)
		}),

	receiveBdChangeRequest: (
		transactionId: string,
		request: BdChangeRequest
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/receive-bd-change-request`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(request)
		}),

	receiveCarrierResponse: (
		transactionId: string,
		response: CarrierResponse
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/receive-carrier-response`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(response)
		}),

	receiveTransferConfirmation: (
		transactionId: string,
		confirmation: TransferConfirmation
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/receive-transfer-confirmation`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(confirmation)
		}),

	queryTransactionStatus: (transactionId: string): Promise<TransactionStatus> =>
		fetchJson(`${CLEARINGHOUSE_API}/query-status/${transactionId}`)
}

// Broker-Dealer API endpoints (for direct broker queries)
export const brokerDealerApi = {
	queryPolicies: (
		transactionId: string,
		request: PolicyInquiryRequest
	): Promise<PolicyInquiryResponse> =>
		fetchJson(`${BROKER_DEALER_API}/query-policies`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(request)
		})
}

// Insurance Carrier API endpoints (for direct carrier queries)
export const insuranceCarrierApi = {
	validatePolicies: (
		transactionId: string,
		request: { policies: string[] }
	): Promise<PolicyInquiryResponse> =>
		fetchJson(`${INSURANCE_CARRIER_API}/validate-policies`, {
			method: 'POST',
			headers: { transactionId },
			body: JSON.stringify(request)
		})
}
