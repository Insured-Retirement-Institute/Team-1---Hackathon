import type { Todo } from "@/models/Todo";
import type {
	PolicyInquiryRequest,
	PolicyInquiryResponse,
	BdChangeRequest,
	CarrierResponse,
	TransferConfirmation,
	TransferNotification,
	TransactionStatus,
	StandardResponse,
	PdfExtractionRequest,
	CarrierLetterRequest
} from '@/models/ClearinghouseApi'
import { monotonicFactory } from "ulid";
import type { Client } from "@/models/Client";
import type { Transaction as Request } from "@/models/Transaction";

const ulid = monotonicFactory()


async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
	const response = await fetch(url, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			requestId: ulid(),
			blobs: ulid(),
			...options?.headers
		}
	})

	if (!response.ok) {
		throw new Error(`HTTP error! status: ${response.status}`)
	}

	return response.json() as Promise<T>
}

async function fetchJsonSimple<T>(url: string, options?: RequestInit): Promise<T> {
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

export const test = () => fetch('/api/todos')
	.then(response => response.json() as Promise<Todo[]>)

export const awsTest = () => fetch('https://q4wbter4btlhos5jz2nm2u53ye0khura.lambda-url.us-east-1.on.aws/health')
	.then(res => res.json())

const CLEARINGHOUSE_API = import.meta.env.VITE_CLEARINGHOUSE_API as string
const BROKER_DEALER_API = import.meta.env.VITE_BROKER_DEALER_API as string
const INSURANCE_CARRIER_API = import.meta.env.VITE_INSURANCE_CARRIER_API as string
const EVENTSOURCE_API = import.meta.env.VITE_EVENTSOURCE as string
const DISTRIBUTOR_API = import.meta.env.VITE_DISTRIBUTOR_API as string

export const checkBrokerDealerHealth = () => fetch(`${BROKER_DEALER_API}/health`)
export const checkClearingHouseHealth = () => fetch(`${CLEARINGHOUSE_API}/health`)
export const checkCarrierHealth = () => fetch(`${INSURANCE_CARRIER_API}/health`)
export const checkEventSourceHealth = () => fetch(`${EVENTSOURCE_API}/health`)
export const checkDistributorHealth = () => fetch(`${DISTRIBUTOR_API}/`)

// Clearinghouse API endpoints
export const clearinghouseApi = {
	triggerPolicyInquiryRequest: (
		request: PolicyInquiryRequest
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/trigger-policy-inquiry`, {
			method: 'POST',
			body: JSON.stringify(request)
		}),

	submitPolicyInquiryResponse: (
		response: PolicyInquiryResponse
	): Promise<StandardResponse> =>
		fetchJson(`${CLEARINGHOUSE_API}/submit-policy-inquiry-response`, {
			method: 'POST',
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
		}),

	triggerPolicyInquiry: (
		request: PolicyInquiryRequest
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/trigger-policy-inquiry`, {
			method: 'POST',
			body: JSON.stringify(request)
		}),

	receivePolicyInquiryResponse: (
		response: PolicyInquiryResponse
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/receive-policy-inquiry-response`, {
			method: 'POST',
			body: JSON.stringify(response)
		}),

	receiveBdChangeRequest: (
		request: BdChangeRequest
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/receive-bd-change-request`, {
			method: 'POST',
			body: JSON.stringify(request)
		}),

	receiveTransferNotification: (
		notification: TransferNotification
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/receive-transfer-notification`, {
			method: 'POST',
			body: JSON.stringify(notification)
		}),

	queryTransactionStatus: (transactionId: string): Promise<TransactionStatus> =>
		fetchJson(`${BROKER_DEALER_API}/query-status/${transactionId}`),

	extractPolicyFromPdf: (
		request: PdfExtractionRequest
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/extract-policy-from-pdf`, {
			method: 'POST',
			body: JSON.stringify(request)
		}),

	generateCarrierLetter: (
		request: CarrierLetterRequest
	): Promise<StandardResponse> =>
		fetchJson(`${BROKER_DEALER_API}/generate-carrier-letter`, {
			method: 'POST',
			body: JSON.stringify(request)
		})
}

// Insurance Carrier API endpoints (for direct carrier queries)
export const insuranceCarrierApi = {
	validatePolicies: (
		request: { policies: string[] }
	): Promise<PolicyInquiryResponse> =>
		fetchJson(`${INSURANCE_CARRIER_API}/validate-policies`, {
			method: 'POST',
			body: JSON.stringify(request)
		}),

	// Direct carrier access (bypassing clearinghouse)
	submitPolicyInquiryRequest: (
		request: PolicyInquiryRequest
	): Promise<StandardResponse> =>
		fetchJson(`${INSURANCE_CARRIER_API}/submit-policy-inquiry-request`, {
			method: 'POST',
			body: JSON.stringify(request)
		})
}

// Distributor API endpoints
export const distributorApi = {
	getAgentProfile: <T = unknown>(npn: string): Promise<T> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/agent/${npn}`),

	getAgentClients: (npn: string): Promise<{ clients: Client[] }> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/agent/${npn}/clients`),

	getAgentRequests: (npn: string): Promise<{ requests: Request[] }> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/agent/${npn}/requests`),

	createRequest: (npn: string, transaction: Partial<Request>): Promise<{ request: Request }> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/agent/${npn}/requests`, {
			method: 'POST',
			body: JSON.stringify({
				...transaction,
				requestType: 'BD_CHANGE'
			})
		}),

	getClientProfile: <T = unknown>(clientId: string): Promise<T> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/client/${clientId}`),

	createClient: (client: Partial<Client>): Promise<unknown> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/agent/12345678/clients`, {
			method: 'POST',
			body: JSON.stringify(client)
		}),

	getClientContracts: <T = unknown>(clientId: string): Promise<T> =>
		fetchJsonSimple(`${DISTRIBUTOR_API}/client/${clientId}/contracts`)
}
