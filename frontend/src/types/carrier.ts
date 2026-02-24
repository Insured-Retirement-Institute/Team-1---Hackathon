export interface StatusHistoryItem {
  status: string
  timestamp: string
  notes?: string
}

export interface WithdrawalStructure {
  systematicInPlace: boolean
}

export interface PolicyError {
  errorCode: string
  message: string
}

export interface ValidationChecks {
  licensingCheck: string
  appointmentCheck: string
  suitabilityCheck: string
  policyRulesCheck: string
}

export interface CarrierValidationDetails {
  validationResult: string
  licensingCheck: string
  appointmentCheck: string
  suitabilityCheck: string
  policyRulesCheck: string
  validatedAt?: string
  rejectionReason?: string
}

export interface BdChangeRequest {
  pk: string
  sk: string
  transactionId: string
  policyNumber: string
  carrierId: string
  carrierName: string
  currentStatus: string
  statusHistory: StatusHistoryItem[]
  createdAt: string
  updatedAt: string
  clientName: string
  ssnLast4: string
  accountType: string
  planType: string
  ownership: string
  productName: string
  cusip: string
  trailingCommission: boolean
  contractStatus: string
  withdrawalStructure: WithdrawalStructure
  carrierValidationDetails?: CarrierValidationDetails
  errors: PolicyError[]
}

export type TransactionStatus =
  | 'MANIFEST_REQUESTED'
  | 'MANIFEST_RECEIVED'
  | 'DUE_DILIGENCE_COMPLETE'
  | 'CARRIER_VALIDATION_PENDING'
  | 'CARRIER_APPROVED'
  | 'CARRIER_REJECTED'
  | 'TRANSFER_INITIATED'
  | 'TRANSFER_PROCESSING'
  | 'TRANSFER_CONFIRMED'
  | 'COMPLETE'

export type CarrierTable = 'carrier' | 'carrier-2'

export type AccountType = 'individual' | 'joint' | 'trust' | 'custodial' | 'entity'

export type PlanType = 'nonQualified' | 'rothIra' | 'traditionalIra' | 'sep' | 'simple'
