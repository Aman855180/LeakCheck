export interface User {
  id: string;
  email: string;
  role: 'finance_exec' | 'cofounder';
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  csrf_token: string;
  user: User;
}

export interface RateCard {
  id: string;
  partner_id: string;
  channel: string;
  rule_type: string;
  params_json: Record<string, any>;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Source {
  id: string;
  partner_id: string;
  source_type: 'orders' | 'settlement' | 'cod' | 'freight' | 'receipts';
  name: string;
  file_format: string;
  is_active: boolean;
}

export interface Upload {
  id: string;
  source_id: string;
  partner_id: string;
  source_type: string;
  file_name: string;
  file_hash: string;
  file_size_bytes: number;
  row_count: number;
  mapping_version: number | null;
  processing_status: 'uploaded' | 'mapping_pending' | 'processing' | 'completed' | 'failed';
  error_count: number;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface UploadPreview {
  type: 'preview' | 'completed';
  upload_id: string;
  file_name: string;
  source_type: string;
  total_rows: number;
  detected_columns: string[];
  dropped_pii_columns: string[];
  preview_rows: Record<string, any>[];
  suggested_mapping: Record<string, { column: string | null; confidence: number; match_type: string }>;
  missing_required: string[];
  canonical_fields: { key: string; display_name: string; required_for: string[]; description: string }[];
  upload: Upload;
  summary?: any;
}

export interface UploadRowError {
  id: string;
  upload_id: string;
  source_row_number: number;
  error_code: string;
  error_message: string;
  raw_record: Record<string, any>;
  created_at: string;
}

export interface ColumnMapping {
  id: string;
  source_id: string;
  version: number;
  mapping_json: Record<string, string>;
  status: 'suggested' | 'approved' | 'superseded' | 'rolled_back';
  created_by: string;
  approved_by: string | null;
  approved_at: string | null;
  rolled_back_at: string | null;
  created_at: string;
}

export interface OrderRecon {
  id: string;
  external_order_id: string;
  order_id: string;
  partner_id: string;
  channel: string;
  payment_mode: string;
  order_date: string;
  order_value: string;
  rate_card_id: string | null;
  expected_amount: string | null;
  received_amount: string;
  settlement_credit: string;
  cod_remittance: string;
  expected_commission: string;
  actual_commission: string;
  expected_fixed_fee: string;
  actual_fixed_fee: string;
  expected_freight: string;
  actual_freight: string;
  expected_cod_fee: string;
  actual_cod_fee: string;
  tcs_amount: string;
  tds_amount: string;
  difference: string | null;
  status: 'settled' | 'short_paid' | 'unpaid_past_due' | 'freight_overcharged' | 'return_not_received' | 'pending';
  reason_codes: string[];
  due_date: string | null;
  age_days: number;
  age_bucket: '0-7' | '8-15' | '16-30' | '31+';
  money_at_risk: string;
  settlement_gap_component: string;
  freight_excess_component: string;
  return_loss_component: string;
  breakdown_json: Record<string, any>;
  source_events_count: number;
  computed_at: string;
}

export interface PaginatedOrderRecon {
  items: OrderRecon[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TimelineEventItem {
  id: string;
  feed_type: 'orders' | 'settlement' | 'cod' | 'freight' | 'tracking' | 'warehouse' | 'reversal';
  event_type: string;
  event_timestamp: string;
  source_partner_id: string;
  amount: string | null;
  transaction_reference: string | null;
  status: string | null;
  details: Record<string, any>;
}

export interface OrderTimelineResponse {
  order_id: string;
  external_order_id: string;
  partner_id: string;
  total_events: number;
  timeline: TimelineEventItem[];
}

export interface ReconSummary {
  as_of: string;
  total_orders: number;
  total_money_at_risk: string;
  settled_count: number;
  short_paid_count: number;
  unpaid_past_due_count: number;
  freight_overcharged_count: number;
  return_not_received_count: number;
  pending_count: number;
  age_bucket_counts: Record<string, number>;
  partner_risk_breakdown: Record<string, string>;
}

export interface Claim {
  id: string;
  order_recon_id: string;
  external_order_id: string;
  order_id: string;
  partner_id: string;
  claim_amount: string;
  recovered_amount: string;
  recovered_at: string | null;
  claim_reason: string;
  evidence_json: Record<string, any>;
  claim_status: 'draft' | 'submitted' | 'in_review' | 'approved' | 'rejected' | 'recovered';
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClaimDetail extends Claim {
  order?: OrderRecon;
}

export interface PaginatedClaims {
  items: Claim[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ClaimsSummary {
  total_claims: number;
  total_claim_amount: string;
  total_recovered_amount: string;
  total_outstanding_amount: string;
  status_counts: Record<string, number>;
  recovery_rate_pct: string;
  partner_claims_summary: Record<string, {
    total_claims: number;
    claimed_amount: string;
    recovered_amount: string;
    outstanding_amount: string;
  }>;
}

export interface DashboardMetrics {
  as_of: string;
  total_orders: number;
  total_money_at_risk: string;
  total_settlement_gap: string;
  total_freight_excess: string;
  total_return_loss: string;
  status_counts: Record<string, number>;
  age_bucket_counts: Record<string, number>;
  age_bucket_risk: Record<string, string>;
  partner_risk_breakdown: Record<string, string>;
  partner_order_counts: Record<string, number>;
  reason_code_risk_breakdown: Record<string, string>;
  reason_code_counts: Record<string, number>;
  claims_summary: ClaimsSummary;
}

function getCsrfTokenFromCookie(): string | null {
  const match = document.cookie.match(new RegExp('(^| )csrf_token=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Attach CSRF token on state-changing requests
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method?.toUpperCase() || 'GET')) {
    const csrfToken = getCsrfTokenFromCookie();
    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
    credentials: 'include', // Sends HttpOnly cookies
  });

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      errorDetail = response.statusText;
    }
    const error = new Error(errorDetail) as Error & { status: number };
    error.status = response.status;
    throw error;
  }

  return response.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    apiRequest<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    apiRequest<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST',
    }),

  getMe: () => apiRequest<User>('/api/v1/auth/me'),

  // Rate Cards
  listRateCards: (partnerId?: string, channel?: string) => {
    const params = new URLSearchParams();
    if (partnerId) params.set('partner_id', partnerId);
    if (channel) params.set('channel', channel);
    return apiRequest<RateCard[]>(`/api/v1/rate-cards/?${params.toString()}`);
  },

  // Sources
  listSources: () => apiRequest<Source[]>('/api/v1/sources/'),

  // Uploads
  uploadFile: (formData: FormData) =>
    apiRequest<UploadPreview>('/api/v1/uploads/', {
      method: 'POST',
      body: formData,
    }),

  listUploads: (skip = 0, limit = 100) =>
    apiRequest<Upload[]>(`/api/v1/uploads/?skip=${skip}&limit=${limit}`),

  getUpload: (uploadId: string) =>
    apiRequest<Upload>(`/api/v1/uploads/${uploadId}`),

  getUploadErrors: (uploadId: string) =>
    apiRequest<UploadRowError[]>(`/api/v1/uploads/${uploadId}/errors`),

  fetchSampleFile: async (filename: string): Promise<File> => {
    const res = await fetch(`/api/v1/uploads/sample-file/${filename}`, {
      credentials: 'include',
    });
    if (!res.ok) {
      throw new Error(`Failed to load sample file: ${res.statusText}`);
    }
    const blob = await res.blob();
    return new File([blob], filename, { type: 'text/csv' });
  },

  processPendingUpload: (uploadId: string) =>
    apiRequest<{ status: string; upload: Upload; summary: any }>(`/api/v1/uploads/${uploadId}/process`, {
      method: 'POST',
    }),

  // Column Mappings
  suggestMapping: (
    sourceId: string, 
    sourceColumns: string[], 
    samplesByCol?: Record<string, any[]>, 
    enableAi: boolean = true
  ) =>
    apiRequest<any>('/api/v1/mappings/suggest', {
      method: 'POST',
      body: JSON.stringify({ 
        source_id: sourceId, 
        source_columns: sourceColumns,
        samples_by_col: samplesByCol,
        enable_ai: enableAi 
      }),
    }),

  approveMapping: (sourceId: string, mappingJson: Record<string, string>) =>
    apiRequest<ColumnMapping>('/api/v1/mappings/approve', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, mapping_json: mappingJson }),
    }),

  getActiveMapping: (sourceId: string) =>
    apiRequest<ColumnMapping>(`/api/v1/mappings/source/${sourceId}`),

  getMappingVersions: (sourceId: string) =>
    apiRequest<ColumnMapping[]>(`/api/v1/mappings/source/${sourceId}/versions`),

  rollbackMapping: (mappingId: string) =>
    apiRequest<ColumnMapping>(`/api/v1/mappings/${mappingId}/rollback`, {
      method: 'POST',
    }),

  // Reconciliation Engine
  triggerRecon: (asOf?: string, orderIds?: string[]) =>
    apiRequest<any>('/api/v1/recon/run', {
      method: 'POST',
      body: JSON.stringify({ as_of: asOf, order_ids: orderIds }),
    }),

  listReconOrders: (params?: {
    status?: string;
    partner_id?: string;
    has_risk?: boolean;
    search?: string;
    start_date?: string;
    end_date?: string;
    reason_code?: string;
    age_bucket?: string;
    sort_by?: string;
    sort_dir?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
    skip?: number;
    limit?: number;
    envelope?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.partner_id) q.set('partner_id', params.partner_id);
    if (params?.has_risk !== undefined) q.set('has_risk', String(params.has_risk));
    if (params?.search) q.set('search', params.search);
    if (params?.start_date) q.set('start_date', params.start_date);
    if (params?.end_date) q.set('end_date', params.end_date);
    if (params?.reason_code) q.set('reason_code', params.reason_code);
    if (params?.age_bucket) q.set('age_bucket', params.age_bucket);
    if (params?.sort_by) q.set('sort_by', params.sort_by);
    if (params?.sort_dir) q.set('sort_dir', params.sort_dir);
    if (params?.page !== undefined) q.set('page', String(params.page));
    if (params?.page_size !== undefined) q.set('page_size', String(params.page_size));
    if (params?.skip !== undefined) q.set('skip', String(params.skip));
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.envelope !== undefined) q.set('envelope', String(params.envelope));
    return apiRequest<any>(`/api/v1/recon/orders?${q.toString()}`);
  },

  getReconOrderDetail: (orderId: string, partnerId?: string) => {
    const q = partnerId ? `?partner_id=${encodeURIComponent(partnerId)}` : '';
    return apiRequest<OrderRecon>(`/api/v1/recon/orders/${encodeURIComponent(orderId)}${q}`);
  },

  getOrderTimeline: (orderId: string, partnerId?: string) => {
    const q = partnerId ? `?partner_id=${encodeURIComponent(partnerId)}` : '';
    return apiRequest<OrderTimelineResponse>(`/api/v1/recon/orders/${encodeURIComponent(orderId)}/timeline${q}`);
  },

  getReconSummary: () =>
    apiRequest<ReconSummary>('/api/v1/recon/summary'),

  // Claims Management
  listClaims: (params?: {
    search?: string;
    partner_id?: string;
    claim_reason?: string;
    claim_status?: string;
    min_amount?: number;
    max_amount?: number;
    sort_by?: string;
    sort_dir?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
    envelope?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.search) q.set('search', params.search);
    if (params?.partner_id) q.set('partner_id', params.partner_id);
    if (params?.claim_reason) q.set('claim_reason', params.claim_reason);
    if (params?.claim_status) q.set('claim_status', params.claim_status);
    if (params?.min_amount !== undefined) q.set('min_amount', String(params.min_amount));
    if (params?.max_amount !== undefined) q.set('max_amount', String(params.max_amount));
    if (params?.sort_by) q.set('sort_by', params.sort_by);
    if (params?.sort_dir) q.set('sort_dir', params.sort_dir);
    if (params?.page !== undefined) q.set('page', String(params.page));
    if (params?.page_size !== undefined) q.set('page_size', String(params.page_size));
    if (params?.envelope !== undefined) q.set('envelope', String(params.envelope));
    return apiRequest<any>(`/api/v1/claims/?${q.toString()}`);
  },

  getClaimDetail: (claimId: string) =>
    apiRequest<ClaimDetail>(`/api/v1/claims/${claimId}`),

  updateClaim: (claimId: string, payload: {
    claim_status?: string;
    notes?: string;
    recovered_amount?: number;
    recovered_at?: string;
  }) =>
    apiRequest<Claim>(`/api/v1/claims/${claimId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  generateDraftClaims: () =>
    apiRequest<{ status: string; claims_generated_or_updated: number }>('/api/v1/claims/generate', {
      method: 'POST',
    }),

  getClaimsSummary: () =>
    apiRequest<ClaimsSummary>('/api/v1/claims/summary'),

  // Money-at-Risk Dashboard
  getDashboardMetrics: () =>
    apiRequest<DashboardMetrics>('/api/v1/dashboard/metrics'),
};
