# Upgrade the E-Commerce CMS — Product Management, Variants & Premium UX

Work directly on the existing project and **upgrade the current CMS and storefront without breaking existing functionality, architecture, database records, or synchronization**. Do not just redesign the interface. Implement, connect, and test the complete functionality.

## 1. Transform the CMS into a Professional Store Management Experience

Redesign and improve the CMS so a non-technical store owner can manage the entire website confidently, comfortably, and efficiently.

The interface must feel like a premium, production-ready commercial application, not a basic admin template.

### Visual and UX requirements
- Create a clean, modern, premium interface with consistent spacing, typography, colors, icons, and component styles.
- Use the existing brand identity and logo. Preserve the established green and reflective gold colors.
- Build a clear sidebar with logically grouped navigation, an informative dashboard, organized page layouts, and consistent action buttons.
- Make forms understandable, with descriptive labels, helpful placeholders, tooltips where necessary, validation messages, and clear success/error feedback.
- Use searchable dropdowns, visual color selectors, image previews, status badges, confirmation dialogs, and contextual actions.
- Provide empty states that explain what the user should do next.
- Support responsive layouts, accessible controls, keyboard navigation, and readable contrast.
- Prevent clutter. Use progressive disclosure so advanced options appear when needed instead of overwhelming the user.
- Include unsaved-change warnings, loading indicators, and useful error recovery.
- Use French as the primary interface language if that matches the existing application, while preserving any existing Arabic or English localization.

The user must understand what each control does without needing technical knowledge.

## 2. Build a Complete Dynamic Product Editor

Upgrade the product creation and editing workflow. Do not limit the product form to a fixed set of fields.

### General product information
Support:
- Product name and description.
- SKU, internal reference, barcode, and brand.
- Category and subcategory.
- Product images, image gallery, and main image selection.
- Purchase price, selling price, discounted price, and profit margin where applicable.
- Stock quantity, low-stock threshold, and availability.
- Publication status: draft, published, inactive, or out of stock.
- Featured products and optional tags.
- Weight, dimensions, shipping information, and other optional attributes.
- SEO title, meta description, and URL slug if supported by the current storefront.

Keep required fields clearly distinguished from optional fields.

### Dynamic categories and custom attributes

Allow administrators to create, edit, reorder, and deactivate categories directly inside the CMS.

When creating a category, let the administrator define the attributes relevant to that product type.

Examples:
- Bags: color, size, material, brand, dimensions.
- Shoes: shoe size, color, material, brand.
- Clothing and scarves: size, color, fabric, style.
- Makeup: shade, volume, brand, skin type.
- Watches: strap material, color, movement, brand.
- Glasses: frame color, frame style, material.

These are examples, not hardcoded restrictions.

Allow the administrator to add custom attributes with appropriate field types:
- Text.
- Number.
- Dropdown.
- Multi-select.
- Boolean.
- Color selector.
- Image upload.
- Measurement or dimension.
- Size selector.

Support required/optional settings, default values, and reusable attribute definitions.

Changing a category must not silently delete existing product information.

## 3. Implement a Complete Color and Size Variant Manager

**This is a core requirement. Every variant must be a real, independently manageable product option, not merely decorative text on the product page.**

For each product, the administrator should be able to enable and configure:
- Colors, with color names and actual color swatches.
- Sizes, with customizable size values.
- Brands and brand logos.
- Materials, styles, models, and other category-specific attributes.
- Custom variant dimensions when required.

### Color management
- Provide a visual color picker and hexadecimal color input.
- Allow readable color names, including French or Arabic names when supported.
- Display each color as a swatch with its label.
- Support multiple colors per product.
- Allow the administrator to create reusable colors in a central attribute library.
- Permit different product images for different colors when supported by the data model.

### Size management
- Support predefined size sets and custom size values.
- Allow different size systems for different categories, such as clothing sizes and shoe sizes.
- Support products without sizes.
- Allow administrators to choose the available sizes for each product.

### Variant-level inventory and pricing

Generate the appropriate combinations of selected attributes, but let the administrator choose which combinations actually exist.

For example, a shoe might have:
- Black / Size 40.
- Black / Size 41.
- White / Size 40.
- White / Size 42.

Each valid combination can have its own:
- SKU or variant reference.
- Barcode, if applicable.
- Stock quantity.
- Price adjustment or independent selling price.
- Purchase cost, if required for inventory management.
- Availability status.
- Image.
- Weight or other relevant properties.

Do not create unavailable combinations automatically as purchasable products.

Provide a compact variant table with inline editing, bulk stock updates, bulk price changes, search, filtering, and clear low-stock indicators.

Prevent duplicate variant combinations and validate stock and pricing inputs.

## 4. Make the Storefront Quantity and Variant Selection Work Correctly

Implement the following customer-facing behavior for every product that has variants.

### Scenario A: The customer selects one quantity

When a customer chooses one unit:
1. Display the available color and size selectors when relevant.
2. Require the customer to select the necessary variant options.
3. Validate that the chosen combination exists and has sufficient stock.
4. Add the correct variant to the cart.

### Scenario B: The customer selects two or more units

**Do not assume that multiple units of the same product must have the same color or size.**

When the customer increases the quantity to two or more, provide an intuitive choice:

- **Same options for all units:** The customer selects one color and size, then specifies the quantity.
- **Different options for each unit:** The customer can distribute the requested quantity across different variants.

For example, if the customer wants two pairs of shoes, show a clear prompt such as:

"Vous souhaitez 2 articles. Voulez-vous la même couleur et la même pointure pour les deux ?"

Offer:
- "Oui, mêmes options."
- "Non, choisir les options séparément."

Use the language already configured for the storefront.

If the customer chooses the same options, allow them to select a single variant and quantity.

If the customer chooses different options, display a simple variant allocation interface, for example:

| Couleur | Pointure | Quantité |
|---|---|---:|
| Noir | 40 | 1 |
| Blanc | 41 | 1 |

Allow the customer to add or remove allocations, select available combinations, and adjust quantities.

The total allocated quantity must equal the requested quantity before proceeding.

If stock is insufficient, show the actual available quantity and require the customer to correct the selection. Never silently substitute another size or color.

### Cart behavior

- Store the exact variant ID, selected attributes, unit price, and quantity for each cart line.
- Display color, size, and other relevant selections clearly in the cart.
- Allow customers to edit variant selections and quantities.
- Merge cart lines only when they refer to the same valid variant and compatible pricing.
- Revalidate availability and pricing before checkout and order confirmation.
- Prevent duplicate stock deductions and overselling.
- Ensure the selected variants remain correct throughout checkout and order creation.

For a product without variants, use a straightforward quantity selector without unnecessary questions.

For a product with only colors or only sizes, ask only for the applicable option.

## 5. Improve the Entire CMS Navigation and Workflow

Review every existing CMS screen and make the interface consistent.

Improve:
- Dashboard and business overview.
- Product listing, filtering, searching, and bulk actions.
- Product creation and editing.
- Category and attribute management.
- Color and size libraries.
- Brands and brand logos.
- Inventory and stock adjustments.
- Purchase and sales pricing.
- Orders and order details.
- Customer management, where supported.
- Discounts and promotions.
- Website content and banners.
- Store settings and delivery configuration.
- Reports and accounting features already present in the project.
- User permissions and audit logs, if supported by the existing architecture.

Use clear terminology, consistent actions, helpful summaries, and sensible defaults.

Do not add meaningless dashboard statistics or fake data. Every displayed metric must come from actual application data.

## 6. Database, API, and Synchronization Requirements

The CMS and storefront must use the same authoritative product and variant data.

Inspect the existing database schema, backend APIs, and frontend data models before changing anything.

Implement and verify:
- Persistent storage for categories, custom attributes, product variants, and stock.
- Correct relationships between products and their variants.
- Validated API requests and responses.
- Database migrations that preserve existing records.
- Server-side price and stock validation.
- Atomic stock updates and transaction-safe order creation.
- Consistent handling of deleted, disabled, and unavailable variants.
- Correct synchronization between CMS changes and the live storefront.
- Proper image upload, storage, validation, and retrieval.
- Authentication and authorization for administrative operations.
- Protection against unauthorized price manipulation, stock changes, and invalid product IDs.
- Logging of important administrative and inventory changes.

Never trust prices, stock quantities, or variant availability submitted by the browser.

Do not introduce a second competing source of truth or replace the existing architecture without a demonstrated technical reason.

## 7. Testing and Acceptance Criteria

After implementing the changes, run the application and test the actual workflows.

At minimum, verify:

1. Create a category with custom attributes.
2. Create a product with multiple colors and sizes.
3. Generate valid variants and assign different stock quantities.
4. Edit a color or size without corrupting existing variants.
5. Publish the product and confirm the storefront displays the correct options.
6. Purchase two units with identical options.
7. Purchase two units with different colors or sizes.
8. Purchase several units distributed across three or more variants.
9. Attempt to select an unavailable combination.
10. Attempt to exceed available stock.
11. Change stock in the CMS and verify storefront availability updates.
12. Edit a variant price and verify the server uses the correct price.
13. Add items to the cart, refresh the page, and verify persistence if cart persistence is supported.
14. Create an order and verify inventory is deducted correctly.
15. Test concurrent orders against limited stock.
16. Verify that an unauthorized user cannot modify products or inventory.
17. Check existing products, orders, and other functionality for regressions.
18. Test responsive behavior, validation messages, empty states, and error handling.

Fix failures rather than merely reporting them.

Run the relevant automated tests, type checks, linting, and production build. Do not claim that something works unless it has been tested. If a feature cannot be completed because of a missing backend capability or architectural limitation, identify the exact blocker and implement the safest feasible solution.

## Final objective

Deliver a coherent, premium-quality e-commerce management application that a real store owner can use every day without technical assistance.

The CMS must make product creation, color and size management, stock control, pricing, and website administration straightforward. The storefront must correctly handle multiple quantities with identical or different variants.

**Inspect first, implement the complete workflows, test the CMS-to-storefront integration, fix regressions, and provide a concise report of what changed, what passed, and what remains blocked. Do not stop at UI mockups or partially wired features.**