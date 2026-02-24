// Enums
export enum ProducerErrorCode {
	NotAppointed = 'notAppointed',
	NotLicensed = 'notLicensed',
	AffiliationMismatch = 'affiliationMismatch'
}

export enum PolicyErrorCode {
	SsnContractMismatch = 'ssnContractMismatch',
	ProprietaryProduct = 'proprietaryProduct',
	PolicyInactive = 'policyInactive',
	PolicyRestricted = 'policyRestricted'
}

export enum ApiAccountType {
	Individual = 'individual',
	Joint = 'joint',
	Trust = 'trust',
	Custodial = 'custodial',
	Entity = 'entity'
}

export enum ApiPlanType {
	NonQualified = 'nonQualified',
	RothIra = 'rothIra',
	TraditionalIra = 'traditionalIra',
	Sep = 'sep',
	Simple = 'simple'
}

export enum ValidationResult {
	Approved = 'approved',
	Rejected = 'rejected'
}

export enum ConfirmationStatus {
	Confirmed = 'confirmed',
	Failed = 'failed'
}

export enum ResponseType {
	Immediate = 'immediate',
	Deferred = 'deferred'
}

export enum TransactionStatusValue {
	ManifestRequested = 'MANIFEST_REQUESTED',
	ManifestReceived = 'MANIFEST_RECEIVED',
	DueDiligenceComplete = 'DUE_DILIGENCE_COMPLETE',
	CarrierValidationPending = 'CARRIER_VALIDATION_PENDING',
	CarrierApproved = 'CARRIER_APPROVED',
	CarrierRejected = 'CARRIER_REJECTED',
	TransferInitiated = 'TRANSFER_INITIATED',
	TransferProcessing = 'TRANSFER_PROCESSING',
	TransferConfirmed = 'TRANSFER_CONFIRMED',
	Complete = 'COMPLETE'
}

export enum BrokerRole {
	Receiving = 'receiving',
	Delivering = 'delivering'
}

// Error types
export interface ProducerError {
	errorCode: ProducerErrorCode
	message: string
}

export interface PolicyError {
	errorCode: PolicyErrorCode
	message: string
}

// Withdrawal structure
export interface WithdrawalStructure {
	systematicInPlace: boolean
}

// Detailed policy info (from DTCC/carrier)
export interface DetailedPolicyInfo {
	policyNumber: string | null
	carrierName: string | null
	accountType: ApiAccountType | null
	planType: ApiPlanType | null
	ownership: string | null
	productName: string | null
	cusip: string | null
	trailingCommission: boolean
	contractStatus: string | null
	withdrawalStructure: WithdrawalStructure
	errors: PolicyError[]
}

// Servicing agent
export interface ServicingAgent {
	agentName: string | null
	npn: string | null
}

// Requesting firm
export interface RequestingFirm {
	firmName: string | null
	firmId: string | null
	servicingAgent: ServicingAgent
}

// Client info for request
export interface ClientRequest {
	clientName: string | null
	ssn: string | null
	policyNumbers: string[]
}

// Client info for response
export interface ClientResponse {
	clientName: string | null
	ssnLast4: string | null
	policies: DetailedPolicyInfo[]
}

// Producer validation
export interface ProducerValidation {
	agentName: string | null
	npn: string | null
	errors: ProducerError[]
}

// Enum references in response
export interface EnumReferences {
	accountType: ApiAccountType[]
	planType: ApiPlanType[]
}

// Policy Inquiry Request
export interface PolicyInquiryRequest {
	requestingFirm: RequestingFirm
	client: ClientRequest
}

// Policy Inquiry Response
export interface PolicyInquiryResponse {
	requestingFirm: RequestingFirm
	producerValidation: ProducerValidation
	client: ClientResponse
	enums: EnumReferences
}

// Policy details
export interface PolicyDetails {
	'policy-id': string
	'policy-type'?: string
	'policy-data'?: Record<string, unknown>
}

// Manifest Response
export interface ManifestResponse {
	'transaction-id': string
	'delivering-broker-id': string
	'response-type': ResponseType
	policies?: PolicyDetails[]
	'additional-data'?: Record<string, unknown>
}

// BD Change Request
export interface BdChangeRequest {
	'transaction-id': string
	'receiving-broker-id': string
	'delivering-broker-id': string
	'carrier-id': string
	'policy-id': string
	'policy-details'?: Record<string, unknown>
	'broker-details'?: Record<string, unknown>
	'validation-requirements'?: Record<string, unknown>
	'request-timestamp'?: string
	'validation-result'?: ValidationResult
	'rejection-reason'?: string
	'approval-details'?: Record<string, unknown>
	'response-timestamp'?: string
	'additional-data'?: Record<string, unknown>
}

// Carrier Response
export interface CarrierResponse {
	'transaction-id': string
	'carrier-id': string
	'policy-id': string
	'validation-result': ValidationResult
	'rejection-reason'?: string
	'additional-data'?: Record<string, unknown>
}

// Transfer Confirmation
export interface TransferConfirmation {
	'transaction-id': string
	'delivering-broker-id': string
	'policy-id': string
	'confirmation-status': ConfirmationStatus
	'additional-data'?: Record<string, unknown>
}

// Status history item
export interface StatusHistoryItem {
	status: string
	timestamp: string
	notes?: string
}

// Transaction status
export interface TransactionStatus {
	'transaction-id': string
	'current-status': TransactionStatusValue
	'status-history'?: StatusHistoryItem[]
	'created-at': string
	'updated-at': string
	'broker-role'?: BrokerRole
	'carrier-validation-details'?: Record<string, unknown>
	'policies-affected'?: string[]
	'additional-data'?: Record<string, unknown>
}

// Standard response
export interface StandardResponse {
	code: string
	message: string
	transactionId: string
	payload?: Record<string, unknown> | null
}

// Error response
export interface ErrorResponse {
	code: string
	message: string
}
