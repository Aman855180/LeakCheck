import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ColumnMappingReview, validateUploadMapping } from '../pages/ColumnMappingReview';
import { api, User, Source } from '../api/client';

vi.mock('../api/client', () => {
  return {
    api: {
      listSources: vi.fn(),
      getActiveMapping: vi.fn(),
      getMappingVersions: vi.fn(),
      getUpload: vi.fn(),
      getUploadPreview: vi.fn(),
      suggestMapping: vi.fn(),
      approveMapping: vi.fn(),
      rollbackMapping: vi.fn(),
      processPendingUpload: vi.fn(),
    },
  };
});

const mockFinanceUser: User = {
  id: 'usr-1',
  email: 'finance_exec@company-a.com',
  role: 'finance_exec',
  created_at: '2026-01-01T00:00:00Z',
};

const mockSource: Source = {
  id: 'src-shopify-1',
  partner_id: 'shopify',
  source_type: 'orders',
  name: 'Shopify Orders Feed',
  file_format: 'csv',
  is_active: true,
};

const mockActiveMapping = {
  id: 'map-v7',
  source_id: 'src-shopify-1',
  version: 7,
  mapping_json: {
    external_order_id: 'Order ID',
    order_value: 'Total Price',
    payment_mode: 'Payment Method',
    order_date: 'Created At',
  },
  status: 'approved' as const,
  created_by: 'usr-1',
  approved_by: 'usr-1',
  approved_at: '2026-11-01T00:00:00Z',
  rolled_back_at: null,
  created_at: '2026-11-01T00:00:00Z',
};

describe('validateUploadMapping pure function', () => {
  const canonicalFields = [
    { key: 'external_order_id', display_name: 'Order ID / External Reference', required_for: ['orders'] },
    { key: 'order_value', display_name: 'Order Value / GMV', required_for: ['orders'] },
    { key: 'order_date', display_name: 'Order Date', required_for: ['orders'] },
    { key: 'payment_mode', display_name: 'Payment Mode (Prepaid/COD)', required_for: [] },
  ];
  const detectedCols = ['retailer_transaction_code', 'basket_gross_inr', 'collection_method', 'purchase_timestamp'];

  it('returns no missing fields and null warning when all required fields are mapped to detected headers', () => {
    const mapping = {
      external_order_id: 'retailer_transaction_code',
      order_value: 'basket_gross_inr',
      order_date: 'purchase_timestamp',
      payment_mode: 'collection_method',
    };
    const res = validateUploadMapping(mapping, detectedCols, canonicalFields, 'orders');
    expect(res.missing).toEqual([]);
    expect(res.warning).toBeNull();
  });

  it('returns missing fields and warning when a required field is unmapped', () => {
    const mapping = {
      external_order_id: 'retailer_transaction_code',
      order_date: 'purchase_timestamp',
    };
    const res = validateUploadMapping(mapping, detectedCols, canonicalFields, 'orders');
    expect(res.missing).toContain('order_value');
    expect(res.warning).toContain('Order Value / GMV');
  });

  it('returns warning when mapped to a header not in the workbook', () => {
    const mapping = {
      external_order_id: 'Order ID', // old v7 header not in workbook
      order_value: 'basket_gross_inr',
      order_date: 'purchase_timestamp',
    };
    const res = validateUploadMapping(mapping, detectedCols, canonicalFields, 'orders');
    expect(res.missing).toContain('external_order_id');
    expect(res.warning).toContain("is mapped to 'Order ID', which is not present in the uploaded workbook headers");
  });
});

describe('ColumnMappingReview Component Isolation & Warnings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listSources).mockResolvedValue([mockSource]);
    vi.mocked(api.getActiveMapping).mockResolvedValue(mockActiveMapping);
    vi.mocked(api.getMappingVersions).mockResolvedValue([mockActiveMapping]);
  });

  it('Mode A: fetches upload-specific preview, renders uploaded headers, and hides stale v7 schema warning', async () => {
    const uploadId = '061efafd-25ce-4330-9172-280fd0184630';
    const mockPreview = {
      type: 'preview' as const,
      upload_id: uploadId,
      source_id: 'src-shopify-1',
      source_name: 'Shopify (Orders Feed)',
      file_name: 'LeakCheck_Gemini_AI_Mapping_Test.xlsx',
      source_type: 'orders',
      processing_status: 'mapping_pending',
      total_rows: 8,
      detected_columns: [
        'retailer_transaction_code',
        'basket_gross_inr',
        'collection_method',
        'purchase_timestamp',
        'parcel_consignment_code',
      ],
      dropped_pii_columns: [],
      preview_rows: [
        {
          retailer_transaction_code: 'RTX-001',
          basket_gross_inr: 1499.0,
          collection_method: 'Prepaid',
          purchase_timestamp: '2026-03-01',
          parcel_consignment_code: 'TRK-100',
        },
      ],
      suggested_mapping: {
        external_order_id: {
          column: 'retailer_transaction_code',
          confidence: 0.85,
          match_type: 'AI_SUGGESTED',
          reasoning: 'Matches order identifier via Gemini',
        },
        order_value: {
          column: 'basket_gross_inr',
          confidence: 0.95,
          match_type: 'AI_SUGGESTED',
          reasoning: 'Gross order amount in INR',
        },
        payment_mode: {
          column: 'collection_method',
          confidence: 0.95,
          match_type: 'AI_SUGGESTED',
          reasoning: 'Collection method represents payment mode',
        },
        order_date: {
          column: 'purchase_timestamp',
          confidence: 0.71,
          match_type: 'FUZZY',
        },
        tracking_number: {
          column: 'parcel_consignment_code',
          confidence: 0.70,
          match_type: 'FUZZY',
        },
      },
      missing_required: [],
      canonical_fields: [
        { key: 'external_order_id', display_name: 'Order ID / External Reference', required_for: ['orders'], description: 'Unique order identifier' },
        { key: 'order_value', display_name: 'Order Value / GMV', required_for: ['orders'], description: 'Gross invoice amount' },
        { key: 'payment_mode', display_name: 'Payment Mode (Prepaid/COD)', required_for: [], description: 'Payment mode' },
        { key: 'order_date', display_name: 'Order Date', required_for: ['orders'], description: 'Order placement date' },
        { key: 'tracking_number', display_name: 'AWB / Waybill / Tracking #', required_for: [], description: 'Shipment tracking' },
      ],
      is_mapping_compatible: false,
      incompatibility_reasons: [
        "Required field 'Order ID / External Reference' mapped to 'Order ID' missing.",
        "Required field 'Order Value / GMV' mapped to 'Total Price' missing.",
        "Required field 'Order Date' mapped to 'Created At' missing."
      ],
      upload: {
        id: uploadId,
        source_id: 'src-shopify-1',
        partner_id: 'shopify',
        source_type: 'orders',
        file_name: 'LeakCheck_Gemini_AI_Mapping_Test.xlsx',
        file_hash: 'hash-123',
        file_size_bytes: 1024,
        row_count: 8,
        mapping_version: null,
        processing_status: 'mapping_pending' as const,
        error_count: 0,
        uploaded_by: 'usr-1',
        created_at: '2026-11-09T00:00:00Z',
        updated_at: '2026-11-09T00:00:00Z',
      },
    };

    vi.mocked(api.getUploadPreview).mockResolvedValue(mockPreview);

    render(
      <ColumnMappingReview
        currentUser={mockFinanceUser}
        sourceId="src-shopify-1"
        uploadId={uploadId}
        sources={[mockSource]}
        onBackToUploads={vi.fn()}
      />
    );

    // Verify upload preview API was called with exact uploadId
    await waitFor(() => {
      expect(api.getUploadPreview).toHaveBeenCalledWith(uploadId);
    });

    // Verify filename and detected columns are displayed in the dropdowns
    await waitFor(() => {
      expect(screen.getByText('LeakCheck_Gemini_AI_Mapping_Test.xlsx')).toBeDefined();
      expect(screen.getAllByText(/retailer_transaction_code/).length).toBeGreaterThan(0);
    });

    // Verify matching badges:
    // 1. Gemini AI Suggested (85% or 95%)
    expect(screen.getByText(/Gemini AI Suggested \(85%\)/)).toBeDefined();
    expect(screen.getAllByText(/Gemini AI Suggested \(95%\)/).length).toBe(2);

    // 2. RapidFuzz Match with confidence < 80% requires review
    expect(screen.getByText(/RapidFuzz Match \(Review Required\) \(71%\)/)).toBeDefined();
    expect(screen.getByText(/RapidFuzz Match \(Review Required\) \(70%\)/)).toBeDefined();

    // Verify stale Schema Update Recommended warning comparing against old v7 headers is NOT present
    expect(screen.queryByText(/Schema Update Recommended:/)).toBeNull();
    expect(screen.queryByText(/mapped to 'Order ID'/)).toBeNull();
    expect(screen.queryByText(/mapped to 'Total Price'/)).toBeNull();
  });

  it('Mode A: dynamically shows warning when a required field is unmapped and clears it when re-mapped', async () => {
    const uploadId = '061efafd-25ce-4330-9172-280fd0184630';
    const mockPreview = {
      type: 'preview' as const,
      upload_id: uploadId,
      source_id: 'src-shopify-1',
      source_name: 'Shopify (Orders Feed)',
      file_name: 'LeakCheck_Gemini_AI_Mapping_Test.xlsx',
      source_type: 'orders',
      processing_status: 'mapping_pending',
      total_rows: 8,
      detected_columns: [
        'retailer_transaction_code',
        'basket_gross_inr',
        'collection_method',
        'purchase_timestamp',
      ],
      dropped_pii_columns: [],
      preview_rows: [],
      suggested_mapping: {
        external_order_id: { column: 'retailer_transaction_code', confidence: 0.90, match_type: 'AI_SUGGESTED' },
        order_value: { column: 'basket_gross_inr', confidence: 0.95, match_type: 'AI_SUGGESTED' },
        order_date: { column: 'purchase_timestamp', confidence: 0.71, match_type: 'FUZZY' },
      },
      missing_required: [],
      canonical_fields: [
        { key: 'external_order_id', display_name: 'Order ID / External Reference', required_for: ['orders'], description: 'Unique order identifier' },
        { key: 'order_value', display_name: 'Order Value / GMV', required_for: ['orders'], description: 'Gross invoice amount' },
        { key: 'order_date', display_name: 'Order Date', required_for: ['orders'], description: 'Order placement date' },
      ],
      is_mapping_compatible: false,
      incompatibility_reasons: [],
      upload: {
        id: uploadId,
        source_id: 'src-shopify-1',
        partner_id: 'shopify',
        source_type: 'orders',
        file_name: 'LeakCheck_Gemini_AI_Mapping_Test.xlsx',
        file_hash: 'hash-123',
        file_size_bytes: 1024,
        row_count: 8,
        mapping_version: null,
        processing_status: 'mapping_pending' as const,
        error_count: 0,
        uploaded_by: 'usr-1',
        created_at: '2026-11-09T00:00:00Z',
        updated_at: '2026-11-09T00:00:00Z',
      },
    };

    vi.mocked(api.getUploadPreview).mockResolvedValue(mockPreview);

    render(
      <ColumnMappingReview
        currentUser={mockFinanceUser}
        sourceId="src-shopify-1"
        uploadId={uploadId}
        sources={[mockSource]}
        onBackToUploads={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('LeakCheck_Gemini_AI_Mapping_Test.xlsx')).toBeDefined();
    });

    // Initially: all 3 required fields mapped -> NO warning
    expect(screen.queryByText(/Schema Update Recommended:/)).toBeNull();

    // Find the dropdown for external_order_id (index 1 after the source selector at index 0)
    const selects = screen.getAllByRole('combobox');
    const orderIdSelect = selects[1];
    expect(orderIdSelect).toBeDefined();

    // User unmaps external_order_id
    fireEvent.change(orderIdSelect, { target: { value: '' } });

    // Warning and missing alert MUST appear now
    await waitFor(() => {
      expect(screen.getByText(/Schema Update Recommended:/)).toBeDefined();
      expect(screen.getByText(/Missing required fields \(Order ID \/ External Reference\)/)).toBeDefined();
    });

    // User re-maps external_order_id to retailer_transaction_code
    fireEvent.change(orderIdSelect, { target: { value: 'retailer_transaction_code' } });

    // Warning MUST disappear again
    await waitFor(() => {
      expect(screen.queryByText(/Schema Update Recommended:/)).toBeNull();
    });
  });

  it('Mode A: displays clean error message when preview API fails without fallback to sample data', async () => {
    const uploadId = 'missing-uuid-123';
    vi.mocked(api.getUploadPreview).mockRejectedValue(new Error('Upload preview not found'));

    render(
      <ColumnMappingReview
        currentUser={mockFinanceUser}
        sourceId="src-shopify-1"
        uploadId={uploadId}
        sources={[mockSource]}
        onBackToUploads={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Upload Review Unavailable')).toBeDefined();
      expect(screen.getAllByText(/Upload preview not found/).length).toBeGreaterThan(0);
    });
  });

  it('Mode B: preserves source-level mapping functionality when uploadId is absent', async () => {
    vi.mocked(api.suggestMapping).mockResolvedValue({
      source_id: 'src-shopify-1',
      source_type: 'orders',
      suggestions: {},
      missing_required: [],
      canonical_fields: [
        { key: 'external_order_id', display_name: 'Order ID / External Reference', required_for: ['orders'], description: 'Unique order identifier' },
      ],
    });

    render(
      <ColumnMappingReview
        currentUser={mockFinanceUser}
        sourceId="src-shopify-1"
        uploadId={undefined}
        sources={[mockSource]}
        onBackToUploads={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Column Mapping Editor: Shopify Orders Feed/)).toBeDefined();
      expect(api.getUploadPreview).not.toHaveBeenCalled();
    });
  });
});
