# MUS LUXURY — COMPLETE RETAIL ERP, POS, INVENTORY & E-COMMERCE PLATFORM

## Mission and role

Act as a principal software architect, senior full-stack engineer, ERP/POS specialist, network engineer, database architect, cybersecurity engineer, and QA automation engineer.

You are working on an existing project called **Mus Luxury**.

Your task is to transform the existing CMS into a complete, professional retail management system for a real Algerian business, while maintaining and improving its existing e-commerce website.

This is a serious production project. Do not treat it as a simple website administration dashboard.

The final application must serve TWO connected purposes:

**1. Local Retail Management System**
Manage the physical store, including inventory, purchases, suppliers, customers, sales, cash register, invoices, employees, accounting operations, barcode scanners, receipt printers, and other physical devices.

**2. Online E-Commerce Management System**
Manage the public website, online products, categories, pricing, orders, customers, delivery, promotions, and website content.

Both systems must work together using a secure, reliable synchronization architecture.

The store owner should be able to manage the physical business and the online store from one coherent application.

Do not blindly rewrite the existing project. Inspect it, understand what works, identify architectural weaknesses, and evolve it safely.

---

# PART 1 — INFRASTRUCTURE AND ARCHITECTURE

## 1. Available VPS infrastructure

The purchased VPS currently advertises these specifications:

| Resource | Specification |
|---|---|
| Provider | Octenium |
| Plan | VPS Starter |
| CPU | 1 Intel Xeon vCore |
| RAM | 2 GB |
| Storage | 150 GB RAID 10 |
| Bandwidth | 250 Mbps |
| Traffic | Advertised unlimited |
| IP | 1 fixed public IP |
| Protection | Anti-DDoS |
| Access | Root SSH |
| Price | 1,900 DZD/month |

Design the architecture around these actual constraints.

Do not assume that advertised resources are equivalent to guaranteed application performance. Verify the VPS configuration, virtualization, available disk space, CPU limits, operating system, network configuration, and resource usage.

### Infrastructure requirements

- Prefer a lightweight deployment architecture.
- Avoid Kubernetes.
- Avoid unnecessary microservices.
- Avoid multiple redundant databases.
- Avoid unnecessary Redis, Elasticsearch, Kafka, or other infrastructure unless a measurable requirement justifies them.
- Use a lightweight reverse proxy such as Nginx or Caddy.
- Use a suitable relational database, preferably PostgreSQL if compatible with the existing project.
- Optimize database connections and queries.
- Use background jobs only when necessary.
- Configure application logging and log rotation.
- Configure automatic security updates appropriately.
- Use HTTPS with automatic certificate renewal.
- Configure firewall rules and restrict management access.
- Monitor RAM, CPU, storage, database performance, and disk usage.

Use the simplest architecture that reliably supports the actual business requirements.

### Resource limitation

The 2 GB RAM and 1 vCore VPS must be treated as a constrained production environment.

Do not attempt to run a heavy stack simply because the VPS can technically start it.

Measure memory consumption and CPU usage during realistic workflows.

Determine whether the VPS can safely handle:
- The website.
- The CMS API.
- The database.
- Authentication.
- Image and file delivery.
- Background synchronization.
- Reports and exports.
- Multiple concurrent users.

If the combined workload exceeds safe limits, recommend a concrete upgrade or service separation based on measurements.

Do not promise unlimited scalability on this VPS.

---

# PART 2 — TWO CONNECTED OPERATING ENVIRONMENTS

## 2. Separate local retail operations from online operations

This is one of the most important architectural decisions.

The physical store must not stop working simply because the internet connection or VPS becomes unavailable.

Design a hybrid architecture.

### Cloud environment

The VPS hosts:
- Public e-commerce website.
- Central application API.
- Central product catalog.
- Online order processing.
- Website administration services.
- Centralized synchronization.
- Backup coordination.
- Business data accessible to authorized remote administrators.

### Local store environment

The physical store must have a local operating environment that can continue essential operations without internet access.

Evaluate the best implementation for the existing project:

- Windows desktop application using Tauri or Electron.
- Local network application with a lightweight local server.
- Desktop POS connected to a local database.
- A local hardware integration service that communicates with USB and network devices.

Choose based on the existing stack and real technical requirements.

Do not force a browser-only application to perform tasks that browsers cannot reliably perform.

### Local operation requirements

The physical store must be able to continue:
- Opening the POS.
- Searching locally available products.
- Scanning barcodes.
- Creating sales.
- Printing receipts.
- Managing local stock movements.
- Registering payments.
- Handling cash operations.
- Recording customer information.
- Managing essential purchases and inventory operations.

Operations must be saved locally and synchronized when the internet returns.

### Critical offline architecture

Implement:
- A local persistent database.
- A durable synchronization queue.
- Unique transaction IDs.
- Idempotent synchronization requests.
- Retry mechanisms.
- Conflict detection.
- Safe recovery after application or computer restarts.
- Synchronization status visibility.
- Clear pending, synchronized, and failed operation states.

Never silently discard local sales or inventory changes.

Never synchronize the same sale twice.

Define how conflicting online and local stock changes are reconciled.

For example, if an online order and a physical-store sale attempt to purchase the last unit of a product, the system must have a defined reservation and reconciliation strategy.

Do not simply overwrite the newest database value with whichever synchronization request arrives last.

Document the source of truth for products, prices, orders, and inventory.

---

# PART 3 — COMPLETE LOCAL STORE MANAGEMENT SYSTEM

## 3. Build a real POS (Point of Sale)

The CMS must evolve into a functional retail POS.

Create a dedicated POS workspace optimized for fast daily transactions.

### POS interface

Include:
- Product search.
- Barcode scanning.
- Product categories.
- Product cards.
- Product images.
- Product variant selection.
- Cart.
- Quantity controls.
- Discounts where authorized.
- Customer selection.
- Payment method selection.
- Transaction totals.
- Receipt generation.
- Order confirmation.

The interface should be fast and practical for a cashier.

Support keyboard shortcuts and barcode-scanner workflows where appropriate.

Avoid unnecessary dialogs and excessive clicks.

### Sales workflow

A typical sale must work as follows:

1. Cashier opens a new transaction.
2. Scans a product barcode or searches for a product.
3. Product is added to the cart.
4. Selects the correct color, size, or variant if necessary.
5. Adjusts quantities.
6. Adds a customer if required.
7. Applies an authorized discount if applicable.
8. Selects payment method.
9. Confirms payment.
10. System creates the sale transaction.
11. Inventory is updated safely.
12. Receipt is generated and printed.
13. Transaction is saved locally.
14. Transaction synchronizes with the cloud when available.

Support cancellation, returns, refunds, and correction workflows with proper permissions and audit records.

Do not allow completed sales to be silently edited or deleted.

Use reversal transactions or controlled correction procedures.

---

## 4. Complete Inventory and Warehouse Management

The inventory system must manage physical products, not just website listings.

Implement:

- Product catalog.
- Product variants.
- SKU management.
- Barcode management.
- Stock by variant.
- Stock by location or warehouse.
- Stock reservations.
- Incoming stock.
- Outgoing stock.
- Manual stock adjustments.
- Damaged products.
- Returned products.
- Low-stock alerts.
- Inventory valuation.
- Stock movement history.
- Physical inventory counting.
- Stock reconciliation.
- Transfer between locations where supported.

### Product variants

Every product must support dynamically configured attributes.

Examples:
- T-shirts: color, size, fabric.
- Shoes: color, size, material.
- Bags: color, dimensions, material.
- Watches: model, strap color, material.
- Makeup: shade, volume.
- Glasses: frame color, frame style.

Every valid combination must have an independently manageable stock quantity.

Do not hardcode colors, sizes, brands, or category types.

The category defines the configurable attribute template; each product defines its actual options; each valid variant owns its inventory.

### Stock calculation

Implement reliable calculations for:
- Total stock.
- Available stock.
- Reserved stock.
- Incoming stock.
- Sold quantity.
- Damaged quantity.
- Returned quantity.

Do not calculate inventory using arbitrary frontend values.

Stock must be derived from validated backend transactions and movements.

---

# PART 4 — HARDWARE AND DEVICE MANAGEMENT

## 5. Build a Device Management Module

The CMS must manage the physical devices used by the shop.

Create a dedicated section named something like:

**Devices & Hardware Management**

The administrator should be able to register, configure, test, and monitor store devices.

### Supported device types

**A. Receipt printers**
- USB thermal printers.
- Network thermal printers.
- ESC/POS-compatible printers.
- Windows-installed printers.
- Supported laser or inkjet printers for full-page documents.

Features:
- Device registration.
- Connection configuration.
- Default printer selection.
- Receipt paper width configuration.
- Print test.
- Receipt preview.
- Printer status where supported.
- Print failure reporting.
- Reprint authorized receipts.

**B. Barcode scanners**
- USB barcode scanners.
- Keyboard-wedge scanners.
- Supported HID scanners.
- Network scanners where compatible.

Features:
- Scanner registration.
- Input testing.
- Barcode format support.
- Prefix and suffix configuration where required.
- Barcode-to-product lookup.
- Duplicate scan protection.
- Unknown barcode handling.

Remember that many USB barcode scanners behave like keyboards. Detect and support this workflow instead of assuming every scanner requires a special driver.

**C. Barcode label printers**

Support:
- Product barcode labels.
- SKU labels.
- Variant labels.
- Price labels.
- Configurable label dimensions.
- Label quantity.
- Print preview.
- Supported printer-specific formatting.

**D. Other store devices**

Allow registration of:
- Cash drawers.
- Customer displays.
- Weighing scales if supported.
- Network printers.
- Other peripherals through documented integrations.

Do not claim a device is supported without implementing and testing its integration.

### Device detection and hardware access

A normal web browser cannot freely enumerate or control every USB device or Windows printer.

Implement the correct architecture for local hardware access.

Evaluate:
- A lightweight local hardware bridge/service.
- Tauri desktop integration.
- Electron main-process device integration.
- Windows printing APIs.
- Supported browser APIs where appropriate.
- Network printer communication where supported.

The cloud website should communicate with the local device bridge only through a secure, authenticated mechanism.

Never expose unrestricted device access to remote websites.

### Device status

Display:
- Registered device.
- Connection status.
- Device type.
- Location.
- Default device.
- Last successful test.
- Supported capabilities.
- Recent errors.

If a device cannot be detected, explain why and provide a troubleshooting procedure.

Do not fabricate device status.

---

# PART 5 — BARCODE AND PRODUCT IDENTIFICATION

## 6. Complete Barcode Management

Every product or variant can have its own barcode.

Implement:
- Barcode generation where appropriate.
- Barcode assignment.
- Barcode scanning.
- Barcode validation.
- Duplicate barcode prevention.
- Barcode printing.
- Barcode search.
- Barcode-to-variant mapping.
- Product label templates.

Support common retail barcode formats where practical, including EAN-13, EAN-8, UPC-A, and Code 128.

Do not generate invalid identifiers or pretend that an internally generated barcode is a registered GS1 identifier.

Support internal store barcodes separately from externally registered product identifiers.

A scanned barcode must resolve to the correct product and variant.

If it is unknown, offer a controlled workflow to register or associate it with a product.

---

# PART 6 — PURCHASING, SUPPLIERS AND RECEIVING

## 7. Supplier and Purchase Management

Create a complete supplier management module.

Store:
- Supplier name.
- Contact information.
- Address.
- Business details where relevant.
- Notes.
- Purchase history.
- Outstanding balances where applicable.

### Purchase workflow

1. Select supplier.
2. Create purchase order or purchase document.
3. Add products and variants.
4. Enter quantities.
5. Enter purchase prices.
6. Calculate totals.
7. Record payment status.
8. Confirm receipt of merchandise.
9. Update stock through inventory movements.
10. Record supplier balance changes.

Support:
- Draft purchases.
- Confirmed purchases.
- Partially received purchases.
- Fully received purchases.
- Cancelled purchases.
- Purchase returns.
- Supplier payments.
- Purchase history.

Do not increase stock simply because a purchase document was drafted. Stock should update through the appropriate receiving operation.

---

# PART 7 — CUSTOMERS AND CUSTOMER MANAGEMENT

## 8. Customer Management

Build a practical customer module.

Include:
- Customer name.
- Phone number.
- Optional email.
- Address.
- Purchase history.
- Orders.
- Returns.
- Payment history where applicable.
- Notes.
- Outstanding balances where credit sales are supported.

Support both walk-in customers and registered customers.

Do not force every physical-store customer to create an online account.

Avoid unnecessary collection of personal information.

Implement appropriate privacy controls and access permissions.

---

# PART 8 — ALGERIAN RETAIL ACCOUNTING AND FINANCIAL OPERATIONS

## 9. Build a Practical Financial Management Module

The system must reflect the needs of a real Algerian retail business.

Use:
- Algerian dinar (DZD) as the primary currency.
- French and Arabic financial terminology where appropriate.
- Localized dates and number formatting.
- Configurable tax settings.
- Purchase and selling price calculations.
- Sales and purchase reports.
- Cash register operations.
- Payment tracking.

Do not hardcode tax rates, fiscal rules, or invoice requirements without verification. Make fiscal settings configurable and document that formal accounting and compliance must be validated against current Algerian regulations by a qualified accountant.

### Financial modules

Implement:
- Sales revenue.
- Purchase expenses.
- Operating expenses.
- Gross margin.
- Profit calculations.
- Cash register.
- Cash opening balance.
- Cash closing balance.
- Cash deposits and withdrawals.
- Cash differences.
- Payment methods.
- Customer balances where applicable.
- Supplier balances.
- Refunds.
- Returns.
- Financial transaction history.

### Payment methods

Support configurable methods such as:
- Cash.
- Bank card.
- Bank transfer.
- Online payment.
- Other payment methods configured by the administrator.

Do not assume every payment method is connected to a real payment gateway.

### Financial calculations

Clearly distinguish:
- Purchase price.
- Selling price.
- Discount.
- Net amount.
- Configured taxes.
- Gross margin.
- Operating expenses.
- Realized profit.

Use decimal-safe monetary calculations. Avoid floating-point rounding errors in financial logic.

### Documents and reports

Support appropriate business documents:
- Sales receipts.
- Sales invoices.
- Purchase documents.
- Delivery notes.
- Quotes.
- Returns and credit documents where applicable.
- Inventory reports.
- Sales reports.
- Purchase reports.
- Cash register reports.
- Profitability reports.

Implement configurable document numbering and proper auditability. Do not claim official fiscal compliance without verification.

---

# PART 9 — ONLINE E-COMMERCE INTEGRATION

## 10. Make the CMS Control the Complete Website

The existing e-commerce website must remain fully operational and controlled through the CMS.

The administrator must manage:
- Homepage content.
- Navigation.
- Categories.
- Products.
- Product images.
- Brands.
- Colors.
- Sizes.
- Variants.
- Prices.
- Discounts.
- Inventory.
- Featured products.
- Banners.
- Store information.
- Orders.
- Customers.
- Delivery configuration.
- Promotional campaigns.

CMS changes must be reflected on the website through the existing API and synchronization architecture.

Do not duplicate product databases.

The physical store and website must share the appropriate catalog and inventory data.

### Online orders

Implement:
- New order notifications.
- Order status management.
- Customer details.
- Product and variant details.
- Payment status.
- Delivery details.
- Cancellation.
- Returns.
- Refund tracking.
- Order history.

Support the Algerian cash-on-delivery workflow, including configurable delivery fees and delivery status.

Allow delivery configuration by wilaya and commune where appropriate.

Do not hardcode the 69 wilayas or shipping prices into the frontend. Make the delivery configuration manageable through the CMS.

### Online and physical inventory

Define safe stock reservation and deduction rules.

Example:

A T-shirt has 10 units in size M.

- An online customer places an order for 2 units.
- The online system reserves those units according to the configured order policy.
- A physical customer purchases 3 units.
- The local POS updates its inventory.
- The cloud synchronization process reconciles both transactions.

The system must never silently oversell.

Define reservation expiry, cancelled order release, completed sale deduction, and offline conflict handling.

---

# PART 10 — BUSINESS DASHBOARD AND REPORTING

## 11. Build a Real Business Dashboard

The dashboard should provide an accurate overview of the entire business.

Include:
- Today's sales.
- Monthly sales.
- Online sales.
- Physical-store sales.
- Number of orders.
- Average order value.
- Best-selling products.
- Low-stock products.
- Inventory valuation.
- Purchase expenses.
- Gross margins.
- Cash register status.
- Pending orders.
- Pending deliveries.
- Supplier balances.
- Synchronization status.
- Device health.

Provide meaningful date filters and report exports.

All metrics must be calculated from real database records.

Clearly distinguish revenue, gross margin, and net profit. Never present them as interchangeable.

Do not add fake charts or hardcoded numbers.

---

# PART 11 — USERS, ROLES AND PERMISSIONS

## 12. Multi-User Retail Management

Build proper role-based access control.

Suggested roles:

- Owner / Super Administrator.
- Store Manager.
- Cashier.
- Inventory Manager.
- Purchasing Manager.
- Accountant.
- Website Manager.

Allow the owner to configure permissions.

Examples:
- Cashiers can create sales but cannot edit purchase prices.
- Inventory managers can update stock but cannot change financial settings.
- Website managers can manage website content but cannot access sensitive financial data.
- Accountants can access authorized reports but cannot change product inventory without permission.

Enforce permissions on the backend, not just by hiding interface elements.

Maintain audit logs for important operations:
- Price changes.
- Stock adjustments.
- Sales cancellations.
- Refunds.
- User permission changes.
- Financial operations.
- Product deletion or archiving.

Include timestamps, user IDs, action details, and relevant record identifiers.

---

# PART 12 — NETWORKING AND LOCAL STORE CONNECTIVITY

## 13. Design the Store's Local Network Integration

Evaluate how the store computers and devices should communicate.

Support a practical LAN configuration.

Possible architecture:

- Main local POS computer or local server.
- Cashier computers.
- Local printer devices.
- Barcode scanners.
- Administrative workstation.
- Optional Wi-Fi-connected devices.

The system should support multiple authorized local terminals where the hardware and architecture permit.

Implement:
- Secure local service communication.
- Device registration.
- Local network configuration.
- Health checks.
- Connection monitoring.
- Controlled remote administration.
- Secure synchronization with the cloud.
- Recovery after network interruption.

Do not expose the local database or hardware-control service directly to the public internet.

Use authentication, access restrictions, and encrypted communication where appropriate.

Document required network ports and firewall rules.

Do not assume that every device connected to Wi-Fi is automatically trusted.

---

# PART 13 — SECURITY AND DATA PROTECTION

## 14. Conduct a Complete Security Audit

Treat the application as a real commercial system containing financial, customer, and inventory data.

Audit:
- Authentication.
- Session handling.
- Authorization.
- Password storage.
- API security.
- Database permissions.
- SQL injection.
- Cross-site scripting.
- CSRF where applicable.
- SSRF where applicable.
- File upload security.
- Rate limiting.
- Input validation.
- Secret management.
- Dependency vulnerabilities.
- Backup protection.
- Audit logging.
- Local device bridge security.
- Offline data protection.
- Synchronization integrity.

### VPS hardening

Implement:
- SSH key authentication.
- Disable direct root SSH login after establishing a secure administrative account and verifying access.
- Restrict SSH access where feasible.
- Firewall configuration.
- HTTPS.
- Automatic security updates.
- Secure database binding.
- Non-root application processes.
- Log rotation.
- Monitoring.
- Secure backup storage.

Do not lock yourself out of the VPS while changing SSH or firewall settings. Verify an alternative administrative session before applying restrictive changes.

Never expose PostgreSQL directly to the public internet.

Never commit `.env` files, passwords, API keys, private keys, or database credentials.

### Backup and disaster recovery

Implement:
- Automatic database backups.
- File and image backups.
- Encrypted off-server backup copies.
- Backup retention policies.
- Backup monitoring.
- Restoration procedures.
- Local database backup.
- Recovery after power failure.
- Recovery after VPS failure.

Test restoration, not just backup creation.

Define realistic Recovery Point Objective (RPO) and Recovery Time Objective (RTO) based on the business requirements and available infrastructure.

---

# PART 14 — ENGLISH AND ARABIC LOCALIZATION

## 15. Complete Bilingual CMS and POS

The entire management system must support English and Arabic.

Translate:
- Dashboard.
- Navigation.
- Products.
- Categories.
- Variants.
- Inventory.
- POS.
- Devices.
- Purchases.
- Suppliers.
- Customers.
- Orders.
- Accounting.
- Reports.
- Settings.
- Notifications.
- Errors.
- Forms.
- Tables.
- Dialogs.

### Arabic RTL

Implement genuine RTL support:
- Correct document direction.
- Proper sidebar placement.
- Correct navigation orientation.
- Correct form alignment.
- Proper modal and dropdown positioning.
- Correct table layout.
- Appropriate icon mirroring.
- Arabic-capable fonts.
- Correct mixed Arabic/English text handling.

Preserve SKUs, barcodes, serial numbers, email addresses, and URLs.

Persist language preferences and test both directions on every major module.

The storefront and CMS must not become inconsistent when switching languages.

---

# PART 15 — ARCHITECTURE AND CODE QUALITY

## 16. Rebuild Weak Areas Properly

Inspect the existing architecture and identify what needs refactoring.

Maintain clear separation between:
- Frontend presentation.
- Application workflows.
- Business domain logic.
- Database access.
- API endpoints.
- Hardware integration.
- Local synchronization.
- Cloud synchronization.
- Authentication and authorization.
- Reporting and financial calculations.

Use appropriate abstractions, strong typing, validation schemas, and reusable components.

Avoid:
- Giant components.
- Giant API controllers.
- Duplicated business logic.
- Circular dependencies.
- Hardcoded business rules.
- Unnecessary dependencies.
- Unnecessary microservices.
- Fake API implementations.
- In-memory-only inventory.
- Direct database access from frontend components.
- Excessive background processes.

Create documentation for important architecture decisions and integration contracts.

Do not rewrite working modules just to make the code look different.

---

# PART 16 — TESTING AND REAL-WORLD VERIFICATION

## 17. Test the Complete Business, Not Just the Website

Build a comprehensive test plan.

### Product and inventory tests
- Create categories.
- Create products.
- Add arbitrary colors and sizes.
- Create valid variants.
- Assign individual stock quantities.
- Assign barcodes.
- Modify stock.
- Transfer stock where supported.
- Receive purchases.
- Register damaged products.
- Process returns.
- Reconcile inventory.

### POS tests
- Scan a barcode.
- Search for a product.
- Add multiple variants.
- Process a cash sale.
- Process another configured payment type.
- Print a receipt.
- Cancel an authorized transaction.
- Process a return.
- Close the cash register.
- Reconcile cash differences.

### Hardware tests
- Detect a registered or supported printer.
- Print a test receipt.
- Print a barcode label.
- Test barcode scanning.
- Disconnect a device and verify status handling.
- Reconnect and verify recovery.
- Test unsupported hardware and show an accurate error.

### E-commerce tests
- Publish a product.
- Verify storefront availability.
- Place an online order.
- Reserve stock correctly.
- Update order status.
- Cancel an order.
- Release eligible reservations.
- Synchronize physical and online inventory.
- Verify that no overselling occurs.

### Offline tests
- Disconnect internet access.
- Create physical-store sales.
- Print receipts.
- Update local inventory.
- Restart the application.
- Restore internet access.
- Synchronize pending operations.
- Verify that every transaction appears exactly once.
- Verify conflict handling.

### Financial tests
- Purchase cost calculations.
- Selling price calculations.
- Discounts.
- Gross margins.
- Payment totals.
- Cash opening and closing.
- Refunds.
- Supplier balances.
- Financial reports.

### Security tests
- Unauthorized API access.
- Invalid permissions.
- Invalid inputs.
- Duplicate requests.
- File upload validation.
- Session expiration.
- Synchronization replay attempts.
- Backup restoration.

Use automated unit, integration, and end-to-end testing where practical.

Never run destructive tests against production data.

---

# PART 17 — IMPLEMENTATION PLAN

## 18. Work in Phases

Do not attempt to implement the entire ERP in one uncontrolled code change.

Follow these phases:

**Phase 1 — Audit**
- Inspect the repository.
- Map existing functionality.
- Review architecture and database.
- Identify critical security and reliability issues.
- Measure the VPS resource constraints.
- Identify missing modules and hardware requirements.

**Phase 2 — Architecture**
- Define the cloud and local environments.
- Define the synchronization model.
- Define data ownership.
- Define product, variant, inventory, order, and financial data models.
- Define hardware integration.
- Document migration and deployment plans.

**Phase 3 — Core retail management**
- Products.
- Categories.
- Variants.
- Inventory.
- Suppliers.
- Purchases.
- Customers.

**Phase 4 — Local POS and hardware**
- POS interface.
- Barcode scanning.
- Receipt printing.
- Barcode label printing.
- Device management.
- Cash register.

**Phase 5 — Online integration**
- Website synchronization.
- Online orders.
- Delivery.
- Stock reservations.
- Customer and order management.

**Phase 6 — Accounting and reporting**
- Sales and purchases.
- Expenses.
- Cash management.
- Financial reporting.
- Document generation.

**Phase 7 — Security and offline synchronization**
- Offline transactions.
- Synchronization queue.
- Conflict resolution.
- Backup and restore.
- Permissions and audit logs.

**Phase 8 — UX, localization and QA**
- Complete CMS redesign.
- English and Arabic.
- RTL.
- Desktop and mobile testing.
- Hardware testing.
- Regression tests.

**Phase 9 — Production deployment**
- VPS hardening.
- Database deployment.
- HTTPS.
- Backup automation.
- Monitoring.
- Production configuration.
- Recovery testing.

Implement in manageable, tested increments. Do not leave the application in a broken state between phases.

---

# PART 18 — RULES FOR CLAUDE

## 19. How you must work

1. Start by understanding the existing repository completely.
2. Do not assume technologies or dependencies without inspecting them.
3. Do not destroy existing data.
4. Do not replace working functionality with mockups.
5. Do not implement hardware support using fake detection.
6. Do not expose local hardware or databases publicly.
7. Do not hardcode business rules that should be configurable.
8. Do not introduce unnecessary infrastructure.
9. Do not claim that tests passed without executing them.
10. Do not deploy experimental changes directly to production.
11. Use database migrations and maintain rollback options.
12. Keep documentation updated.
13. Test every important workflow after implementation.
14. Fix root causes rather than hiding errors.
15. Prioritize data integrity, security, and business continuity.

When an implementation is blocked by missing hardware, credentials, API access, or infrastructure, explain precisely what is missing and provide a safe test alternative.

You may use mocks for automated testing, but never present a mock as real device detection or a real production integration.

## 20. Final deliverables

Produce:

1. Complete architecture assessment.
2. Existing-versus-proposed architecture comparison.
3. Database schema and migration plan.
4. Cloud/local synchronization design.
5. Hardware compatibility and integration report.
6. VPS deployment and resource assessment.
7. Security audit report.
8. Implementation plan and completed modules.
9. Automated test results.
10. Backup and disaster recovery documentation.
11. Network configuration documentation.
12. Production deployment instructions.
13. Remaining limitations and recommended hardware upgrades.

## FINAL OBJECTIVE

Build Mus Luxury into a professional, secure, maintainable retail management platform that can manage a real physical shop in Algeria and its online store from one connected system.

The owner must be able to open the application every morning, manage stock, receive products from suppliers, sell through the POS, scan barcodes, print receipts, manage customers, monitor finances, manage website orders, and operate essential store functions even when the internet is unavailable.

The online store and physical store must share accurate business data without compromising availability, security, or inventory integrity.

**Do not build a pretty dashboard pretending to be an ERP. Build the actual business operations, with working backend logic, database persistence, hardware integrations, reliable synchronization, and tested workflows.**