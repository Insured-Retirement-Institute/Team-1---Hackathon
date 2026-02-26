export interface Contract {
	policyNumber: string
	clientId: string
	carrierId: string
	carrierName: string
	productType: string
	productName: string
	planType: string
	status: string
	contractStatus?: string
	cusip: string
	issueState: string
	hasSystematicWithdrawal: boolean
	hasTrailingCommission: boolean
	pk: string
	sk: string
	type: string
	accountType?: string
}
