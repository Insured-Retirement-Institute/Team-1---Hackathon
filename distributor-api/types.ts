/**
 * Distributor API TypeScript Types
 * Base URL: https://8mmrxe8ug1.execute-api.us-east-1.amazonaws.com/Prod
 */

// ============================================================================
// Base Types
// ============================================================================

export interface Agent {
  pk: string;                  // "AGENT#{npn}"
  sk: string;                  // "PROFILE"
  type: "Agent";
  npn: string;
  agentName: string;
  firmId: string;
  firmName: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  createdAt: string;           // ISO 8601
}

export interface Client {
  pk: string;                  // "CLIENT#{clientId}"
  sk: string;                  // "PROFILE"
  type: "Client";
  clientId: string;
  clientName: string;
  ssnLast4: string;
  createdAt: string;           // ISO 8601
}

export interface AgentClient {
  pk: string;                  // "AGENT#{npn}"
  sk: string;                  // "CLIENT#{clientId}"
  type: "AgentClient";
  clientId: string;
  clientName: string;
  ssnLast4: string;
  assignedAt: string;          // ISO 8601
}

export interface Contract {
  pk: string;                  // "CLIENT#{clientId}"
  sk: string;                  // "CONTRACT#{policyNumber}"
  type: "Contract";
  clientId: string;
  policyNumber: string;
  carrierName: string;
  carrierId: string;           // "ATH1" | "PAC1" | "PRU1"
  productName: string;
  productType: string;
  planType: string;            // "IRA" | "Roth IRA" | "Non-Qualified" | etc.
  cusip: string;
  issueState: string;
  status: "Active" | "Surrendered" | "Death Claim Pending";
  systematicWithdrawal: boolean;
  commissionTrails: boolean;
}

export type RequestStatus =
  | "MANIFEST_REQUESTED"
  | "MANIFEST_RECEIVED"
  | "DUE_DILIGENCE_COMPLETE"
  | "CARRIER_VALIDATION_PENDING"
  | "CARRIER_APPROVED"
  | "CARRIER_REJECTED"
  | "TRANSFER_INITIATED"
  | "TRANSFER_PROCESSING"
  | "TRANSFER_CONFIRMED"
  | "COMPLETE";

export interface Request {
  pk: string;                  // "AGENT#{npn}"
  sk: string;                  // "REQUEST#{requestId}"
  type: "Request";
  requestId: string;
  clientId: string;
  clientName: string;
  contracts: string[];         // Array of policy numbers
  requestType: "BD_CHANGE";
  status: RequestStatus;
  receivingBrokerId: string;
  deliveringBrokerId: string;
  createdAt: string;           // ISO 8601
  updatedAt: string;           // ISO 8601
}

// ============================================================================
// API Response Types
// ============================================================================

/** GET / */
export interface HealthResponse {
  status: "healthy";
  service: "distributor-api";
}

/** GET /agent/{npn} */
export type GetAgentResponse = Agent;

/** GET /agent/{npn}/clients */
export interface GetAgentClientsResponse {
  clients: AgentClient[];
  count: number;
}

/** GET /agent/{npn}/requests */
export interface GetAgentRequestsResponse {
  requests: Request[];
  count: number;
}

/** GET /client/{clientId} */
export type GetClientResponse = Client;

/** GET /client/{clientId}/contracts */
export interface GetClientContractsResponse {
  contracts: Contract[];
  count: number;
}

// ============================================================================
// API Request Types
// ============================================================================

/** POST /agent/{npn}/clients */
export interface CreateClientRequest {
  clientName: string;
  ssnLast4: string;
}

/** POST /agent/{npn}/clients - Response */
export interface CreateClientResponse {
  message: string;
  client: Client;
}

/** POST /agent/{npn}/requests */
export interface CreateRequestRequest {
  clientId: string;
  contracts: string[];         // Array of policy numbers to include
  receivingBrokerId: string;
  requestType?: "BD_CHANGE";
}

/** POST /agent/{npn}/requests - Response */
export interface CreateRequestResponse {
  message: string;
  request: Request;
}

// ============================================================================
// Error Response
// ============================================================================

export interface ErrorResponse {
  error: string;
}

// ============================================================================
// API Client Helper Types
// ============================================================================

export interface DistributorApiEndpoints {
  /** GET / */
  health: () => Promise<HealthResponse>;

  /** GET /agent/{npn} */
  getAgent: (npn: string) => Promise<GetAgentResponse>;

  /** GET /agent/{npn}/clients */
  getAgentClients: (npn: string) => Promise<GetAgentClientsResponse>;

  /** POST /agent/{npn}/clients */
  createClient: (npn: string, request: CreateClientRequest) => Promise<CreateClientResponse>;

  /** GET /agent/{npn}/requests */
  getAgentRequests: (npn: string) => Promise<GetAgentRequestsResponse>;

  /** GET /client/{clientId} */
  getClient: (clientId: string) => Promise<GetClientResponse>;

  /** GET /client/{clientId}/contracts */
  getClientContracts: (clientId: string) => Promise<GetClientContractsResponse>;

  /** POST /agent/{npn}/requests */
  createRequest: (npn: string, request: CreateRequestRequest) => Promise<CreateRequestResponse>;
}
