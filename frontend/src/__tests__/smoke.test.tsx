import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { App } from '../App';
import { api } from '../api/client';
import { ClaimsManagement } from '../pages/ClaimsManagement';
import { ReconciliationHub } from '../pages/ReconciliationHub';

// Mock the API client
vi.mock('../api/client', () => {
  return {
    api: {
      getMe: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      listRateCards: vi.fn().mockResolvedValue([]),
      listSources: vi.fn().mockResolvedValue([
        { id: 'src-1', partner_id: 'amazon', source_type: 'orders', format: 'csv', version: 1 }
      ]),
      getDashboardMetrics: vi.fn().mockResolvedValue({
        total_orders: 1250,
        total_money_at_risk: 15420.50,
        total_settlement_gap: 9200.00,
        total_freight_excess: 4100.50,
        total_return_loss: 2120.00,
        age_bucket_counts: { '0-7': 100, '8-15': 40, '16-30': 15, '31+': 5 },
        partner_risk_breakdown: { amazon: 8400.00, shopify: 7020.50 },
        reason_code_breakdown: { settlement_shortfall: 9200.00, freight_overcharge: 4100.50 },
        claims_summary: {
          total_claims: 28,
          total_claim_amount: 15420.50,
          total_recovered_amount: 4500.00,
          total_outstanding_amount: 10920.50,
          status_counts: { draft: 10, submitted: 8, recovered: 10 },
          recovery_rate_pct: 29.18
        }
      }),
      listReconOrders: vi.fn().mockResolvedValue({
        items: [
          {
            id: 'recon-1',
            order_id: 'ORD-TEST-001',
            partner_id: 'amazon',
            channel: 'marketplace',
            payment_mode: 'PREPAID',
            order_date: '2026-10-25T10:00:00Z',
            order_value: 1200.00,
            expected_amount: 1050.00,
            received_amount: 900.00,
            difference: -150.00,
            status: 'short_paid',
            reason_codes: ['excess_commission'],
            age_days: 12,
            age_bucket: '8-15',
            money_at_risk: 150.00,
            settlement_gap_component: 150.00,
            freight_excess_component: 0.00,
            return_loss_component: 0.00,
            audit_details: { history: [] }
          }
        ],
        total: 1,
        page: 1,
        page_size: 25,
        total_pages: 1
      }),
      listClaims: vi.fn().mockResolvedValue({
        items: [
          {
            id: 'claim-1',
            order_recon_id: 'recon-1',
            external_order_id: 'ORD-TEST-001',
            partner_id: 'amazon',
            claim_amount: 150.00,
            recovered_amount: 0.00,
            outstanding_amount: 150.00,
            claim_reason: 'excess_commission',
            claim_status: 'draft',
            notes: 'Test claim notes',
            evidence_json: { settlement_gap: '150.00' },
            created_at: '2026-10-26T12:00:00Z',
            updated_at: '2026-10-26T12:00:00Z'
          }
        ],
        total: 1,
        page: 1,
        page_size: 25,
        total_pages: 1
      }),
      getClaimsSummary: vi.fn().mockResolvedValue({
        total_claims: 1,
        total_claim_amount: 150.00,
        total_recovered_amount: 0.00,
        total_outstanding_amount: 150.00,
        status_counts: { draft: 1 },
        recovery_rate_pct: 0.00,
        partner_claims_summary: { amazon: { count: 1, amount: 150.00 } }
      }),
      getReconSummary: vi.fn().mockResolvedValue({
        total_orders: 1,
        status_counts: { short_paid: 1 },
        total_order_value: 1200.00,
        total_expected: 1050.00,
        total_received: 900.00,
        total_money_at_risk: 150.00,
        total_settlement_gap: 150.00,
        total_freight_excess: 0.00,
        total_return_loss: 0.00
      }),
      listUploads: vi.fn().mockResolvedValue([]),
      getMapping: vi.fn().mockResolvedValue({ mappings: {} }),
      getMappingHistory: vi.fn().mockResolvedValue([]),
      getOrderTimeline: vi.fn().mockResolvedValue({
        order_id: 'ORD-TEST-001',
        timeline: [],
        discrepancies: ['excess_commission']
      })
    }
  };
});

describe('Phase 7 Frontend End-to-End Smoke Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. Smoke Test: Authentication Flow & Role Badge for Finance Exec', async () => {
    (api.getMe as any).mockResolvedValueOnce({
      id: 'usr-1',
      email: 'finance_exec@company-a.com',
      role: 'finance_exec',
      is_active: true,
      created_at: '2026-10-01T00:00:00Z'
    });

    render(<App />);

    // Expect session to transition to Dashboard with Finance Exec role badge
    expect(await screen.findByText('Finance Exec')).toBeDefined();
    expect(screen.getByText('Executive Dashboard')).toBeDefined();
    expect(screen.getByText('finance_exec@company-a.com')).toBeDefined();
    expect(screen.getByText('v1.0.0 Ready')).toBeDefined();
  });

  it('2. Smoke Test: Orders & Reconciliation Hub with Filters & Detail', async () => {
    const mockUser = {
      id: 'usr-1',
      email: 'finance_exec@company-a.com',
      role: 'finance_exec' as const,
      is_active: true,
      created_at: '2026-10-01T00:00:00Z'
    };

    render(<ReconciliationHub currentUser={mockUser} />);

    // Table renders headers and records
    expect(await screen.findByText(/Orders & Reconciliation Hub/i)).toBeDefined();
    expect(await screen.findByText('ORD-TEST-001')).toBeDefined();

    // Search bar interaction
    const searchInput = screen.getByPlaceholderText(/Search by Order ID/i);
    fireEvent.change(searchInput, { target: { value: 'ORD-TEST-001' } });
    expect((searchInput as HTMLInputElement).value).toBe('ORD-TEST-001');

    // Click Audit & Timeline button to open detail drawer
    const auditBtn = await screen.findByRole('button', { name: /audit/i });
    expect(auditBtn).toBeDefined();
    fireEvent.click(auditBtn);
    const badges = await screen.findAllByText('Excess Commission');
    expect(badges.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Tariff Audit/i)).toBeDefined();
  });

  it('3. Smoke Test: Claims Management RBAC (Finance Exec vs Co-founder permissions)', async () => {
    // A) Test Finance Exec: can see enabled "Sync Draft Claims" action capability
    const financeUser = {
      id: 'usr-1',
      email: 'finance_exec@company-a.com',
      role: 'finance_exec' as const,
      is_active: true,
      created_at: '2026-10-01T00:00:00Z'
    };

    const { unmount } = render(<ClaimsManagement currentUser={financeUser} />);
    expect(await screen.findByText(/Claims Management & Recovery Hub/i)).toBeDefined();
    expect(screen.getByText(/Export Evidence CSV/i)).toBeDefined();
    const syncBtnFinance = screen.getByText(/Sync Draft Claims/i).closest('button') as HTMLButtonElement;
    expect(syncBtnFinance).not.toBeNull();
    expect(syncBtnFinance.disabled).toBe(false);
    unmount();

    // B) Test Co-founder: Read-only access (can export CSV, but Sync Draft Claims button is strictly disabled)
    const cofounderUser = {
      id: 'usr-2',
      email: 'cofounder@company-a.com',
      role: 'cofounder' as const,
      is_active: true,
      created_at: '2026-10-01T00:00:00Z'
    };

    render(<ClaimsManagement currentUser={cofounderUser} />);
    expect(await screen.findByText(/Claims Management & Recovery Hub/i)).toBeDefined();
    expect(screen.getByText(/Export Evidence CSV/i)).toBeDefined();
    const syncBtnCofounder = screen.getByText(/Sync Draft Claims/i).closest('button') as HTMLButtonElement;
    expect(syncBtnCofounder).not.toBeNull();
    expect(syncBtnCofounder.disabled).toBe(true);
  });
});
