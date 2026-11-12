# MUS LUXURY — Complete Storefront Redesign, Navigation Repair, Mobile UX & Production Quality Audit

Act as a senior frontend engineer, UI/UX designer, and software architect. Work directly on the existing Mus Luxury e-commerce project.

**Objective:** Transform the current storefront into a polished, premium luxury-shopping experience that works correctly on desktop, tablet, and mobile, integrates with the existing CMS and backend, and contains no known frontend regressions.

Do not simply provide recommendations or mockups. Inspect the source code, implement the changes, run the application, test real user journeys, and fix the problems discovered.

## 1. Start by Inspecting the Existing Project

Before changing code:

- Inspect the frontend framework, router, component structure, styling system, shared layouts, state management, API clients, and existing dependencies.
- Identify the two header/navigation areas visible in the supplied screenshot.
- Inspect all existing storefront routes, including Home, Boutique, Maroquinerie, Chaussures, Beauté, La Maison, and every other implemented page.
- Identify how products, categories, images, colors, sizes, pricing, stock, and availability are retrieved from the CMS.
- Determine which elements are duplicated, hardcoded, disconnected, or visually inconsistent.
- Inspect existing brand assets and preserve the Mus Luxury logo and established dark-green and gold identity.
- Review the existing Apple Design Skill installation and follow its actual `SKILL.md` and relevant references. If it is not installed, install it using the official repository instructions where the environment permits.

Apple Design Skill repository: https://github.com/dickwu/apple-design-skill

Use the skill as a source of design principles, accessibility standards, interaction guidance, and design critique. Translate its recommendations to the actual web stack. Do not blindly copy native iOS/macOS components into the website.

Create a short implementation plan, then proceed with the fixes. Do not stop after the audit.

## 2. Fix the Duplicate Header and Navigation Architecture

The current screenshot shows two stacked navigation areas. They create unnecessary vertical space and make the hierarchy confusing.

Redesign the shared storefront layout.

### Desktop header

Create a coherent header system with clearly differentiated layers:

**Utility bar**
- Delivery information across Algeria.
- Relevant contact information and social links.
- Language selector for the languages actually supported.
- Order tracking and delivery information where implemented.

**Primary navigation**
- Mus Luxury logo.
- Main navigation links.
- Search.
- Wishlist.
- Shopping cart with an accurate item count.

**Category navigation**
- Keep this as a separate row only if it adds real value to browsing.
- Avoid duplicating the same destinations in multiple rows.
- Use the existing CMS-managed categories rather than hardcoded category lists.
- If the separate row is unnecessary, replace it with a cleaner navigation structure.

Keep the header visually compact, premium, and consistent with the brand. Ensure the content does not jump, overlap, or become obscured when the header is sticky.

Do not delete useful functionality merely to reduce the number of rows.

### Correct active-route indicator

The navigation underline or selected state must follow the current route reliably.

Implement route-aware active states using the existing router's location and matching APIs.

Requirements:
- The active link updates after every navigation.
- Directly opening a URL selects the correct page.
- Browser back and forward update the active state.
- Refreshing a page preserves the correct active state.
- Nested routes use intentional matching rules.
- Parent categories can be active on their relevant detail pages without incorrectly highlighting unrelated links.
- Exactly the intended navigation item receives the active treatment.
- Hover, keyboard focus, and active states remain visually distinct.

Use a subtle gold underline or another existing brand-consistent indicator, with a smooth transition that respects reduced-motion preferences.

Do not maintain the active link using manually duplicated component state.

### Routing reliability

- Use the existing routing architecture.
- Avoid unnecessary full-page reloads.
- Ensure internal links work correctly.
- Support direct navigation and page refreshes on nested routes through the correct hosting configuration.
- Display a useful not-found page for invalid routes.
- Preserve query parameters and intended navigation state when applicable.
- Eliminate console errors, invalid route targets, and broken links.

## 3. Build a Proper “La Maison” Store Page

The current La Maison destination must become a complete physical-store information page, not a generic landing page or an empty section.

Design it as a premium boutique experience.

### Page structure

**A. Editorial hero**
- High-quality store photography or existing relevant brand imagery.
- A strong French heading such as “La Maison Mus Luxury”.
- A concise introduction to the boutique and brand.
- Clear actions: “Nous trouver”, “Nous contacter”, and “Itinéraire”, as appropriate.
- A refined layout that uses the established green and gold palette without excessive decorative elements.

**B. Store identity**
- Actual store name.
- Full physical address.
- Real store photographs where available.
- A short brand introduction.
- Optional store services and shopping information, based on verified data.

**C. Interactive location map**
- Display a responsive map with a marker for the actual store.
- Provide zoom and pan controls where supported.
- Include a visible address and a button to open directions in the appropriate map service.
- Provide a usable external map link as a fallback.
- Ensure the map works on mobile and does not overflow its container.

Do not invent the store's coordinates, address, or opening hours. Retrieve the actual information from existing project configuration or CMS data. If information is missing, create a clear CMS-configurable setting and mark the missing value rather than presenting fictional details.

Use a map provider appropriate to the existing stack, budget, and deployment constraints. Avoid exposing secret API keys in frontend code. If using a provider that requires a key, configure it securely and document the requirement.

**D. Opening hours**
- Present the actual opening schedule in a clean, readable format.
- Display today's hours only when the schedule and relevant timezone are known.
- Handle closed days and special hours.
- Make opening hours editable through the CMS if the existing architecture supports store settings.

**E. Contact and customer service**
- Display the verified phone number, WhatsApp contact, email, and social links where configured.
- Use working `tel:`, `mailto:`, and WhatsApp links where applicable.
- Include a simple contact section with clear actions.
- Add a contact form only if the backend can actually receive and process submissions securely.

**F. Additional sections**
Where genuine content is available, add store photography, a visit invitation, shopping information, and a final contact call to action.

Keep the page visually distinctive, useful, and easy to navigate. Do not fill it with generic paragraphs, fake reviews, invented store history, or decorative sections with no purpose.

## 4. Complete Responsive Mobile Storefront

Mobile is a first-class experience, not a compressed desktop layout.

Test and optimize the entire storefront across narrow phones, large phones, tablets, laptops, and desktop screens.

### Mobile navigation

Replace the oversized desktop navigation with a dedicated mobile navigation pattern.

Use a compact top header with:
- Brand logo.
- Search access.
- Shopping cart.
- A menu or category-navigation control when appropriate.

Implement a fixed bottom navigation bar where useful, with a small number of clearly labeled destinations such as:
- Accueil.
- Boutique.
- Favoris.
- Panier.
- Menu or account functionality, only if it exists.

Choose the final destinations based on actual application functionality. Do not show nonfunctional account features or placeholder tabs.

Requirements:
- Respect device safe areas and bottom insets.
- Reserve enough page padding so the bottom bar never covers product cards, buttons, checkout controls, or footer content.
- Highlight the active destination based on the actual route.
- Use sufficiently large touch targets and clear active states.
- Ensure all navigation destinations are reachable.
- Provide a usable menu for categories that do not fit in the bottom bar.
- Support scrolling without accidental interactions or layout shifts.
- Keep the bar visually consistent with the luxury brand.

### Mobile layout and performance

- Remove horizontal overflow and clipped text.
- Use responsive grids that adapt product-card counts to the available width.
- Keep product images properly cropped and consistently proportioned.
- Make prices, discounts, color selectors, sizes, and add-to-cart controls readable and usable.
- Make search, filters, sorting, and category navigation touch-friendly.
- Prevent sticky elements from covering content.
- Use responsive image sizes and lazy loading where appropriate.
- Avoid loading unnecessarily large desktop assets on mobile.
- Respect reduced motion and accessibility preferences.
- Keep the checkout process simple and usable on small screens.

Use fluid layouts and appropriate breakpoints rather than fixing the design to a few device widths.

## 5. Rebuild the Storefront Around Real CMS Data

The CMS is the source of truth for products, categories, and configurable attributes.

Audit every storefront page and remove hardcoded product or category data wherever the CMS is intended to control it.

### Products and categories

Ensure the storefront correctly reflects:
- Published products.
- CMS-managed categories and category ordering.
- Product names, descriptions, and images.
- Dynamic brand names and brand logos.
- Custom product attributes.
- Configured colors and visual color swatches.
- Configured sizes and other variant dimensions.
- Variant-specific availability and stock.
- Correct prices and discounts.
- Featured products and promotional banners.
- Product visibility and availability status.

Do not assume a product has only predefined colors, sizes, or brands.

The storefront must render the actual options configured in the CMS. If an administrator creates a new category, color, size, brand, or custom attribute, the frontend must handle it without requiring a frontend code change or redeployment, provided the backend supports dynamic configuration.

### Product details and selection

- Ensure every product card opens the correct product detail page.
- Display appropriate variant selectors when required.
- Prevent selecting nonexistent or unavailable combinations.
- Show accurate stock and pricing.
- Support the correct behavior for multiple quantities with identical or different variants.
- Ensure the cart retains the selected variant IDs and quantities.
- Revalidate prices and availability through the backend before checkout.

### Search, filters, and sorting

Implement and verify:
- Search against actual available product data.
- Category filtering.
- Relevant dynamic attribute filters where supported.
- Price sorting and other valid sort options.
- Correct pagination or incremental loading.
- Clear filter and no-results states.

Do not create filter controls that only change their visual appearance without changing the results.

### Wishlist and cart

Verify that:
- Wishlist buttons add and remove the correct products.
- Cart counts match actual cart contents.
- Cart quantities and selected variants remain accurate.
- Price totals are calculated correctly.
- Stock changes are handled safely.
- Empty carts and wishlists have useful states.
- Cart and wishlist persistence behave according to the existing architecture.

Do not introduce customer accounts or a new authentication system unless required by the current project.

## 6. Apply Apple Design Skill Principles Without Losing Brand Identity

Use the Apple Design Skill to conduct a real design review and guide implementation.

Review the relevant design references before making major UI decisions. Focus on layout, typography, color, accessibility, interaction, responsive design, navigation, feedback, and visual craft.

### Visual direction

The target is a distinctive luxury e-commerce brand:
- Deep green surfaces.
- Restrained gold accents.
- High-quality product imagery.
- Refined typography.
- Clear visual hierarchy.
- Intentional whitespace.
- Consistent iconography.
- Subtle, purposeful motion.
- Clean, premium product cards.
- Carefully designed hover, focus, selected, loading, and disabled states.

Retain the existing brand assets and visual identity. Do not replace the logo, invent a new identity, or apply generic Apple-style visuals everywhere.

Use platform-independent design principles appropriately for a web storefront.

### Design tokens

Establish or refine a consistent token system for:
- Brand and semantic colors.
- Typography and type hierarchy.
- Spacing.
- Border radius.
- Borders and shadows.
- Container widths.
- Responsive breakpoints.
- Focus indicators.
- Motion and transitions.

Use existing project tokens when they are suitable. Avoid inconsistent one-off values throughout the codebase.

Verify text contrast and touch-target sizes. Use semantic HTML, accessible labels, keyboard navigation, visible focus states, and appropriate image alternative text.

Animations must improve comprehension or provide feedback, not slow down shopping.

## 7. Frontend Engineering and Code Quality

Keep the existing architecture unless there is a demonstrated technical reason to change it.

- Reuse shared layout, navigation, product-card, button, form, and modal components.
- Separate page components from reusable presentation components and data-access logic.
- Use the existing router correctly.
- Keep components focused and maintainable.
- Avoid duplicating header implementations across pages.
- Avoid giant components, deeply nested conditions, and repeated business rules.
- Use the project's existing typing conventions and enforce correct data shapes.
- Use stable React keys or equivalent framework identity mechanisms.
- Avoid stale state, effect loops, memory leaks, race conditions, and unnecessary rerenders.
- Clean up event listeners and subscriptions.
- Implement proper loading, empty, error, and retry states.
- Use consistent API error handling.
- Remove obsolete code and unused imports introduced by the changes.
- Avoid unnecessary dependencies and architecture rewrites.
- Never suppress errors just to make the build pass.

Do not hide backend integration failures behind fake fallback products or fabricated success messages.

## 8. CMS Configuration for Store Information and Navigation

Where appropriate, expose relevant settings through the existing CMS rather than hardcoding them in the storefront.

These may include:
- Store name, address, map coordinates, and map link.
- Opening hours.
- Phone, WhatsApp, email, and social links.
- Navigation labels and category ordering.
- Homepage banners and images.
- Featured categories and featured products.
- Store descriptions and contact information.

Reuse existing CMS settings if they already exist. Implement new settings only with proper persistence, validation, permissions, and API integration.

Changes made in the CMS must propagate to the storefront correctly without requiring a frontend rebuild when the application architecture supports runtime configuration.

Do not create duplicate settings that compete with existing sources of truth.

## 9. Required Verification and Regression Testing

Do not declare the task complete just because the website renders.

Run the project and test the actual storefront in a browser.

### Navigation and routing
1. Navigate through every primary navigation link.
2. Verify that the active underline or indicator follows the selected route.
3. Test direct URLs, refresh, browser back, and browser forward.
4. Verify nested routes and invalid URLs.
5. Confirm the desktop header no longer contains redundant navigation.
6. Confirm the mobile menu and bottom navigation work and never cover content.

### La Maison
7. Verify the page displays the correct configured address and contact details.
8. Test map rendering, zooming, and the external directions link.
9. Verify opening hours and contact links.
10. Test the page on mobile, including map and contact sections.

### CMS integration
11. Create or edit a product in the CMS and verify the storefront reflects the change.
12. Add a custom category and verify navigation and filtering update correctly.
13. Create custom colors, sizes, brands, and attributes and verify they render correctly.
14. Change a product price, image, or availability and verify the storefront updates.
15. Test invalid or incomplete API responses and ensure the UI handles them gracefully.

### Shopping workflow
16. Test search, filters, sorting, product details, wishlist, and cart.
17. Test quantities with identical and different variant selections.
18. Test unavailable combinations and insufficient stock.
19. Verify totals and price calculations.
20. Verify backend validation and prevent client-side price manipulation.

### Responsive and technical quality
21. Test at representative viewport widths, including 320, 375, 390, 768, 1024, and 1440 CSS pixels.
22. Check for horizontal scrolling, clipped elements, overlapping text, broken grids, and fixed bars covering content.
23. Check console errors, failed network requests, missing images, and broken links.
24. Test keyboard navigation, focus visibility, and reduced-motion behavior.
25. Run the project's available unit tests, integration tests, linting, type checks, and production build.
26. Fix all discovered regressions and rerun the relevant tests.

Use browser automation if available. Otherwise, run the application and perform real browser checks using the available environment. Do not claim that browser tests passed if they were not executed.

## 10. Definition of Done

The work is complete only when:

- The duplicate navigation problem has been resolved through a coherent header design.
- Active navigation indicators reliably follow the actual route.
- La Maison is a complete, useful, responsive physical-store page.
- The mobile storefront has a dedicated navigation and layout strategy.
- Product listings, filters, variants, cart, and wishlist are connected to real application data.
- The CMS and storefront remain synchronized.
- No known broken links, dead buttons, major layout defects, or runtime errors remain from the changes.
- The code is clean and consistent with the existing architecture.
- The relevant tests and production build have been run successfully, with any limitations disclosed.

### Final report

Provide a concise report with:
1. What was changed.
2. Which components, routes, and backend integrations were affected.
3. Which tests were actually executed.
4. Which tests passed or failed.
5. Any remaining blockers or external configuration requirements.

**Do not stop at planning, screenshots, or visual-only changes. Implement the complete solution, verify the real user flows, fix the defects, and preserve the existing working features.**