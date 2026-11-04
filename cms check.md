# MUS LUXURY — FULL SYSTEM AUDIT, CMS UX/UI OVERHAUL, BACKEND VERIFICATION & BILINGUAL LOCALIZATION

## Role and mission

Act as a senior full-stack engineer, software architect, QA automation engineer, UX auditor, accessibility specialist, and application security engineer.

Work directly on the existing Mus Luxury repository.

Your mission is to perform a complete technical and functional audit of the entire application, including:

- The CMS administration software.
- The public e-commerce storefront.
- Every page, form, button, link, dropdown, modal, menu, tab, filter, and interactive component.
- All frontend-to-backend connections.
- Database operations, authentication, authorization, and persistence.
- Product management, categories, variants, colors, sizes, brands, inventory, pricing, orders, customers, and existing accounting features.
- Desktop, tablet, and mobile experiences.
- English and Arabic localization, including proper right-to-left layout.
- Performance, accessibility, runtime errors, UI instability, and regression testing.

**Do not assume the application works because it looks good or because the development server starts. Verify actual behavior.**

Inspect the code, execute real workflows, identify defects, fix them, and retest. Do not replace functional implementations with mock data or superficial UI changes.

---

## 1. Perform a Complete Repository and Architecture Audit

Before modifying anything, inspect the actual project.

Identify:
- Frontend framework, routing, component architecture, and state management.
- Backend framework, API endpoints, authentication, and business logic.
- Database schema, relationships, migrations, constraints, and transaction handling.
- CMS-to-backend and storefront-to-backend communication.
- File uploads, image storage, configuration, and environment variables.
- Existing localization, translation files, and language-selection behavior.
- Existing tests, build scripts, linting, and type-checking tools.
- Dependencies, obsolete code, duplicated logic, and known technical debt.

Map every major CMS module to its frontend components, API endpoints, and database operations.

Create an internal checklist of all routes, interactive elements, and important user workflows. Use it to ensure that no major part of the application is overlooked.

Preserve working features and existing data. Do not perform destructive database resets or unnecessary framework migrations.

## 2. Audit and Repair the Entire CMS UX/UI

The CMS must be a professional, intuitive store-management application that a non-technical administrator can use comfortably.

Review every screen, not just the dashboard or product editor.

### Visual consistency
- Establish a consistent design system for colors, typography, spacing, sizing, borders, shadows, icons, and interaction states.
- Use the existing Mus Luxury brand identity.
- Remove inconsistent spacing, misaligned elements, unnecessary decoration, and conflicting styles.
- Fix overcrowded forms, oversized controls, awkward empty spaces, and poor visual hierarchy.
- Ensure that tables, cards, dialogs, forms, and navigation follow consistent patterns.
- Use clear headings and understandable terminology.
- Make important information easy to scan.
- Keep advanced controls organized without overwhelming the user.

### Workflow usability
- Reduce unnecessary clicks and navigation.
- Provide contextual actions where appropriate.
- Use searchable, creatable selectors for configurable product attributes.
- Allow administrators to create custom colors, sizes, brands, categories, and attributes.
- Provide inline editing and bulk operations where useful.
- Preserve user input when validation fails.
- Warn about unsaved changes.
- Confirm destructive operations.
- Display clear success, error, loading, empty, and disabled states.
- Prevent duplicate submissions and accidental repeated actions.

### Responsive administration
Test the CMS at desktop, tablet, and mobile widths.

Tables must remain usable through responsive columns, horizontal scrolling where appropriate, or a deliberate alternative layout. Forms and dialogs must fit the available viewport. Menus must not cover essential actions.

Do not force desktop-only layouts onto mobile screens.

## 3. Audit Every Single Button and Interactive Element

Create an inventory of interactive controls across the CMS and storefront.

Include:
- Buttons.
- Text links.
- Icon buttons.
- Sidebar navigation.
- Tabs and segmented controls.
- Dropdowns and searchable selectors.
- Color pickers and size selectors.
- Checkboxes, radio buttons, and switches.
- Search and filter controls.
- Pagination.
- Sorting controls.
- Modal dialogs and confirmation prompts.
- Image upload, preview, replacement, and removal actions.
- Save, cancel, create, update, delete, publish, and archive operations.
- Cart, wishlist, quantity, variant, and checkout controls.
- Language selectors.
- Export, import, backup, and reporting actions, where implemented.

For every interactive element, verify:

1. It is visible when it should be.
2. Its label communicates the action.
3. It responds correctly to mouse, touch, and keyboard input where applicable.
4. It invokes the intended handler.
5. It updates the correct state.
6. It calls the correct API when necessary.
7. It handles loading and prevents accidental duplicate submissions.
8. It reports success only after the operation succeeds.
9. It handles server errors and invalid input properly.
10. It does not trigger unrelated actions.
11. It does not silently fail.
12. It remains usable after navigation, refresh, or reopening the relevant screen.

A button that only changes its appearance is not functional. A button that displays a success notification without completing its intended operation is not functional.

Remove placeholder `href="#"` links, empty handlers, dead controls, and misleading actions. If a feature is not implemented, either implement it properly or clearly indicate its status without pretending it works.

Do not make destructive operations active merely to satisfy a button test.

## 4. Verify Every Frontend-to-Backend Connection

Trace the complete lifecycle of every important operation.

For each feature, verify:

**User action → frontend validation → API request → backend validation → database operation → API response → frontend state update → persisted result.**

Test actual database persistence, not just frontend state changes.

### Required checks
- Correct API endpoint and HTTP method.
- Correct request payload and response handling.
- Authentication headers and session behavior.
- Server-side validation.
- Authorization for administrative actions.
- Database transactions and constraint enforcement.
- Correct error handling for failed requests.
- Loading and disabled states during requests.
- Refresh behavior after successful changes.
- Correct synchronization between CMS and storefront.
- Consistent handling of network disconnections and timeouts.

Verify that changes remain correct after navigating away and returning, refreshing the page, or reopening the application where persistence is expected.

Do not hide API failures with fallback mock data.

Do not expose database credentials, secrets, stack traces, internal server details, or sensitive information in frontend errors.

### Feature-specific integration tests

Test the actual application workflows for:
- Creating, editing, publishing, unpublishing, and archiving products.
- Creating categories and custom attributes.
- Managing colors, sizes, brands, images, and variants.
- Editing prices, discounts, and stock.
- Searching, filtering, and sorting products.
- Creating and managing orders.
- Customer management where implemented.
- Sales, purchase costs, profit calculations, and accounting features where implemented.
- Exporting and importing data where implemented.
- Updating storefront settings, banners, and store information.
- Cart, wishlist, checkout, and order tracking.
- English and Arabic language preferences.

Do not claim that an integration works until the relevant request and resulting state have been verified.

## 5. Eliminate UI Shaking, Flickering, Layout Shifts, and Visual Bugs

Perform a dedicated visual-stability audit.

Inspect the application during:
- Initial page loading.
- Navigation between routes.
- API requests and responses.
- Opening and closing dialogs.
- Dropdown interactions.
- Image loading.
- Table updates.
- Form validation.
- Switching languages.
- Switching between LTR and RTL layouts.
- Changing viewport sizes.
- Adding or removing products and variants.
- Updating cart quantities.
- Scrolling with sticky headers or navigation.

### Detect and fix
- Layout shifts caused by images without reserved dimensions.
- Content jumping when fonts load.
- Headers changing height unexpectedly.
- Sidebar or navigation flicker.
- Horizontal overflow.
- Incorrect scroll restoration.
- Modal positioning issues.
- Dropdowns appearing behind other elements.
- Unstable table columns.
- Incorrect or missing React keys.
- Unnecessary rerenders.
- Repeated API requests.
- State updates after components are unmounted.
- Race conditions and stale asynchronous responses.
- Animation conflicts.
- CSS transitions causing unwanted movement.
- Focus loss and unexpected scroll jumps.
- Content disappearing during loading.
- Errors caused by missing or malformed API data.

Use browser developer tools and automated visual testing where available. Inspect browser console errors and failed network requests.

Avoid arbitrary timeouts, forced reflows, and CSS hacks that conceal underlying defects.

Use stable layout dimensions, appropriate loading skeletons, predictable state transitions, and deliberate animation.

Respect `prefers-reduced-motion`. Motion must never interfere with usability.

## 6. Implement Complete English and Arabic Localization Throughout the CMS

Add complete English and Arabic language support to the entire administration application, not merely the login screen or sidebar.

### Language selection
- Provide a clearly visible language selector in the CMS.
- Allow the administrator to switch between English and Arabic.
- Preserve the selected language across routes and refreshes.
- Persist the preference using the existing user settings or a suitable local preference mechanism.
- Use English or the existing default language for the first visit according to the project's established behavior.
- Avoid requiring a page reload unless the architecture genuinely requires one.

### Translation coverage

Translate every user-facing CMS string, including:
- Navigation and page titles.
- Dashboard metrics and descriptions.
- Buttons, links, menus, and tooltips.
- Forms, field labels, placeholders, and helper text.
- Validation errors and confirmation dialogs.
- Tables, filters, sorting, and pagination.
- Product and variant management.
- Colors, sizes, brands, and categories.
- Inventory, pricing, orders, and customers.
- Reports, accounting, and settings.
- Notifications, loading states, empty states, and server errors.
- Authentication, permission errors, and session-expiration messages.
- Date, number, currency, and status formatting where applicable.

Search the source code for hardcoded user-facing strings and migrate them to a consistent localization system.

Do not leave random English strings inside the Arabic interface or translate only a subset of the pages.

Use translation keys with consistent naming, organized language dictionaries, interpolation support, and a clear fallback strategy. Reuse an existing internationalization library if one is already installed and suitable.

Do not translate product names, brand names, SKUs, or user-entered content automatically unless the application explicitly supports translated content fields.

### Arabic RTL layout

Arabic must be a properly designed right-to-left interface, not simply English text aligned to the right.

When Arabic is active:
- Set the correct document language and text direction.
- Use `dir="rtl"` or the appropriate framework-level direction mechanism.
- Mirror directional navigation, sidebars, breadcrumbs, and arrows when appropriate.
- Reverse directional icons only when their meaning is directional.
- Align labels, form controls, and text correctly.
- Ensure dropdowns, popovers, tooltips, modals, and menus open in appropriate positions.
- Ensure tables and action columns remain usable.
- Handle mixed Arabic and English text, email addresses, SKUs, URLs, and numbers correctly.
- Use logical CSS properties such as `margin-inline-start` and `padding-inline-end` instead of unnecessary left/right-specific styles.
- Prevent punctuation, currency symbols, and numeric values from displaying incorrectly.
- Select appropriate fonts with good Arabic glyph coverage.
- Preserve consistent spacing and typography across both directions.
- Verify that icons and logos are not incorrectly mirrored.

Test both LTR and RTL at every important breakpoint.

### Translation quality

Use clear, natural Arabic suitable for an administration application.

Avoid awkward literal translations, mixed-language labels, broken plurals, inconsistent terminology, and untranslated notifications.

Keep technical identifiers and user-entered product data intact.

## 7. Keep English and Arabic Support Compatible With the Storefront

Audit the existing storefront language selector and make sure language switching works consistently across the public website and CMS where intended.

Verify:
- All advertised languages are actually available.
- Navigation labels and buttons are translated.
- Product option labels and category interfaces use the correct language where translations exist.
- Forms and checkout errors are localized.
- Arabic storefront layouts render correctly in RTL.
- Cart, search, filters, dialogs, and mobile navigation remain usable in both directions.
- Switching language preserves the current page and relevant shopping state.
- Language switching does not corrupt URLs, selected variants, cart quantities, or form input.
- CMS-managed content follows the application's existing translation model.

Do not pretend that product descriptions or store content are translated when no translation exists. Define a sensible fallback or implement the necessary content fields where required.

## 8. Verify Data Integrity and Business Logic

Review the backend and database for correctness.

Check:
- Product and variant relationships.
- Unique SKU and variant constraints where applicable.
- Valid prices and discounts.
- Stock quantity validation.
- Category and attribute references.
- Image metadata and upload validation.
- Referential integrity.
- Historical order records.
- Transaction handling.
- Concurrent inventory updates.
- Duplicate order submission protection.
- Correct financial calculations.
- Safe handling of archived or deleted records.
- Consistent data across CMS and storefront.

Prices and stock must be validated on the server. Never trust client-submitted values as authoritative.

Verify that concurrent orders cannot oversell limited stock. Ensure inventory updates and order creation are transaction-safe and appropriately idempotent.

Do not change historical order prices or product snapshots when an administrator edits a current product.

## 9. Run a Security and Permissions Audit

Inspect administrative and public API boundaries.

Verify:
- Authentication is enforced on protected endpoints.
- Authorization checks prevent users from performing actions outside their permissions.
- Public storefront endpoints expose only intended data.
- Sensitive information is not returned to unauthorized clients.
- Inputs are validated and safely handled.
- File uploads restrict unsafe types, sizes, and paths.
- Secrets are not committed to source code.
- Administrative actions cannot be performed merely by hiding buttons in the frontend.
- CORS, session handling, and security headers are appropriate for the existing deployment.
- Errors do not leak sensitive internals.
- Dependencies are checked using the project's available security tooling.

Fix verified vulnerabilities without performing destructive security tests against production systems.

## 10. Create and Execute an Automated Test Plan

Use the existing test framework where possible. Add missing tests for important workflows.

### Unit tests
Test:
- Validation rules.
- Price and discount calculations.
- Variant selection.
- Quantity handling.
- Localization helpers.
- RTL/LTR direction switching.
- State transitions.
- Permission checks and relevant business rules.

### Integration tests
Test:
- API requests and response handling.
- Database persistence.
- Product and variant CRUD.
- Category and attribute management.
- Inventory updates.
- Order creation.
- Error and timeout handling.
- Localization settings and data formatting.

### End-to-end tests
Use browser automation such as the project's existing Playwright, Cypress, or equivalent setup where available.

Test real user journeys:

1. Open the CMS and navigate through every major module.
2. Create a product with custom colors and sizes.
3. Save it and verify the database contains the correct values.
4. Refresh the application and confirm the product remains correct.
5. Publish the product and verify the storefront displays it.
6. Purchase multiple units with the same variant.
7. Purchase multiple units with different variants.
8. Attempt an invalid or unavailable combination.
9. Attempt to exceed available stock.
10. Verify the backend rejects invalid prices and unauthorized changes.
11. Update product information in the CMS and verify synchronization.
12. Switch the CMS from English to Arabic.
13. Navigate through all major CMS screens in Arabic.
14. Verify correct RTL layout, typography, forms, tables, and dialogs.
15. Switch back to English and verify the layout returns to LTR.
16. Repeat critical workflows on mobile-sized viewports.
17. Test network failures and recoverable validation errors.
18. Verify the browser console and network panel contain no unexpected failures.

Use isolated test data. Never wipe production data or perform destructive tests against a live store.

## 11. Browser-Based Visual and Interaction Testing

Run the application and inspect actual rendered pages at multiple viewport widths, including:
- 320 px.
- 375 px.
- 390 px.
- 768 px.
- 1024 px.
- 1440 px.

Test both English LTR and Arabic RTL.

Inspect every major CMS screen and storefront route for:
- Overlapping elements.
- Clipped text.
- Broken layout.
- Horizontal scrolling.
- Incorrect active navigation.
- Misplaced dialogs.
- Buttons hidden behind sticky elements.
- Unusable forms.
- Incorrect focus behavior.
- Loading flicker.
- Unexpected layout movement.
- Inconsistent typography.
- Missing icons or images.
- Incorrect language direction.

Where visual regression tooling exists, capture baseline and updated screenshots and investigate meaningful differences.

Do not blindly accept screenshots just because the page renders.

## 12. Fix Defects Until the Relevant Tests Pass

Use this cycle:

1. Reproduce the defect.
2. Identify the root cause.
3. Implement a focused correction.
4. Add or update a regression test.
5. Rerun the relevant test.
6. Check related workflows for regressions.
7. Repeat until the defect is resolved or a clearly documented external blocker remains.

Prioritize:
1. Data loss, security, and financial correctness.
2. Broken backend integrations and critical shopping workflows.
3. Broken navigation and nonfunctional buttons.
4. Localization and RTL failures.
5. Runtime errors and unstable UI.
6. Accessibility and responsive usability.
7. Visual refinement and performance.

Do not conceal failing tests, suppress errors, or claim success without evidence.

## 13. Final Completion Report

When finished, provide:

- A summary of the CMS UX/UI improvements.
- A summary of the storefront fixes.
- A list of repaired buttons, interactions, and backend integrations.
- The English and Arabic localization coverage.
- RTL and LTR verification results.
- The UI stability and responsive fixes.
- The database and security corrections.
- The exact tests executed and their results.
- Any remaining failures or blockers, with the affected feature and reason.
- Any external configuration still required.

Clearly distinguish tests that passed from tests that were not run.

## Final acceptance criteria

The project is complete only when the CMS and storefront have been audited end to end, critical controls have been tested, backend connections have been verified, English and Arabic are usable throughout the CMS, RTL and LTR layouts work correctly, and discovered defects have been corrected and retested.

**Do not stop at a successful build, a good-looking dashboard, or a partially translated interface. Test the real workflows and report the actual results.**