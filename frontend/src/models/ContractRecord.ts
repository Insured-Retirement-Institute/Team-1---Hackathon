import type { PolicyError, WithdrawalStructure } from './ClearinghouseApi'

export enum ContractStatus {
	Active = 'Active',
	Inactive = 'Inactive',
	DistributionSpecific = 'Distribution Specific',
	FullWithdrawalPending = 'Full Withdrawal Pending',
	CarrierPending = 'Carrier Pending',
	CarrierSpecific = 'Carrier Specific',
	ActiveRestricted = 'Active - Restricted',
	OwnershipIssue = 'Ownership Issue',
	NotLicensed = 'Not Licensed',
	Unappointed = 'Unappointed'
}

export enum PlanType {
	NonQualified = 'Non Qualified',
	RothIRA = 'Roth IRA',
	TraditionalIRA = 'Traditional IRA',
	SepIRA = 'Sep IRA',
	SimpleIRA = 'Simple IRA'
}

export enum AccountType {
	Individual = 'Individual Account',
	JointOwned = 'Joint Owned Account',
	Trust = 'Trust Account',
	Entity = 'Entity Account'
}

export enum OwnershipType {
	Individual = 'Individual',
	JointOwned = 'Joint Owned',
	TrustOwned = 'Trust Owned',
	EntityOwned = 'Entity Owned',
	Custodial = 'Custodial',
	JointOwnedAccount = 'Joint Owned Account',
	TrustAccount = 'Trust Account',
	EntityAccount = 'Entity Account'
}

export enum CustodialOwnershipType {
	Person = 'A Person',
	Entity = 'An Entity'
}

export enum SigningOption {
	ESign = 'e-sign',
	WetSign = 'wetsign'
}

export interface Signer {
	email: string
	phoneNumber: string
}

export enum BeneficiaryType {
	Person = 'A Person',
	Trust = 'A Trust'
}

export enum TaxIdType {
	TIN = 'TIN',
	SSN = 'SSN'
}

export interface Beneficiary {
	id: string
	beneficiaryType?: BeneficiaryType
	firstName?: string
	lastName?: string
	taxType?: TaxIdType
	taxId?: string
	addressLine1?: string
	addressLine2?: string
	city?: string
	state?: string
	zip?: string
	dob?: string
	allocationPercentage?: number
	revocable?: boolean
}

export interface CustodialInfo {
	ownershipType?: CustodialOwnershipType
	ownerFirstName?: string
	ownerLastName?: string
	ownerEntityName?: string
	ownerEntityBeneficiaryName?: string
	ownerSsn?: string
	addressLine1?: string
	addressLine2?: string
	addressCity?: string
	addressState?: string
	addressZip?: string
	brokerageNumber?: string
	signingOption?: SigningOption
	existingCustodialFirstName?: string
	existingCustodialLastName?: string
	existingCustodialName?: string
	existingCustodialEmail?: string
	existingCustodialCell?: string
	existingCustodialAddressLine1?: string
	existingCustodialAddressLine2?: string
	existingCustodialCity?: string
	existingCustodialState?: string
	existingCustodialZip?: string
	acceptingCustodialFirstName?: string
	acceptingCustodialLastName?: string
	acceptingCustodialName?: string
	acceptingCustodialEmail?: string
	acceptingCustodialCell?: string
	acceptingCustodialAddressLine1?: string
	acceptingCustodialAddressLine2?: string
	acceptingCustodialCity?: string
	acceptingCustodialState?: string
	acceptingCustodialZip?: string
	documentData?: string
	signers?: Signer[]
	beneficiaries?: Beneficiary[]
}

// ContractRecord is a superset of DetailedPolicyInfo from the API
export interface ContractRecord {
	// Internal fields
	id: string | number
	selected?: boolean
	dtccResolved?: boolean

	// Maps to DetailedPolicyInfo.policyNumber
	contractNumber: string

	// Direct mappings from DetailedPolicyInfo
	carrierName: string
	productName: string
	cusipNumber: string // Maps to DetailedPolicyInfo.cusip
	ownership: OwnershipType | string
	planType?: PlanType
	accountType?: AccountType
	trailing: boolean // Maps to DetailedPolicyInfo.trailingCommission
	contractStatus: ContractStatus
	withdrawalProgram: boolean // Maps to DetailedPolicyInfo.withdrawalStructure.systematicInPlace

	// Additional fields from DetailedPolicyInfo
	withdrawalStructure?: WithdrawalStructure
	errors?: PolicyError[]

	// Extended fields not in DetailedPolicyInfo
	ownerName?: string
	custodialInfo?: CustodialInfo
	effectiveDate?: string
}
