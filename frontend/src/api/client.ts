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
  suggestMapping: (sourceId: string, sourceColumns: string[]) =>
    apiRequest<any>('/api/v1/mappings/suggest', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, source_columns: sourceColumns }),
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
};
