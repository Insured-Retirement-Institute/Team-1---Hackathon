import type { PolicyError, WithdrawalStructure } from './ClearinghouseApi'

export enum ContractStatus {
	ProprietaryProduct = 'Proprietary Product',
	NotActive = 'Not Active',
	Unappointed = 'Unappointed',
	Inactive = 'Inactive',
	ActiveRestricted = 'Active - Restricted',
	Active = 'Active'
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
}
