# LeakCheck Sample Data Files for Upload Testing

These 5 sample CSV files cover all 5 required source types and represent real-world marketplace and carrier exports for Company A.

---

### File Catalog

| File Name | Source Type | Recommended Source in Dropdown | Notable Test Features |
| :--- | :--- | :--- | :--- |
| `01_shopify_orders.csv` | `orders` | **Shopify Direct Orders** | • Contains Customer Name, Phone, Address to test **DPDP Act PII Auto-stripping**<br>• Row 6 has a missing Order ID (triggers `MISSING_ORDER_ID` quarantine)<br>• Row 7 has an invalid amount `INVALID_AMT` (triggers `INVALID_NUMERIC` quarantine)<br>• Contains calibrated orders `ORD-W-204118`, `ORD-M-88120`, `ORD-W-204377` |
| `02_amazon_settlement.csv` | `settlement` | **Amazon Marketplace** | • Amazon header convention (`order-id`, `settlement-amount`, `commission-fee`, `tcs-amount`, `tds-amount`)<br>• Contains credit settlement for `ORD-W-204118` and net fee deduction (-₹96) for RTO order `ORD-W-204377` |
| `03_delhivery_cod_remittance.csv` | `cod` | **Delhivery Logistics** | • Courier COD remittance headers (`order_number`, `cod_amount`, `awb`)<br>• Ingests COD remittance for `ORD-M-88120` (₹899.00) |
| `04_bluedart_freight_invoice.csv` | `freight` | **BlueDart Express** | • Logistics freight charges with statuses (`DELIVERED`, `RTO`)<br>• Ingests freight charges for `ORD-W-204118` (₹65), `ORD-M-88120` (₹78.50), `ORD-W-204377` (₹96) |
| `05_blr_warehouse_receipts.csv` | `receipts` | **BLR Central Fulfillment** | • Inward return receipts for warehouse verification (`receipt_date`, `status`, `warehouse_id`)<br>• Verifies warehouse return delivery for RTO order `ORD-W-204377` to validate return claim deadlines |

---

### Step-by-Step Testing Workflow in Upload Center

1. **Sign in as Finance Executive:**
   - Email: `finance_exec@company-a.com`
   - Password: `Password123!` (or click the quick-fill button on the Sign-In screen)

2. **Upload `01_shopify_orders.csv`:**
   - In **Upload Center**, select **Shopify Direct Orders**.
   - Select or drag `sample_files/01_shopify_orders.csv`.
   - Click **Upload Statement**.
   - Notice the system automatically navigates to **Column Mapping Review** with:
     - 100% exact & fuzzy matched canonical fields.
     - Notice that `Customer Name`, `Customer Phone`, and `Shipping Address` are discarded at parse time per DPDP Act.
     - Click **Approve & Activate (v1)** and then **Ingest Staged File**.
   - In **Upload Center**, open the **Quarantined Rows Audit** to inspect the 2 quarantined rows (Rows 6 & 7).

3. **Upload the Remaining 4 Files:**
   - Repeat for `02_amazon_settlement.csv` under **Amazon Marketplace**.
   - Repeat for `03_delhivery_cod_remittance.csv` under **Delhivery Logistics**.
   - Repeat for `04_bluedart_freight_invoice.csv` under **BlueDart Express**.
   - Repeat for `05_blr_warehouse_receipts.csv` under **BLR Central Fulfillment**.

4. **Verify Co-founder Read-Only RBAC:**
   - Sign out and sign in as `cofounder@company-a.com`.
   - Notice that file uploads are disabled with an alert banner.
   - Switch to **Column Mapping** and verify that the Co-founder **can** approve new mapping versions and roll back historical versions.
