## 2025-12-17 - Table Header Accessibility
**Learning:** Tables with sortable columns must use semantic `<button>` elements inside `<th>` with `aria-sort` attributes. This ensures screen readers announce the sortability and current state, and allows keyboard navigation.
**Action:** Always wrap sortable column text in buttons and manage `aria-sort` state dynamically.
