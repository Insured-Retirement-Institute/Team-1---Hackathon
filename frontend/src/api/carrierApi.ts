import type { BdChangeRequest, CarrierTable, StatusHistoryItem } from '@/types/carrier'
import { ulid } from 'ulid'

// API base URL - set via environment variable for production
const API_BASE_URL = import.meta.env.VITE_CARRIER_API_URL || ''

// Helper function to get random array element with type safety
function getRandomElement<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)] as T
}

// Generate random NPN
function generateNpn(): string {
  return Array.from({ length: 8 }, () => Math.floor(Math.random() * 10)).join('')
}

// Carrier configuration matching API specs and DynamoDB data
const CARRIER_CONFIG: Record<CarrierTable, { carrierId: string; carrierName: string; policyPrefix: string }> = {
  'carrier': {
    carrierId: 'athene',
    carrierName: 'Athene',
    policyPrefix: 'ATH'
  },
  'carrier-2': {
    carrierId: 'pacific-life',
    carrierName: 'Pacific Life',
    policyPrefix: 'PAC'
  }
}

// Mock data matching the Policy Inquiry API and Insurance Carrier API specs
const generateMockData = (tableId: CarrierTable): BdChangeRequest[] => {
  const config = CARRIER_CONFIG[tableId]

  const products: Record<CarrierTable, string[]> = {
    'carrier': [
      'Athene Accumulator 7',
      'Athene Agility 10',
      'Athene Amplify 3.0',
      'Athene MaxRate 3',
      'Athene MYG 4 ROP',
      'Athene MYG 5 MVA',
      'Athene MYG 6',
    ],
    'carrier-2': [
      'Pacific Protective Growth',
      'Pacific Index Income',
      'Pacific Index Foundation 2',
      'Pacific Index Edge',
      'Pacific Index Advisory',
      'Pacific Index Foundation',
      'Pacific Income Provider',
      'Pacific Secure Income',
      'Pacific Expedition 2',
    ]
  }

  const clients = [
    { name: 'John Smith', ssn: '6789' },
    { name: 'Mary Johnson', ssn: '4321' },
    { name: 'Robert Williams', ssn: '5555' },
    { name: 'Patricia Brown', ssn: '1234' },
    { name: 'Michael Davis', ssn: '9876' },
    { name: 'Jennifer Garcia', ssn: '2468' },
    { name: 'David Martinez', ssn: '1357' },
    { name: 'Linda Wilson', ssn: '8642' },
  ] as const

  const agentFirstNames = ['Brian', 'Stephanie', 'Kevin', 'Amanda', 'Jason', 'Nicole', 'Ryan', 'Melissa']
  const agentLastNames = ['Adams', 'Baker', 'Campbell', 'Douglas', 'Edwards', 'Foster', 'Graham', 'Hayes']

  const statuses = [
    'MANIFEST_REQUESTED',
    'MANIFEST_RECEIVED',
    'DUE_DILIGENCE_COMPLETE',
    'CARRIER_VALIDATION_PENDING',
    'CARRIER_APPROVED',
    'CARRIER_REJECTED',
    'TRANSFER_INITIATED',
    'TRANSFER_PROCESSING',
    'TRANSFER_CONFIRMED',
    'COMPLETE',
  ] as const

  const accountTypes = ['individual', 'joint', 'trust', 'custodial', 'entity'] as const
  const planTypes = ['nonQualified', 'rothIra', 'traditionalIra', 'sep', 'simple'] as const
  const ownershipTypes = ['single', 'joint', 'trust', 'corporate'] as const
  const contractStatuses = ['active', 'surrendered', 'matured', 'lapsed', 'pending'] as const

  const startPolicyNum = tableId === 'carrier' ? 100001 : 200001
  const records: BdChangeRequest[] = []

  for (let i = 0; i < 10; i++) {
    const policyNum = startPolicyNum + i
    const clientIdx = i % clients.length
    const client = clients[clientIdx]!
    const statusIdx = Math.floor(Math.random() * statuses.length)
    const status = statuses[statusIdx]!
    const isRejected = status === 'CARRIER_REJECTED'
    const contractStatus = isRejected ? getRandomElement([...contractStatuses]) : 'active'

    const statusHistory: StatusHistoryItem[] = []
    const baseTime = new Date()
    baseTime.setDate(baseTime.getDate() - Math.floor(Math.random() * 30))

    for (let j = 0; j <= statusIdx; j++) {
      const historyTime = new Date(baseTime.getTime() + j * 3600000 * (1 + Math.random() * 3))
      const historyStatus = statuses[j]!
      statusHistory.push({
        status: historyStatus,
        timestamp: historyTime.toISOString(),
        notes: j === statusIdx && status === 'CARRIER_REJECTED' ? 'Producer not appointed with carrier' : undefined
      })
    }

    const agentFirst = getRandomElement([...agentFirstNames])
    const agentLast = getRandomElement([...agentLastNames])

    const record: BdChangeRequest = {
      pk: `POLICY#${config.policyPrefix}-${policyNum}`,
      sk: `REQUEST#${ulid()}`,
      requestId: ulid(),
      policyNumber: `${config.policyPrefix}-${policyNum}`,
      carrierId: config.carrierId,
      carrierName: config.carrierName,
      currentStatus: status,
      statusHistory,
      createdAt: baseTime.toISOString(),
      updatedAt: new Date().toISOString(),
      clientName: client.name,
      ssnLast4: client.ssn,
      servicingAgent: {
        agentName: `${agentFirst} ${agentLast}`,
        npn: generateNpn()
      },
      accountType: getRandomElement([...accountTypes]),
      planType: getRandomElement([...planTypes]),
      ownership: getRandomElement([...ownershipTypes]),
      productName: getRandomElement([...products[tableId]]),
      cusip: Math.random().toString(36).substring(2, 11).toUpperCase(),
      trailingCommission: Math.random() > 0.5,
      contractStatus: contractStatus,
      withdrawalStructure: {
        systematicInPlace: Math.random() > 0.75
      },
      errors: []
    }

    // Add validation details if past validation stage
    const validationStatuses = ['CARRIER_APPROVED', 'CARRIER_REJECTED', 'TRANSFER_INITIATED', 'TRANSFER_PROCESSING', 'TRANSFER_CONFIRMED', 'COMPLETE']
    if (validationStatuses.includes(status)) {
      const lastHistoryItem = statusHistory[statusHistory.length - 1]
      record.carrierValidationDetails = {
        validationResult: isRejected ? 'rejected' : 'approved',
        licensingCheck: isRejected && Math.random() > 0.5 ? 'failed' : 'passed',
        appointmentCheck: isRejected && Math.random() > 0.5 ? 'failed' : 'passed',
        suitabilityCheck: 'passed',
        policyRulesCheck: isRejected && Math.random() > 0.5 ? 'failed' : 'passed',
        validatedAt: lastHistoryItem?.timestamp,
        rejectionReason: isRejected ? 'Producer is not appointed with carrier' : undefined
      }
    }

    if (isRejected) {
      record.errors.push({
        errorCode: 'notAppointed',
        message: 'Producer is not appointed with carrier'
      })
    } else if (contractStatus !== 'active') {
      record.errors.push({
        errorCode: 'policyInactive',
        message: `Policy is ${contractStatus}`
      })
    }

    records.push(record)
  }

  return records
}

// Cache for mock data
let carrierCache: BdChangeRequest[] | null = null
let carrier2Cache: BdChangeRequest[] | null = null

async function fetchFromApi(table: CarrierTable): Promise<BdChangeRequest[]> {
  const response = await fetch(`${API_BASE_URL}/carrier/${table}`)
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
  }
  return response.json()
}

export async function fetchCarrierRequests(table: CarrierTable = 'carrier'): Promise<BdChangeRequest[]> {
  // If API URL is configured, use the real API
  if (API_BASE_URL) {
    try {
      return await fetchFromApi(table)
    } catch (error) {
      console.warn('API fetch failed, falling back to mock data:', error)
    }
  }

  // Use mock data (cached for consistency during session)
  if (table === 'carrier') {
    if (!carrierCache) {
      carrierCache = generateMockData('carrier')
    }
    return carrierCache
  } else {
    if (!carrier2Cache) {
      carrier2Cache = generateMockData('carrier-2')
    }
    return carrier2Cache
  }
}

export async function fetchCarrierRequestById(
  requestId: string,
  table: CarrierTable = 'carrier'
): Promise<BdChangeRequest | null> {
  const data = await fetchCarrierRequests(table)
  return data.find(r => r.requestId === requestId) || null
}
