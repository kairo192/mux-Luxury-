# MUS LUXURY CMS — FULL FUNCTIONALITY, TRANSLATION & UI STABILITY AUDIT

Act as a senior full-stack engineer, QA automation engineer, UI/UX engineer, and application security engineer.

Your task is to inspect, repair, improve, and thoroughly test the entire Mus Luxury CMS codebase.

**This is an implementation task, NOT a code review or a list of suggestions. You must make the necessary changes directly in the existing project.**

## 1. First: Understand the entire architecture

Before modifying anything:

- Inspect the complete repository structure.
- Understand the React frontend, Tauri desktop integration, Python backend, API services, database, state management, and localization implementation.
- Identify all application pages, routes, components, modals, dialogs, forms, buttons, dropdowns, and interactive elements.
- Trace frontend actions to their actual backend API operations.
- Identify incomplete implementations, dead buttons, placeholder functionality, duplicated components, and inconsistent state handling.
- Preserve the existing design language, branding, architecture, and business logic.

Do not replace working functionality with mock implementations.

## 2. Fix the incomplete language translation system

**Critical existing bug:** Selecting a language currently translates only navigation tabs. The actual page content remains in the previous language.

Fix this globally.

Requirements:

- Implement complete application-wide localization.
- Support English, French, and Arabic.
- Every page must translate, including:
  - Page titles and subtitles.
  - Dashboard statistics and descriptions.
  - Buttons and action labels.
  - Product management.
  - Product creation and editing forms.
  - Categories and attributes.
  - Inventory and stock management.
  - Orders and customer management.
  - Accounting and financial pages.
  - Settings.
  - Notifications.
  - Confirmation dialogs.
  - Validation messages.
  - Empty states.
  - Tooltips.
  - Loading indicators.
  - Error messages.
  - Success messages.
  - Tables, filters, pagination and dropdowns.
- Translate dynamically generated UI labels.
- Remove hardcoded user-facing strings from components.
- Centralize translations using a consistent localization architecture.
- Ensure all translation keys exist in all three languages.
- Add missing-key detection and sensible fallback behavior.
- Changing language must update the entire application immediately without requiring a restart.
- Persist the selected language after application restart.
- Implement correct RTL layout for Arabic, including icons, alignment, forms, tables, navigation, and dialogs.
- Ensure Arabic typography does not break component dimensions.

Do not consider localization complete until every page has been checked in all three languages.

## 3. Repair ALL buttons and interactive functionality

Audit every page and every interactive element.

Specific existing issue:

The **"Créer un nouveau produit"** action/button underneath the main button is not working correctly.

Investigate the actual event handler, component state, routing, modal logic, API requests, and backend integration.

Fix it completely.

When creating a product:

- The button must trigger the correct product creation workflow.
- The form must open correctly.
- Category selection must work.
- Dynamic attributes must load based on the selected category.
- Color, size, brand, quantity, and variant controls must work.
- Image uploads must work.
- Form validation must work.
- Submission must call the real backend API.
- Loading and submission states must be handled correctly.
- Successful creation must update the product list.
- Failed requests must display useful error messages.
- Prevent accidental duplicate submissions.
- Do not report success if the backend operation failed.

Repeat this level of investigation for every other button.

Audit:
- Create, edit and delete actions.
- Search and filtering.
- Sorting.
- Pagination.
- Dropdowns and selectors.
- Tabs and navigation.
- Image upload and removal.
- Product variant management.
- Stock updates.
- Category management.
- Customer operations.
- Order management.
- Accounting operations.
- Export and import.
- Settings.
- Language switching.
- Confirmation dialogs.
- Notifications.

Every visible interactive element must have a meaningful and working action.

No decorative buttons pretending to be functional.

## 4. Fix the UI shaking and layout instability

**Critical existing visual bug:** The interface shakes or shifts when the product preview becomes active/selected.

Investigate the root cause instead of applying random CSS patches.

Check for:

- Layout shifts when preview components mount.
- Dynamic component height changes.
- Width changes caused by scrollbars.
- Conditional rendering affecting parent dimensions.
- Unstable flex and grid sizing.
- Incorrect CSS transitions.
- Image dimensions changing after loading.
- State updates causing unnecessary re-renders.
- Modal and dropdown positioning issues.
- Preview activation changing container dimensions.
- Font loading and localization-related layout shifts.

Implement proper fixes:

- Stable component dimensions.
- Consistent grid and flex layouts.
- Reserved image and preview dimensions.
- Correct overflow handling.
- Stable modal positioning.
- Proper loading skeleton dimensions.
- Controlled transitions.
- No unnecessary layout animations.
- Avoid changing parent dimensions when preview state changes.
- Prevent horizontal overflow.

Test the preview in active, inactive, loading, selected, and deselected states.

The interface must remain visually stable.

Apply this audit to the entire CMS, not just the product preview.

## 5. Rebuild and standardize message boxes

Improve the application's notification and messaging system.

All messages must be structured, consistent, readable, and functional.

Create reusable components for:

1. Success notifications.
2. Error notifications.
3. Warning notifications.
4. Informational notifications.
5. Confirmation dialogs.
6. Form validation messages.
7. Loading and processing states.

Requirements:

- Clear titles.
- Short and meaningful descriptions.
- Appropriate icons.
- Consistent spacing and typography.
- Correct visual hierarchy.
- Proper positioning.
- Responsive behavior.
- Smooth but restrained animations.
- Automatic dismissal for non-critical notifications.
- Manual dismissal.
- Correct stacking when multiple notifications appear.
- No overlapping dialogs.
- No notifications appearing outside the viewport.
- Confirmation dialogs must have working Cancel and Confirm actions.
- Destructive actions must require appropriate confirmation.

Do not use browser alert() and confirm() as substitutes for a proper application messaging system.

All messages must be localized.

## 6. Launch and test using Google Chrome

You MUST actually run the application and test it in a real browser.

Use the existing development environment.

- Start the backend.
- Start the frontend.
- Verify API connectivity.
- Launch Google Chrome using Playwright with the installed Chrome channel where available.
- If Chrome is unavailable, report this explicitly rather than claiming Chrome testing succeeded.
- Use the actual running application, not static mockups.

Test the following:

### Functional testing
- Visit every route.
- Open every page.
- Interact with every button.
- Test forms and validation.
- Test product creation.
- Test product editing.
- Test product deletion.
- Test category operations.
- Test dynamic product attributes.
- Test image uploads.
- Test search and filtering.
- Test navigation.
- Test notifications and confirmation dialogs.
- Verify backend requests and responses.

### Localization testing
Run the complete application in:
- English.
- French.
- Arabic.

Inspect every page in every language.

Verify that no untranslated English or French labels remain when another language is selected.

### Visual testing
Test:
- Dashboard.
- Every management page.
- Product creation.
- Product editing.
- Product preview.
- Active preview state.
- Inactive preview state.
- Modals.
- Dropdowns.
- Notifications.
- RTL Arabic layout.

Test desktop resolutions:
- 1920x1080.
- 1600x900.
- 1366x768.
- 1280x800.

Check for layout shifts, overflow, clipped content, overlapping elements, and broken alignment.

## 7. Automated testing

Implement or improve automated testing using the existing testing stack.

Use Playwright for browser-level tests where appropriate.

Create reusable tests for:
- Navigation.
- Localization.
- Product CRUD.
- Category CRUD.
- Form validation.
- API integration.
- Notifications.
- Preview state changes.
- Layout stability.
- RTL rendering.

Add tests that detect:
- JavaScript errors.
- Failed network requests.
- Console errors.
- Broken API responses.
- Missing translations.
- Unexpected page navigation.
- Layout instability.

Use real test data and an isolated test environment. Never corrupt production data or delete existing user data during testing.

## 8. Code quality and performance

Review the codebase for:

- Duplicate components.
- Dead code.
- Incorrect state management.
- Memory leaks.
- Unnecessary re-renders.
- Missing React keys.
- Incorrect effect dependencies.
- Race conditions.
- Unhandled promises.
- Missing error boundaries.
- Inconsistent API handling.
- Incorrect loading states.
- Accessibility problems.

Refactor only where necessary and preserve existing functionality.

Do not introduce unnecessary dependencies.

## 9. Final verification

After implementing all fixes:

1. Restart the complete application.
2. Run frontend build and type checks.
3. Run backend tests.
4. Run the automated browser tests.
5. Repeat the manual Chrome tests.
6. Verify all three languages.
7. Verify the product preview no longer causes shaking.
8. Verify every audited button performs its intended operation.
9. Verify the messaging system works correctly.
10. Inspect the browser console and network requests.

Do not claim something works unless you have actually tested it.

## 10. Final report

Produce a detailed report containing:

- Every issue discovered.
- Root cause of each issue.
- Files modified.
- Changes implemented.
- Buttons and workflows tested.
- Pages tested.
- Localization results.
- Chrome browser testing results.
- Automated test results.
- Backend integration results.
- Remaining issues, if any.

Include screenshots of important fixed screens and test evidence.

Use these statuses:
- PASS — Successfully implemented and tested.
- FAIL — Still broken.
- BLOCKED — Could not test because of an identified dependency or environment limitation.

**FINAL REQUIREMENT:**

Do not stop after fixing the language selector or the product creation button.

The entire CMS must be audited and repaired systematically.

Do not redesign the application unnecessarily. Preserve its current visual identity while making it stable, fully functional, multilingual, and production-ready.

Never fabricate test results. If a test cannot be performed, explain exactly why.
3. What I expect after Antigravity finishes
Don't accept a response saying "all fixed" just because the build succeeds.

A successful build does not prove that the application works.
Verification	Required result
English	Every page translated
French	Every page translated
Arabic	Every page translated + RTL
Product creation	Real product saved in backend
Product preview	No shaking or layout movement
Buttons	Actual actions work
Notifications	Structured and functional
Chrome	Actual browser testing
Backend	No failed or incorrect API operations
Regression	Existing features still work

One important point: Tell Antigravity not to use fake product data or mock API responses to make tests pass. Use an isolated test database, and preserve the real database.

Once Antigravity finishes, send me its final report and screenshots. I can then help you challenge its results and identify anything it claims to have fixed without sufficient evidence.

