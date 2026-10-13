# Development-only accessibility audit

`axe-core` is pinned to **4.11.0** (MPL-2.0), with npm lockfile integrity. It is injected only by the dedicated local Playwright audit; it is not a runtime dependency, bundled asset, SaaS collector, or automatically loaded by the overlay. No upstream source was modified or vendored. Keep package LICENSE/notices when redistributing it; MPL source-availability requirements apply to covered files and their modifications, not a blanket relicensing assertion about this application. A production/bundled or modified integration needs separate license review.

Install without lifecycle scripts:

```bash
npm ci --prefix tests/browser/ux-a11y --ignore-scripts --no-audit --no-fund
```

Run `tests/browser/ux-hardening.e2e.cjs` with the existing pinned Playwright installation. It asserts zero **serious/critical** violations on actual initial, processed and correction views. Other impacts and `incomplete` checks are retained in evidence, not silently claimed passing. Automated accessibility checks are not WCAG certification or assistive-technology/human usability proof.

The parent browser package retains Playwright **1.63.0** under Apache-2.0. No other catalog framework was installed. The local Chromium executable must be explicitly supplied when a Playwright-managed browser is unavailable.
