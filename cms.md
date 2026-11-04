# MASTER PROMPT — TRANSFORM THE DESKTOP CMS INTO A COMPLETE STORE MANAGEMENT ERP

## 1. ROLE AND MISSION

Act as a senior ERP software architect, full-stack developer, financial systems engineer, database architect, accounting software specialist, application security engineer, and QA engineer.

Your mission is to upgrade my EXISTING Windows desktop CMS into a complete, professional Store Management ERP that controls the entire e-commerce website and manages all business operations.

This is not simply a product-management application anymore.

It must become a centralized business management system capable of managing:

- The entire public e-commerce website.
- Products and product variants.
- Categories and attributes.
- Purchasing and suppliers.
- Sales and customer orders.
- Inventory and warehouse operations.
- Purchase prices and selling prices.
- Profit margins and financial calculations.
- Expenses and operating costs.
- Cash register and financial transactions.
- Accounting records and financial reports.
- Customer and supplier accounts.
- Invoices and documents.
- Website content and marketing.
- Reports, analytics, and business performance.

**The objective is to create a fully integrated desktop ERP and e-commerce management platform, not a collection of disconnected modules.**

Inspect the existing repository and architecture before changing anything.

Do not rebuild working components unnecessarily. Extend, repair, and integrate the existing application.

Implement actual functionality, connect all frontend and backend operations, run tests, and fix errors.

---

# 2. CORE ARCHITECTURE AND DATA INTEGRATION

The desktop application, backend, database, and public website must work as one unified system.

## Required architecture

### Desktop CMS / ERP
The main administrative application used by the store owner to control all operations.

### Backend API
The central business logic responsible for calculations, transactions, authorization, inventory, orders, accounting, and synchronization.

### Database
The authoritative storage for all business information and financial records.

### Public website
The customer-facing e-commerce platform displaying information controlled by the desktop CMS.

## Critical integration rules

1. Every CMS module must use real backend APIs.
2. All important business records must persist in the database.
3. The website must retrieve the correct data from the same backend.
4. Product updates must immediately become available to the website after successful synchronization.
5. Orders submitted through the website must automatically appear in the desktop ERP.
6. Website sales must automatically affect inventory and financial records according to the configured business rules.
7. Purchasing operations must update inventory and product costs.
8. Expenses must affect financial reports.
9. Every financial transaction must be traceable.
10. No module should maintain an independent conflicting version of business data.

Use database transactions for operations that affect multiple related records.

Implement proper validation, error handling, concurrency protection, and synchronization.

Never use mock data in production functionality.

---

# 3. COMPLETE WEBSITE MANAGEMENT

The desktop application must provide centralized control over the entire public website.

## Website dashboard and configuration

Allow the administrator to manage:

- Website name and branding.
- Logo and favicon.
- Brand colors.
- Homepage content.
- Homepage banners.
- Promotional sections.
- Featured products.
- Featured categories.
- Navigation menus.
- Product display ordering.
- Store contact information.
- WhatsApp number.
- Social media links.
- Store information pages.
- Terms and conditions.
- Privacy policy.
- Delivery information.
- SEO titles and descriptions.
- Website visibility and publication settings.

## Website content management

Provide appropriate interfaces for:

- Creating content sections.
- Editing existing sections.
- Publishing and unpublishing content.
- Managing images and media.
- Reordering sections.
- Managing promotional campaigns.
- Scheduling publication when supported.

Do not pretend the CMS can change arbitrary frontend code. Implement a structured content management system that the website frontend actually consumes.

## Website verification

Whenever a setting or content item is modified:

1. Validate the information.
2. Save it to the backend.
3. Confirm successful persistence.
4. Synchronize the public website.
5. Verify that the change appears correctly.

---

# 4. COMPLETE PRODUCT AND CATALOG MANAGEMENT

Build a professional product-management system.

## Product CRUD

Implement:

- Create products.
- Read product details.
- Update products.
- Archive or deactivate products.
- Delete products safely when permitted.
- Duplicate products.
- Bulk product operations.
- Import and export.

## Product information

Each product should support:

- Product name.
- SKU / reference.
- Barcode.
- Description.
- Category.
- Brand.
- Brand logo.
- Purchase price.
- Selling price.
- Promotional price.
- Quantity.
- Minimum stock.
- Product images.
- Product status.
- Creation and modification dates.
- Product variants.
- Product attributes.

## Dynamic categories

Maintain the existing dynamic category builder.

The administrator must be able to create custom categories and define their attributes.

Examples:

**Shoes**
- Brand.
- Size.
- Color.
- Material.
- Quantity per variant.

**Bags**
- Brand.
- Material.
- Color.
- Dimensions.
- Quantity.

**Watches**
- Brand.
- Model.
- Color.
- Strap material.
- Product reference.

The product creation form must adapt automatically to the selected category.

Do not hardcode every category's attributes.

## Product variants

Support combinations such as:

- Small / Medium / Large.
- Multiple colors.
- Multiple sizes.
- Different barcodes.
- Different prices where necessary.
- Different stock quantities.

Each variant must have its own identifiable record when independent inventory or pricing is required.

---

# 5. PURCHASE MANAGEMENT — GESTION DES ACHATS

Create a complete purchasing module.

This module is essential for controlling the real cost of inventory.

## Supplier management

Implement full supplier CRUD:

- Supplier name.
- Company name.
- Contact person.
- Phone number.
- Email.
- Address.
- Tax or registration identifiers where applicable.
- Supplier reference.
- Payment terms.
- Outstanding balance.
- Total purchases.
- Purchase history.
- Supplier notes.
- Active/inactive status.

## Purchase orders

Allow the administrator to:

- Create purchase orders.
- Add products and variants.
- Select suppliers.
- Specify quantities.
- Specify unit purchase prices.
- Apply discounts.
- Record taxes where applicable.
- Add transport and additional costs.
- Track expected delivery dates.
- Track purchase order status.
- Print or export purchase documents.

## Purchase receiving

When purchased goods arrive:

1. Record the received quantities.
2. Compare received quantities against ordered quantities.
3. Identify missing or damaged items.
4. Update inventory correctly.
5. Record the actual acquisition cost.
6. Update cost calculations using the configured costing method.
7. Create the corresponding supplier liability or payment record.
8. Preserve the complete purchase history.

Support partial deliveries and partial payments.

Do not update inventory simply because a purchase order was created. Inventory must change according to actual goods received.

## Purchase price history

Maintain historical purchase prices for each product and supplier.

Never overwrite historical purchase records when the purchase price changes.

Display:

- Last purchase price.
- Current calculated cost.
- Average purchase cost.
- Supplier-specific purchase prices.
- Purchase price evolution.

---

# 6. PRODUCT COSTING AND SELLING PRICE CALCULATIONS

This is one of the most important parts of the system.

Implement accurate financial calculations.

## Purchase cost

The system must distinguish between:

- Purchase unit price.
- Purchase discounts.
- Taxes.
- Shipping and transport.
- Customs or other acquisition costs when applicable.
- Additional acquisition expenses.

Calculate the acquisition cost using a configurable and documented allocation method.

For example:

Total acquisition cost =
Net purchase cost + allocated acquisition expenses.

Unit acquisition cost =
Total acquisition cost / received quantity.

Do not include recoverable taxes in inventory cost when the applicable accounting treatment requires them to be excluded. Support configurable tax treatment.

## Costing methods

Support an appropriate inventory valuation method, preferably:

- Weighted average cost.
- FIFO when required.

Select the method at the company or inventory configuration level.

Do not mix costing methods inconsistently.

Maintain cost history and prevent historical financial reports from changing unexpectedly when new purchases occur.

## Selling price management

Allow the administrator to configure:

- Purchase cost.
- Target profit margin.
- Desired markup.
- Selling price.
- Promotional price.
- Minimum permitted selling price.
- Tax treatment.

Implement two clearly distinguished calculations.

**Markup:**

Selling price = Cost × (1 + Markup percentage)

**Gross margin:**

Selling price = Cost / (1 - Gross margin percentage)

Never confuse markup with gross margin.

Display both values where useful.

## Automatic price calculator

When the purchase cost changes, provide a calculator showing:

- Current acquisition cost.
- Desired margin.
- Suggested selling price.
- Current selling price.
- Expected gross profit.
- Expected gross margin.
- Markup percentage.
- Tax-inclusive price where applicable.

Allow manual price overrides with appropriate permission and audit history.

Never automatically change public prices without an explicitly configured pricing rule or administrator confirmation.

---

# 7. SALES MANAGEMENT — GESTION DES VENTES

Build a complete sales management module.

Support:

- Website orders.
- Manual sales entered by an administrator.
- In-store sales / POS if required.
- Sales invoices.
- Sales returns.
- Refunds.
- Discounts.
- Delivery charges.
- Customer information.
- Payment methods.
- Payment status.
- Sales history.

## Sales CRUD

Allow authorized administrators to:

- Create sales records.
- View sales details.
- Edit permitted information.
- Cancel sales under controlled rules.
- Process returns.
- Issue refunds.
- Print invoices.
- Export sales reports.

Never allow arbitrary editing or deletion of finalized financial records.

Use reversals, credit notes, and audit records when financial corrections are necessary.

## Automatic sales calculations

For every sale calculate:

- Product quantity.
- Unit selling price.
- Subtotal.
- Discounts.
- Taxes.
- Delivery fees.
- Total amount.
- Amount paid.
- Remaining amount.
- Cost of goods sold.
- Gross profit.

The backend must calculate authoritative totals.

Never trust totals submitted by the frontend.

## Website order integration

When a customer places an order:

1. Validate the product and variant.
2. Retrieve the current server-side selling price.
3. Validate availability.
4. Apply the correct discounts and delivery rules.
5. Calculate the order total.
6. Create the order.
7. Record the price and product details as historical snapshots.
8. Reserve or decrement stock according to the configured order workflow.
9. Make the order visible in the desktop ERP.
10. Generate the relevant financial records at the correct business event.

Protect against duplicate submissions and overselling.

---

# 8. INVENTORY AND STOCK MANAGEMENT

Implement professional inventory control.

Features:

- Real-time stock.
- Stock per product variant.
- Stock adjustments.
- Stock transfers where multiple locations are supported.
- Inventory reception.
- Inventory reservation.
- Inventory release.
- Low-stock alerts.
- Out-of-stock alerts.
- Inventory valuation.
- Damaged goods.
- Lost goods.
- Returned goods.
- Stock movement history.
- Inventory reconciliation.

Every inventory movement must have:

- Product.
- Variant where applicable.
- Quantity.
- Movement type.
- Date and time.
- Source document.
- User responsible.
- Previous stock.
- Resulting stock.
- Reason.

Never allow manual changes to stock without recording a movement.

Use transactional updates to prevent race conditions.

---

# 9. CUSTOMER MANAGEMENT

Create a customer management module.

Customer accounts on the public website are NOT required.

The desktop ERP must manage customers associated with orders and sales.

Support:

- Customer CRUD.
- Customer name.
- Phone number.
- Email when available.
- Addresses.
- Order history.
- Purchase history.
- Total purchases.
- Outstanding balances.
- Payment history.
- Customer notes.
- Customer status.

Provide customer search and filtering.

Allow administrators to view customer purchase history and outstanding amounts.

Avoid collecting unnecessary personal information.

---

# 10. EXPENSE MANAGEMENT — GESTION DES DÉPENSES

Create a complete business-expense module.

Allow the administrator to record:

- Rent.
- Electricity.
- Internet.
- Employee salaries.
- Transport.
- Packaging.
- Advertising.
- Maintenance.
- Software subscriptions.
- Administrative expenses.
- Other custom expenses.

Each expense must support:

- Description.
- Category.
- Amount.
- Date.
- Payment method.
- Supplier or beneficiary where applicable.
- Invoice or receipt attachment.
- Reference number.
- Notes.
- Payment status.
- Recurrence where required.

Implement:

- Expense CRUD.
- Expense categories.
- Monthly expenses.
- Annual expenses.
- Expense reports.
- Search and filters.
- Export.
- Approval workflows if multiple roles exist.

Expenses must be included correctly in financial reports.

Do not confuse the date an expense is recorded with the date it is actually paid.

---

# 11. FINANCIAL MANAGEMENT AND CASH REGISTER

Create a financial management dashboard.

## Cash management

Support:

- Cash register.
- Opening balance.
- Cash inflows.
- Cash outflows.
- Cash withdrawals.
- Cash deposits.
- Cash closing balance.
- Cash differences.
- Daily cash reconciliation.
- Cash movement history.

## Payment management

Support configurable payment methods:

- Cash.
- Bank transfer.
- Card.
- Online payment.
- Other custom methods.

Track:

- Payment amount.
- Payment date.
- Payment reference.
- Related sale or purchase.
- Payment status.
- Remaining balance.

Support partial payments.

Do not automatically mark a payment as received unless the payment has actually been confirmed.

## Financial accounts

Allow the store to manage:

- Cash account.
- Bank accounts.
- Payment accounts.
- Supplier liabilities.
- Customer receivables.
- Other configurable financial accounts.

All financial movements must be traceable to their source transactions.

---

# 12. ACCOUNTING MODULE — COMPTABILITÉ

Build an accounting module with a structured, auditable financial ledger.

Do not implement accounting as simple income-minus-expenses calculations.

## Accounting features

Implement:

- Chart of accounts.
- Journal entries.
- General ledger.
- Journal records.
- Debit and credit movements.
- Trial balance.
- Accounts receivable.
- Accounts payable.
- Cash and bank movements.
- Expense accounting.
- Purchase accounting.
- Sales accounting.
- Inventory accounting.
- Tax records where applicable.
- Financial period management.
- Financial reports.
- Accounting exports.

## Double-entry accounting

Where formal accounting is implemented, every posted accounting entry must balance:

Total debits = Total credits.

Validate this rule on the backend before posting.

Use configurable accounts and posting rules.

For example, support accounting mappings for:

- Sales revenue.
- Purchase expenses or inventory.
- Cash.
- Bank.
- Customer receivables.
- Supplier payables.
- Taxes payable.
- Operating expenses.
- Cost of goods sold.
- Inventory assets.

Use appropriate accounting treatment according to the configured accounting policy.

Do not create duplicate accounting entries when an order or payment is retried.

## Financial record integrity

Posted accounting entries must not be silently deleted or modified.

Use controlled reversal entries and corrections.

Maintain:

- Original document.
- Posting date.
- Accounting period.
- User responsible.
- Journal reference.
- Related transaction.
- Audit history.

Support period closing and prevent unauthorized changes to closed periods.

## Algerian accounting context

Design the accounting module to support Algerian business requirements, including configurable:

- DZD currency.
- VAT rates and tax treatment.
- Tax identifiers.
- Invoice numbering.
- Applicable fiscal settings.
- Accounting accounts.
- Financial reports and exports.

Do not hardcode tax rates or claim legal compliance without verification.

Keep tax rules configurable and document the assumptions.

The resulting reports and accounting configuration must be reviewed by a qualified Algerian accountant before being used for official statutory accounting or tax declarations.

---

# 13. PROFIT, MARGIN AND BUSINESS ANALYTICS

Create a dedicated business performance dashboard.

Calculate and display:

- Total revenue.
- Net sales.
- Gross profit.
- Gross margin.
- Cost of goods sold.
- Operating expenses.
- Net operating result.
- Outstanding customer balances.
- Outstanding supplier balances.
- Inventory valuation.
- Purchase totals.
- Sales totals.
- Average order value.
- Best-selling products.
- Most profitable products.
- Slow-moving products.
- Low-stock products.
- Monthly performance.
- Annual performance.

Clearly distinguish:

**Revenue:** Sales value according to the configured accounting basis.

**Gross profit:** Net sales minus cost of goods sold.

**Operating result:** Gross profit minus applicable operating expenses.

**Net profit:** Result after all applicable costs, expenses, taxes, and financial items.

Do not label cash received as revenue automatically.

Do not count unpaid customer balances as cash.

Do not count supplier credit purchases as immediate cash outflows.

Do not count the same transaction twice.

Provide filters for:

- Today.
- Yesterday.
- This week.
- This month.
- This year.
- Custom date range.

All dashboards must use actual backend calculations.

---

# 14. INVOICES AND BUSINESS DOCUMENTS

Create professional document generation.

Support:

- Purchase orders.
- Purchase invoices.
- Sales invoices.
- Customer receipts.
- Supplier payment receipts.
- Credit notes.
- Refund documents.
- Expense receipts.
- Stock adjustment documents.
- Financial reports.

Documents should include:

- Store branding.
- Document number.
- Date.
- Customer or supplier details.
- Product descriptions.
- Quantities.
- Unit prices.
- Taxes where applicable.
- Discounts.
- Total.
- Payment status.
- Relevant legal information where configured.

Support PDF export and printing.

Use safe and consistent document numbering.

Never generate duplicate invoice numbers.

---

# 15. REPORTING AND EXPORTS

Create an integrated reporting module.

Reports must include:

- Sales reports.
- Purchase reports.
- Profit and margin reports.
- Product performance.
- Inventory reports.
- Stock movement reports.
- Supplier reports.
- Customer reports.
- Expense reports.
- Cash register reports.
- Bank movement reports.
- Accounts receivable.
- Accounts payable.
- General ledger.
- Trial balance.
- Financial summaries.

Support:

- PDF.
- Excel.
- CSV.

Ensure exported reports match the actual filtered database results.

Protect sensitive financial reports with appropriate administrator permissions.

---

# 16. ADMINISTRATOR ROLES AND PERMISSIONS

Implement permission-based access if multiple staff members use the software.

Example roles:

- Owner / Super Administrator.
- Store Manager.
- Sales Employee.
- Inventory Manager.
- Accountant.

Permissions should control access to:

- Product management.
- Purchase prices.
- Selling prices.
- Financial reports.
- Accounting.
- Expenses.
- Customer information.
- Order management.
- Website settings.
- Backups.
- Administrator management.

The owner must be able to configure permissions.

Enforce permissions on the backend, not only in the interface.

Maintain an audit log for sensitive operations.

---

# 17. BACKUP AND DATA RECOVERY

Protect all business information.

Implement:

- Manual database backups.
- Scheduled backups where supported.
- Product image backups.
- Document backups.
- Configuration backups.
- Backup verification.
- Restore functionality.
- Backup retention policies.
- Secure backup storage.

Test restoration in an isolated environment.

Never run destructive recovery tests against production.

Ensure the backup includes financial records, stock history, purchase records, sales history, and accounting records.

---

# 18. UI/UX AND DESKTOP APPLICATION DESIGN

Transform the existing desktop interface into a professional ERP interface.

Preserve the existing brand identity, logo, and color palette.

Create a clear navigation structure:

1. Dashboard.
2. Website Management.
3. Products.
4. Categories and Attributes.
5. Inventory.
6. Purchases.
7. Suppliers.
8. Sales.
9. Orders.
10. Customers.
11. Expenses.
12. Cash Register.
13. Finance.
14. Accounting.
15. Reports.
16. Invoices and Documents.
17. Users and Permissions.
18. Backup and Recovery.
19. Settings.

Use professional data tables, search, filters, sorting, pagination, dialogs, forms, and clear status indicators.

Provide useful loading, empty, error, and success states.

Avoid overcrowded screens.

Use clear financial formatting and distinguish costs, revenue, profit, liabilities, and cash balances.

Support DZD formatting and the languages already supported by the project.

Do not replace the existing interface unnecessarily. Improve and extend it consistently.

---

# 19. DATABASE DESIGN AND FINANCIAL DATA INTEGRITY

Review the existing database and design the necessary relationships.

Ensure proper relationships between:

- Products.
- Categories.
- Attributes.
- Variants.
- Suppliers.
- Purchase orders.
- Purchase receipts.
- Purchase invoices.
- Customers.
- Sales.
- Orders.
- Payments.
- Expenses.
- Inventory movements.
- Cash accounts.
- Accounting journals.
- Ledger entries.
- Financial periods.
- Documents.
- Users.
- Audit logs.

Use database migrations.

Preserve existing data.

Use appropriate decimal or fixed-precision numeric types for financial values. Never use floating-point arithmetic for authoritative money calculations.

Define currency precision and rounding rules explicitly.

Use database transactions for related financial and inventory operations.

Prevent duplicate payments, duplicate invoices, and duplicate journal entries.

Maintain historical snapshots for product prices, supplier prices, order totals, and financial documents.

Never recalculate old posted financial transactions using today's product prices.

---

# 20. SECURITY AND PRODUCTION QUALITY

Perform a full security audit.

Check:

- Authentication.
- Authorization.
- Password hashing.
- Session management.
- Secure token storage.
- API protection.
- SQL injection.
- IDOR.
- XSS.
- CSRF where applicable.
- File upload security.
- Rate limiting.
- CORS.
- HTTPS.
- Secret management.
- Dependency vulnerabilities.
- Data exposure.
- Audit logging.

Protect sensitive information, especially:

- Purchase prices.
- Profit margins.
- Customer details.
- Supplier details.
- Financial reports.
- Accounting records.
- Administrator credentials.

Do not expose internal financial information through public website APIs.

Never store private API credentials in frontend code.

---

# 21. COMPLETE TESTING AND INTEGRATION

Do not stop after implementing the interface.

Run real integration tests.

## Essential end-to-end workflow

Test the following scenario:

1. Administrator logs into the desktop ERP.
2. Administrator creates a supplier.
3. Administrator creates a purchase order.
4. Administrator records the received goods.
5. Inventory increases correctly.
6. Acquisition cost is calculated correctly.
7. Weighted average cost or configured costing method updates correctly.
8. Administrator defines a target gross margin.
9. System calculates a suggested selling price.
10. Administrator publishes the product.
11. Public website displays the product and correct selling price.
12. Customer submits a guest order.
13. Order appears in the desktop ERP.
14. Inventory changes correctly.
15. Sales totals are calculated correctly.
16. Cost of goods sold is calculated correctly.
17. Gross profit is calculated correctly.
18. Relevant accounting entries are generated according to the configured posting rules.
19. Customer payment is recorded.
20. Cash or bank balance changes correctly.
21. An operating expense is recorded.
22. Financial reports reflect the expense.
23. Dashboard profit and financial summaries update correctly.
24. An authorized administrator generates a report.
25. Backup and restoration are verified in an isolated environment.

Test partial payments, partial deliveries, cancellations, refunds, returns, concurrent orders, and failed API requests.

Use isolated test data and databases.

Never create fake financial transactions in the live production database.

---

# 22. IMPLEMENTATION RULES

Follow these rules strictly:

1. Inspect the entire existing project before modifying it.
2. Preserve working functionality.
3. Implement actual CRUD operations for every relevant module.
4. Connect every interface to its backend functionality.
5. Connect every backend operation to the correct database records.
6. Connect the public website to the same authoritative business data.
7. Do not leave empty buttons or placeholder functionality.
8. Do not use fake calculations.
9. Do not hardcode financial results.
10. Do not use floating-point values for authoritative money calculations.
11. Do not silently delete financial records.
12. Do not change historical accounting records when current product prices change.
13. Do not expose internal costs or financial information publicly.
14. Do not introduce unnecessary frameworks.
15. Use safe migrations.
16. Run tests after major changes.
17. Fix actual errors instead of hiding them.
18. Document missing external dependencies.
19. Do not claim production readiness without evidence.
20. Do not deploy destructive changes without authorization.

If the implementation is too large for one session, divide it into logical phases, preserve progress, and continue from the existing implementation.

Prioritize financial integrity, inventory accuracy, backend authorization, and data consistency before cosmetic improvements.

---

# 23. REQUIRED PROJECT DOCUMENTATION

Create or update:

- `docs/ERP_ARCHITECTURE.md`
- `docs/PRODUCTION_AUDIT.md`
- `docs/API_INVENTORY.md`
- `docs/DATABASE_SCHEMA.md`
- `docs/PURCHASING_AND_COSTING.md`
- `docs/SALES_AND_INVENTORY.md`
- `docs/ACCOUNTING_LOGIC.md`
- `docs/FINANCIAL_CALCULATIONS.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/BACKUP_RESTORE.md`
- `docs/TEST_REPORT.md`

Document financial formulas, tax assumptions, inventory valuation methods, transaction rules, and accounting mappings.

---

# 24. FINAL ACCEPTANCE CRITERIA

The project must not be considered complete until:

- The desktop CMS operates as a complete store-management ERP within the implemented scope.
- The public website is controlled by the desktop CMS through real APIs.
- Product, category, and attribute management works.
- Purchase management works.
- Supplier management works.
- Purchase costs are calculated correctly.
- Selling prices and profit margins are calculated correctly.
- Inventory is accurate.
- Sales and website orders are integrated.
- Customer records are managed correctly.
- Expenses are included in financial reporting.
- Cash and bank movements are traceable.
- Accounting entries balance.
- Financial reports use correct data and formulas.
- Invoices and documents can be generated.
- Permissions are enforced server-side.
- Historical financial data is preserved.
- Backups can be restored.
- No known critical data-integrity or security defects remain unresolved.
- Automated tests pass or remaining failures are explicitly documented.
- The desktop application, backend, database, and website work together correctly.

## FINAL INSTRUCTION

Start by inspecting the existing repository.

Understand what is already implemented and what is missing.

Create an implementation plan based on the actual code.

Then implement, connect, test, and repair the entire system.

Do not simply create additional dashboard pages. Build the real business logic behind them.

Do not claim that accounting, purchasing, inventory, or financial management works until the underlying database operations and calculations have been tested.

**The final result must be a unified Windows desktop Store Management ERP that controls the complete e-commerce website and manages the real financial and operational activities of the business.**

The goal is a professional, reliable, secure, maintainable, production-ready business management system—not a demo or a collection of disconnected screens.