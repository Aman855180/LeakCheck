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

  lookupRateCard: (partnerId: string, channel: string, ruleType: string, targetDate: string) => {
    const params = new URLSearchParams({
      partner_id: partnerId,
      channel,
      rule_type: ruleType,
      target_date: targetDate,
    });
    return apiRequest<RateCard>(`/api/v1/rate-cards/lookup?${params.toString()}`);
  },
};
