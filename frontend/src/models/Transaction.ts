export interface Transaction {
	requestId: string
	clientId: string
	clientName: string
	transactionType: string
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
