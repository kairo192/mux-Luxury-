# Additional Requirements — Visual Product Designer, Fully Customizable Fields, Clean Architecture, and Full Verification

Extend the previous implementation requirements. These requirements are mandatory and apply to the CMS frontend, backend, database, APIs, and storefront.

## 1. Turn the Product Editor into a Visual Product Design Workspace

Do not build a basic form with static text fields, fixed dropdowns, and hardcoded options. The product editor must feel like a professional product configuration and design application.

The administrator should be able to configure the product while seeing a clear, live preview of how it will appear on the storefront.

### Visual product configuration

Create a dedicated product editing workspace with:

- A live product card preview that updates as the administrator edits the product.
- A product image gallery with upload, preview, reordering, replacement, and removal.
- Visual color swatches displayed as circles or rounded color chips.
- Click-to-select color controls with a color picker and editable hexadecimal values.
- Customizable size selectors and variant configuration.
- Editable product name, brand, description, prices, discount, stock, and product attributes.
- A preview of available product options and their storefront presentation.
- Clear actions to add, duplicate, edit, reorder, and remove configurable items.
- A preview of product availability, discount presentation, and variant selection.
- An organized layout that separates basic information, media, variants, pricing, inventory, and advanced settings.

The preview must use the actual product data and the same relevant presentation rules as the storefront. It must not be a disconnected mockup containing hardcoded example values.

Use a split workspace where practical: editing controls on one side and a live preview on the other. On smaller screens, switch to a responsive layout without sacrificing usability.

## 2. Eliminate Hardcoded Colors, Brands, Sizes, and Product Attributes

**Nothing that should be customizable by the store owner may be restricted to a hardcoded list of predefined values.**

Do not assume that the store only uses known brands, standard colors, predefined sizes, or fixed product categories.

The system must support both optional reusable presets and completely custom values.

### Colors

Build a reusable visual color management component.

Each color should support:
- Color name, entered and edited freely.
- A circular color swatch displaying the actual selected color.
- A visual color picker.
- A manually editable HEX value.
- Optional RGB or other color input formats if useful.
- Optional color image or texture when a solid swatch is insufficient.
- Rename, duplicate, edit, remove, and reuse actions.
- Searchable selection from existing colors.
- Creating a new color directly inside the product editor without navigating away.

Example: the administrator can create "Vert sauge", select its exact color visually, and use it on any product. The system must not require this color to exist in the application beforehand.

Changing a color name or appearance must have clearly defined effects on existing products. Avoid unintentionally changing historical order records or unrelated variants.

### Sizes

Do not limit sizes to fixed options such as S, M, L, XL, or 38, 39, 40.

Allow the administrator to:
- Type any size or size label.
- Add multiple custom sizes quickly.
- Create reusable size sets.
- Define separate size sets for shoes, clothes, accessories, and other categories.
- Reorder and edit size values.
- Define custom size attributes such as dimensions, capacity, or measurements.
- Assign a distinct stock quantity to each valid variant.

Presets can improve speed, but custom entries must always remain possible.

### Brands

Do not use a hardcoded brand list.

Allow the administrator to:
- Enter any brand name.
- Create a new brand directly from the product editor.
- Upload a brand logo.
- Preview, replace, crop where supported, and remove the logo.
- Reuse existing brands through a searchable selector.
- Edit brand details and associate a brand with multiple products.
- Leave the brand empty when it is not applicable.

A new brand must be persisted in the database and immediately available to the relevant product forms.

### Custom product attributes

Create a reusable attribute builder where the administrator can define:

- Attribute name.
- Field type.
- Input options or allowed values, when applicable.
- Whether the attribute is required.
- Whether it affects product variants.
- Whether it appears on the storefront.
- Whether it can be used for filtering.
- Whether it is product-specific or reusable across categories.

Support text, numbers, custom dropdowns, multiple selections, booleans, colors, sizes, measurements, images, and other appropriate field types.

For selectable values, allow free-text entry and creation of new options directly from the selector. A dropdown must never be the only way to define a new value when custom values are needed.

When a category changes, adapt the product editor to the category's configured attributes while preserving compatible existing information.

## 3. Use Reusable, Interactive Visual Components

Create a consistent component library instead of rebuilding controls independently across different screens.

Examples include:

- `ColorSwatchPicker`
- `CustomCreatableSelect`
- `SizeSetEditor`
- `BrandSelector`
- `BrandLogoUploader`
- `AttributeBuilder`
- `VariantMatrixEditor`
- `ProductImageGallery`
- `LiveProductCardPreview`
- `PriceAndMarginEditor`
- `StockQuantityEditor`
- `ConfirmActionDialog`
- `InlineValidationMessage`

Component names are illustrative; adapt them to the project's conventions.

Each component must have a clear responsibility, typed inputs, predictable behavior, and reusable validation logic where appropriate.

### Interaction quality

- Make visual choices selectable with mouse, touch, and keyboard.
- Show visible selection states and useful labels.
- Provide contextual editing rather than forcing users to navigate through many screens.
- Support inline editing where it improves workflow.
- Confirm destructive operations.
- Preserve unsaved changes when validation fails.
- Provide meaningful feedback when an action succeeds or fails.
- Use consistent loading, empty, disabled, and error states.
- Keep forms compact without hiding important information.
- Avoid unnecessary modal dialogs, excessive dropdowns, and deeply nested menus.

The goal is to make the product editor feel like a practical visual workspace, not a spreadsheet disguised as an application.

## 4. Make Product Variant Configuration Fully Dynamic

The variant system must work with any configured attribute that is designated as a variant dimension.

For example, an administrator may configure a product with:
- Color and size.
- Color and material.
- Model and capacity.
- Frame color and frame style.
- Any other supported combination of custom attributes.

Do not hardcode variant generation to two fields named `color` and `size`.

Implement a data model that supports configurable variant dimensions and valid combinations.

For each variant, persist a stable identifier and the relevant option selections, SKU, stock, pricing, availability, and optional image.

The interface must let administrators:
- Generate combinations from selected options.
- Exclude combinations that do not exist.
- Add an individual combination manually when needed.
- Edit each combination independently.
- Apply bulk changes safely.
- Identify duplicate combinations.
- Disable or archive variants without corrupting historical orders.
- See stock and pricing changes in the preview when relevant.

The storefront must derive its selectable options from the actual published product data. It must not display hardcoded colors, sizes, or combinations that the administrator has not configured.

## 5. Backend Architecture and Clean Code Requirements

Do not implement this as a collection of loosely connected UI forms and API calls.

First inspect the existing repository, dependency versions, database schema, API contracts, and project structure. Preserve working functionality and follow established conventions unless there is a concrete reason to change them.

### Architecture

Establish clear separation between:

- Presentation components.
- Application workflows and use cases.
- Domain rules and product/variant logic.
- Data access and persistence.
- API controllers or route handlers.
- Request validation and response serialization.
- Authentication and authorization.
- File and image storage.
- Inventory and order processing.

Use the architecture appropriate to the current technology stack. Do not introduce unnecessary frameworks, layers, microservices, or dependencies merely for architectural appearance.

### Data integrity

- Use stable database identifiers instead of identifying variants by their displayed labels.
- Define appropriate foreign keys, unique constraints, indexes, and transactions.
- Model product attributes and variant options so custom values can be persisted without schema changes for every new color, brand, or size.
- Validate all incoming requests on the server.
- Enforce stock and price rules on the backend.
- Use atomic inventory operations and transaction-safe order creation.
- Prevent duplicate variants and invalid option combinations.
- Handle concurrent orders without overselling.
- Preserve historical order details when product names, prices, brands, or variant labels change.
- Use safe database migrations and maintain compatibility with existing records.

Never rely on frontend validation as the only security or data-integrity control.

### Maintainability

- Use clear names, small focused functions, and consistent project conventions.
- Avoid giant components, giant route handlers, duplicated business rules, unnecessary abstractions, and deeply nested conditional logic.
- Use strong typing where supported by the existing stack.
- Define clear interfaces and contracts between the CMS, backend, and storefront.
- Centralize shared validation and domain rules appropriately.
- Handle errors consistently without exposing secrets, stack traces, or sensitive internal details to users.
- Remove dead code, obsolete components, duplicate implementations, and unused dependencies introduced by the changes.
- Keep configuration and secrets outside source code.
- Document non-obvious business rules and architectural decisions.
- Do not suppress type errors or lint failures just to make the build pass.

## 6. Full Functional Verification — No Superficial Testing

Do not stop after the interface looks correct.

Test the actual behavior of every newly implemented feature, including persistence, API integration, storefront rendering, and error handling.

### Required tests

1. Create a completely new color, assign it a custom name and HEX value, save it, refresh, and verify persistence.
2. Create a brand that does not already exist, upload its logo, and assign it to a product.
3. Create custom sizes outside any predefined size list.
4. Define a new product attribute and configure whether it appears on the storefront or creates variants.
5. Create a product with arbitrary custom variant dimensions.
6. Generate valid combinations, exclude invalid ones, and save the product.
7. Reopen the editor and confirm that every value, selection, image, and variant is restored correctly.
8. Modify a product and verify that the live preview updates correctly.
9. Publish the product and verify that the storefront displays the same configured values.
10. Verify that newly created options become available without rebuilding or redeploying the application.
11. Test duplicate options, malformed values, missing required fields, invalid prices, and invalid stock quantities.
12. Test deleting, renaming, disabling, or archiving options used by existing products.
13. Test concurrent inventory changes and order creation.
14. Verify that unauthorized API requests cannot modify products, prices, or stock.
15. Test image upload failures, invalid file types, oversized files, and missing images.
16. Run regression tests against existing products, orders, customers, CMS functions, and storefront behavior.
17. Run automated tests, type checks, linting, and the production build.

Add automated unit tests for business rules, integration tests for APIs and persistence, and end-to-end tests for the most important administrator and customer workflows.

Use isolated test data and clean up after tests. Never run destructive tests against production data.

### Final delivery requirements

After implementation:
- Report the main architectural changes.
- Identify the files and modules changed.
- List the tests actually executed and their results.
- Distinguish verified functionality from anything that remains untested.
- Explain any remaining blocker precisely.
- Fix discovered defects before considering the task complete.

**Final standard:** Every configurable product option must be editable, persist correctly, and flow through the backend into the storefront. The visual editor must be intuitive and professional, the data model must support future customization, and the code must remain clean, secure, testable, and maintainable.

Do not replace working features with mock data, fake interactions, hardcoded values, or visual-only implementations. Inspect, implement, run, verify, and fix.
One important architectural decision: don't create a new database column every time the store owner adds a color, brand, size, or custom attribute. Store configurable attributes and variant combinations in a properly related data model, with stable IDs and database constraints. That is what lets the CMS grow without requiring a code change for every new product type.
