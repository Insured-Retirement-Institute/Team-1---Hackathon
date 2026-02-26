export interface Request {
	requestId: string
	clientId: string
	clientName: string
	requestType: string
	status: string
	contracts: string[]
	receivingBrokerId: string
	deliveringBrokerId: string
	createdAt: string
	updatedAt: string
	pk: string
	sk: string
	type: string
}

// Backwards compatibility alias
export type Transaction = Request
