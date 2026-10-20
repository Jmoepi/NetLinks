# NetLinks design system

The visual language is adapted from the user-supplied reference `docs/design-reference.html`. Only the visual language carries over (colour, type, layout rhythm, components, motion). None of its content, copy or remote assets were used.

## 1. Approach
- Plain CSS with custom properties, no Tailwind. Every page already rendered through about 45 semantic classes in one stylesheet (`frontend/app/globals.css`). Re-theming those classes plus targeted markup changes restyled the whole app with little JSX churn. Moving to Tailwind would have meant rewriting every `className`, adding PostCSS and a new build dependency, for no behavioural gain and more regression risk on a demo-critical UI.
- Tokens live in `frontend/app/tokens.css` (imported before `globals.css` in `app/layout.tsx`). It is the single source for colours, the type scale, spacing, motion and the status palette.
- Icons come from `lucide-react` pinned to exactly `1.60.0` (`npm install --save-exact`). They use `strokeWidth={1.5}` and are always `aria-hidden`; text always carries the meaning. The reference's `≠` conflict glyph maps to lucide `EqualNot`.
- Fonts are system sans and mono stacks only (`--font-sans`, `--font-mono`), with no web fonts and no `next/font/google`. There are no remote assets of any kind, so the demo runs offline. The walkthrough verifies this by failing on any request to a host other than localhost:3000/8000 (0 seen).
- Headings and labels are uppercased with CSS `text-transform`, so the DOM text and accessible names are unchanged. Automated checks must compare `textContent` (Chromium's `innerText` applies the transform).

## 2. Tokens
| Token | Value | Use |
|---|---|---|
| `--canvas` | `#050505` | body background |
| `--surface-0` | `#000000` | alternate landing section, document page, form fields, nested panels |
| `--surface-1` | `#0a0a0a` (neutral-950) | panels, row hover, dialog |
| `--surface-2` | `#171717` (neutral-900) | table header, secondary-button hover |
| `--line` | `#171717` | decorative hairlines and row dividers |
| `--line-strong` | `#262626` (neutral-800) | panel borders, pill outlines, circle buttons (decorative) |
| `--control-border` | `#737373` (neutral-500) | form-field, secondary-button and link underline borders (non-text, ≥ 3:1) |
| `--text-strong` | `#ffffff` | headings, values |
| `--text` | `#d4d4d4` (neutral-300) | body text |
| `--text-muted` | `#a3a3a3` (neutral-400) | small informational text, labels, hints. This is the minimum for information |
| `--text-decor` | `#525252` (neutral-600) | decorative only (the `--` placeholder for unranked results) |
| `--accent` | `#FF3000` | primary buttons, active nav dot, dots, section indices, rank numbers, focus ring, selection |
| `--on-accent` | `#000000` | text and icons on accent fills |
| `--focus` | `var(--accent)` | `outline: 2px solid; outline-offset: 3px` on every `:focus-visible` |

Layout: `--container 1536px` (screen-2xl), `--gutter 1.5rem` (3rem from 768px), `--header-h 4.5rem`, spacing `--space-1…24` (0.25rem steps), radius 0 for buttons, fields and panels, and 999px for pills and circles.

### Type scale
| Token | Value | Use |
|---|---|---|
| `--fs-xs` … `--fs-5xl` | .75 / .875 / 1 / 1.125 / 1.25 / 1.5 / 1.875 / 2.25 / 3 rem | labels → stat numbers |
| `--fs-page-title` | `clamp(2.25rem, 4.5vw, 3.5rem)` | workspace h1 (SME, Buyer, Admin, document, audit) |
| `--fs-display` | `clamp(3.5rem, 11vw, 9rem)` | landing hero h1 only |
| `--fs-manifesto` | `clamp(2.75rem, 8vw, 8rem)` | landing manifesto only |
| weights | 300 light (lead copy), 400, 500, 600 semibold (headings, buttons) | |
| leading | display .9, manifesto .85, heading 1.05, body 1.625 | |
| tracking | tight -0.025em (headings), widest 0.1em (labels, buttons), stamp 0.25em | |

The display size is used only on `/`. Workspace pages never go above `--fs-page-title`.

### Status palette
| Status | Colour | Tint | Icon (lucide) | Used for |
|---|---|---|---|---|
| Eligible / Pass / SME-confirmed / Shared / success | `--ok #4ade80` | `--ok-tint` 8% | `CircleCheck` / `Check` / `UserCheck` | status pills, check outcomes, lineage, notices, stat labels |
| Needs Review / Low confidence | `--warn #fbbf24` | `--warn-tint` | `TriangleAlert` | pills, low-confidence rows (2px amber edge), "Low confidence - please confirm", date panels |
| Not Eligible / Fail / Conflict / error / danger | `--fail #fda4af` (rose-300) | `--fail-tint` | `CircleX` / `X` / `EqualNot` | pills, conflict rows and panels, error notices, the Reset button |
| Awaiting SME / info | `--info #7dd3fc` | `--info-tint` | `Hourglass` / `Info` | pills, info notices |
| AI-extracted | `--ai #c4b5fd` | `--ai-tint` | `Sparkles` | lineage pill |
| Verified | `--verified #5eead4` | `--verified-tint` | `ShieldCheck` | lineage pill |
| Not yet assessed / Not shared | `--neutral-status #a3a3a3` | none | `Minus` | pills |

Not Eligible uses rose, not the accent. The accent marks actions and position (primary button, active nav, rank), so a red-orange "Not Eligible" would read as a call to action and blur the one-accent rule. Rose (hue ~350°) is clearly distinct from the accent (hue ~11°). Every status is shown as icon + text label + colour, never colour alone.

## 3. Contrast results (WCAG AA)
Output of `node .agents/tasks/restyle-contrast.mjs` (it parses `tokens.css` and uses the WCAG relative-luminance formula). Exit code 0: all informational pairs PASS.

| Pair | Ratio | Requirement | Result |
|---|---|---|---|
| --text-strong #ffffff on --canvas / surface-0 / surface-1 / surface-2 | 20.38 / 21.00 / 19.80 / 17.93 | 4.5:1 | PASS |
| --text #d4d4d4 on --canvas / surface-0 / surface-1 / surface-2 | 13.75 / 14.17 / 13.36 / 12.09 | 4.5:1 | PASS |
| --text-muted #a3a3a3 on --canvas / surface-0 / surface-1 / surface-2 | 8.08 / 8.33 / 7.85 / 7.11 | 4.5:1 | PASS |
| --control-border #737373 as text on --canvas | 4.30 | 4.5:1 | fail: never used for text |
| --control-border #737373 field border vs --surface-1 (non-text) | 4.18 | 3:1 | PASS |
| --text-decor #525252 on --canvas | 2.61 | - | decorative only |
| --line-strong #262626 hairline on --canvas | 1.35 | - | decorative only |
| --accent #ff3000 text on --canvas / surface-0 / surface-1 / surface-2 | 5.51 / 5.67 / 5.35 / 4.84 | 4.5:1 | PASS |
| --accent focus ring vs --canvas (non-text) | 5.51 | 3:1 | PASS |
| #ffffff on --accent, small text | 3.70 | 4.5:1 | fail: not used for small text |
| #ffffff on --accent, manifesto (large text) | 3.70 | 3:1 | PASS |
| #000000 on --accent (primary button, `mark`) | 5.67 | 4.5:1 | PASS |
| #000000 on #ffffff (button hover) | 21.00 | 4.5:1 | PASS |
| #000000 on --fail (danger hover) | 11.11 | 4.5:1 | PASS |
| --ok #4ade80 on canvas / surface-1 / surface-2 | 11.70 / 11.36 / 10.29 | 4.5:1 | PASS |
| --warn #fbbf24 on canvas / surface-1 / surface-2 | 12.21 / 11.86 / 10.74 | 4.5:1 | PASS |
| --fail #fda4af on canvas / surface-1 / surface-2 | 10.78 / 10.47 / 9.48 | 4.5:1 | PASS |
| --info #7dd3fc on canvas / surface-1 / surface-2 | 12.22 / 11.87 / 10.75 | 4.5:1 | PASS |
| --ai #c4b5fd on canvas / surface-1 / surface-2 | 11.04 / 10.72 / 9.71 | 4.5:1 | PASS |
| --verified #5eead4 on canvas / surface-1 / surface-2 | 13.78 / 13.38 / 12.12 | 4.5:1 | PASS |
| --neutral-status #a3a3a3 on canvas / surface-1 / surface-2 | 8.08 / 7.85 / 7.11 | 4.5:1 | PASS |
| --ok on its tint over canvas / surface-0 / surface-1 | 10.61 / 10.97 / 10.16 | 4.5:1 | PASS |
| --warn on its tint over canvas / surface-0 / surface-1 | 10.99 / 11.44 / 10.59 | 4.5:1 | PASS |
| --fail on its tint over canvas / surface-0 / surface-1 | 9.77 / 10.15 / 9.42 | 4.5:1 | PASS |
| --info on its tint over canvas / surface-0 / surface-1 | 11.03 / 11.42 / 10.56 | 4.5:1 | PASS |
| --ai on its tint over canvas / surface-0 / surface-1 | 10.01 / 10.39 / 9.56 | 4.5:1 | PASS |
| --verified on its tint over canvas / surface-0 / surface-1 | 12.35 / 12.77 / 11.78 | 4.5:1 | PASS |
| --text (notice body) on ok / warn / fail / info tints over canvas | 12.47 / 12.38 / 12.46 / 12.41 | 4.5:1 | PASS |
| --text (notice body) on the same tints over surface-1 | 11.94 / 11.92 / 12.01 / 11.87 | 4.5:1 | PASS |

Automated accessibility (axe-core 4.10.3, tags wcag2a/wcag2aa/wcag21a/wcag21aa, run by `.agents/tasks/restyle-walkthrough.mjs` with seeded data on screen): 0 violations on `/`, `/sme`, `/sme/readiness`, `/documents/[id]`, `/buyer`, `/buyer/opportunities/1`, `/buyer/opportunities/1/results`, `/buyer/audit` and `/admin` at 1280x800, and on `/`, `/sme`, `/buyer/opportunities/1/results`, `/buyer/audit` and `/admin` at 390x844. The one finding during the run was fixed: the fairness tables at 390px were a non-focusable scroll region (serious), so their wrappers are now `role="region"` with an `aria-label` and `tabIndex={0}`.

Computed contrast and automated keyboard and axe checks aren't full WCAG validation. That still needs manual testing with assistive technologies and an expert accessibility review.

## 4. Component patterns
- Eyebrow (`components/Eyebrow.tsx`, `.eyebrow`): xs uppercase widest `--text-muted` label, 6px accent dot and a 4rem hairline. It sits above every page title.
- Section index (`components/SectionIndex.tsx`, `.section-index`): mono xs accent `01 / PROFILE`. It's `aria-hidden` because it repeats the heading below it; heading texts are unchanged.
- Buttons, all square, xs semibold uppercase widest, 300ms colour transitions:
  - Primary (default `button`): accent fill with black text, inverting to white fill with black text on hover and focus.
  - `button.secondary`: transparent with a `--control-border` outline, white text, and a `--surface-2` hover.
  - `button.danger`: rose outline that fills rose with black text on hover. It never uses the accent.
  - `.compact` for the shortlist Move up/down buttons, which carry `ArrowUp`/`ArrowDown` icons.
  - `.button-link`: a link that looks like the primary button (accent fill, black text, square, xs uppercase widest, white inversion on hover and focus, accent focus ring). Used for "Sign in to the demo" on the landing page.
  - `.link-arrow`: underlined uppercase text link with an accent `ArrowRight`/`ArrowUpRight` that nudges 4px on hover and focus.
  - `.btn-circle`: 64px (48px on mobile) outline circle. Its row's `:hover`/`:focus-within` fills it with the accent and rotates the `Plus` 45°.
  - `.icon-button`: menu open/close.
- Pills (`.badge`, `.pill`): rounded-full, 1px border, xs. Status and lineage variants recolour the border and text and add the 8% tint. The header AI-mode pill is mono uppercase: Cached is a neutral outline with `Database`, and Live has an accent outline and text with a pulsing 6px accent dot. Its text is unchanged ("AI mode: Cached" / "AI mode: Live" / "AI mode: unknown").
- Numbered row lists (`.row-list`, `.row`, `.row-inner`, `.row-index`): hairline-separated rows with a mono `01` index that turns accent and a `--surface-1` background on hover/focus-within. Used for documents, buyer requests, readiness actions, opportunities, gaps, skills, overrides and the landing sections.
- Sign-in choice rows (`.choice-list`, `label.choice`): each row is a `<label>` wrapping a native radio, a mono `01` index and `.choice-title` / `.choice-desc` text, inside a `<fieldset>` with a numbered `<legend>`. The checked row gets a 2px accent left edge and a `--surface-1` background via `:has(input:checked)`; the radio keeps its own accent focus ring.
- Pagination (`components/Pagination.tsx`, `.pagination`): `<nav aria-label="{list} pagination">` with a `role="status"` line "Showing 21–40 of 57", Previous/Next and numbered page buttons. The current page has `aria-current="page"` and the accent fill. The ends use `aria-disabled="true"` (still focusable and announced, muted text, no low opacity). Gaps (`…`) are `aria-hidden`. The page lives in the URL (`?page=`, `?eligible_page=`, …) so refresh and Back work, and the component renders nothing when the list fits on one page.
- Capability line (`.capability-line`): an always-visible "Capability match (n / 100): …" line under each result card's meta, with a hairline top border. The Score breakdown `<details>` stays collapsed.
- Result rows (`.result-card`): a bordered row with a 2px left edge in the status colour. The grid shows a mono 3xl rank (accent, `aria-label="Rank n"`, text `#n`), an uppercase name with pills, and a right-aligned mono score.
- Timeline (`.timeline`, `.timeline-list`): a 4/8 grid with a sticky left heading column. Each entry has a mono `<time>`, an uppercase action h3, a role pill (visually hidden "Role: " prefix) and a `<dl class="audit-meta">` with visible Actor / Entity / Details / Reason labels.
- Stat grid (`.stat-grid`): big mono `--fs-5xl` numbers with uppercase labels. DOM order is label then number (textContent "Eligible 2"), and `flex-direction: column-reverse` shows the number on top. Decision stats keep a visually hidden colon, so the text reads "Overrides: 1".
- Forms: dark square fields (`--surface-0`) with a 1px `--control-border`. Focus turns the border accent and adds the accent outline. Radios and checkboxes use `accent-color: var(--accent)`, and the file input's selector button is styled like a secondary button. Labels are xs uppercase widest `--text-muted`.
- Tables: header row xs uppercase widest on `--surface-2`, hairline rows with a hover tint, mono `.num` cells, low-confidence rows amber-tinted with a 2px amber edge, and conflict rows rose-tinted.
- Dialog (`.dialog`): `--surface-1`, square, 1px `--line-strong`, uppercase title, black 80% blurred backdrop. The native `showModal` focus trap and opener restore are unchanged.
- Notices (`.notice`): a 2px left border in the status colour on its tint, with a leading lucide icon and the body in `--text`.
- Document highlight `mark`: accent background, black text, 2px white outline.
- `details/summary`: uppercase xs widest with an accent chevron that rotates when open.
- Shell:
  - Demo-data banner: mono xs uppercase strip with an accent dot, in normal flow on every page, `role="note"`, text unchanged.
  - Header: sticky from 768px up, `rgb(5 5 5 / .85)` with `backdrop-filter: blur(12px)` and a hairline bottom border.
  - `NET / LINKS` lockup: `Crosshair` icon that rotates 90° on hover/focus, accent slash, `aria-label="NetLinks home"`.
  - Nav links: xs uppercase widest, with an accent dot on the active link.
  - Account menu (`components/AccountMenu.tsx`): a disclosure button (`aria-expanded`, `aria-controls`, accessible name "Account: {name}, {role}") showing the persona name and a role pill, and a square `--surface-1` panel with the persona, role and mono demo email, a "Switch account (demo)" heading over persona buttons (the current one has `aria-current="true"` and a check icon) and a secondary "Sign out" button. Opening focuses the first persona button; Escape closes it and restores focus to the trigger; outside click and route change close it. Signed out, the header shows a "Sign in" `.link-arrow` instead (hidden on `/login`).
  - Mobile overlay menu (`components/MobileMenu.tsx`, below 1024px): full-screen `role="dialog" aria-modal="true" aria-label="Menu"`. It traps Tab/Shift+Tab, closes on Escape, link click or route change, locks body scroll, restores focus to "Open menu", and is `inert` when closed.
  - Footer (`components/Footer.tsx`): lockup, "Built for the YES AI Hackathon 2026 · Prototype with fictional demo data · No real authentication", "© NetLinks prototype".
- Landing:
  - Hero: eyebrow, display h1 "Match. / Prove. / Shortlist.", light lead, a `.button-link` "Sign in to the demo" and `.link-arrow` links.
  - `.hero-graphic`: CSS radial and conic grayscale gradients plus an inline SVG `feTurbulence` noise layer, fading to the canvas.
  - Decorative accent square with `ArrowDownLeft`, shown from 1100px so it never collides with the headline.
  - Rotating `.stamp` with "Explainable matching •" on a circular `textPath` (`useId` path id).
  - Full-bleed `.landing-section` blocks (alternating `.alt`), each with a section index and an h2: `01 / PROBLEM`, `02 / HOW IT WORKS` (`id="how"`, five numbered steps), `03 / WHO IT'S FOR`, `04 / TRUST & PRIVACY`, `05 / ROADMAP`, `06 / DEMO` (sign-in call to action). Static text only: no metrics, logos, testimonials or partner claims, and no role rows (sign-in lives on `/login`).
  - Full-bleed accent `.manifesto`: "Rules decide eligibility." in black and "AI explains. Humans decide." in white at display size.

## 5. Where each pattern is used
| Page | Patterns |
|---|---|
| `/` | hero, hero graphic, accent square, stamp, eyebrow, button-link, link-arrow, landing sections `01 / PROBLEM` … `06 / DEMO` with numbered rows, manifesto |
| `/login` | eyebrow "Demo sign-in", info notice, numbered fieldsets with sign-in choice rows (role, persona), read-only demo email and password fields, primary button |
| `/sme` | eyebrow "SME workspace", page title, mono meta, link-arrow, `01 / UPLOAD`, `02 / PROFILE`, `03 / SHARING`, document rows with `FileText`, profile table with lineage pills, low-confidence and conflict rows, dialog, pagination (documents) |
| `/sme/readiness` | eyebrow "SME readiness", `01 / REQUESTS`, `02 / UPLOAD`, `03 / OPPORTUNITY` (+n), numbered request and action rows, status pills, pagination (requests) |
| `/documents/[id]` | eyebrow "Source document", `01 / PAGE`, mono document page, accent `mark` |
| `/buyer` | eyebrow "Buyer workspace", numbered opportunity rows, mono meta, link-arrows, pagination (server-side) |
| `/buyer/opportunities/[id]` | eyebrow "Requirements", `01 / RFQ`, `02 / MANDATORY`, `03 / PREFERRED`, `04 / WEIGHTS`, dark fields, mono weights and total |
| `/buyer/opportunities/[id]/results` | eyebrow "Matching results", `01 / RUN`, `02 / ELIGIBLE`, `03 / NEEDS REVIEW`, `04 / NOT ELIGIBLE`, `SHORTLIST`, result rows, side-by-side panels (amber dates, rose conflicts), score table with mono cells, capability line, numbered shortlist, pagination per group; at ≥1280px a 4/8 grid with a sticky shortlist |
| `/buyer/audit` | timeline with sticky left heading, mono times, role pills, labelled `dl`, Event type and Role filters, pagination (20 per page, newest first, server-side) |
| `/admin` | eyebrow "YES Admin", `01 / PIPELINE` … `07 / RESET`, stat grids, mono captions, numbered gap/skill/override rows, fairness tables, radio rows, rose danger button, dialog, pagination (overrides) |

## 6. Motion
- Colour, border and background transitions run at 300ms (`--dur-fast`): buttons, links, nav, fields, the summary chevron. Row hover backgrounds and circle fills run at 500ms (`--dur-med`).
- The arrow nudge (`translateX(4px)`, 300ms) applies to `.link-arrow`. Icon rotation covers the lockup crosshair (90°, 500ms) and the role-row plus (45°, 500ms).
- The manifesto scales to 1.05 on hover/focus-within (700ms). The stamp spins every 10s linearly. The Live AI-mode dot pulses every 2s. The mobile menu fades in over 500ms.
- `prefers-reduced-motion: reduce` sets `animation: none` and near-zero transition durations everywhere, and forces `transform: none` on the stamp, manifesto, arrows, circle icons and lockup icon. The walkthrough confirms the stamp's computed `animation-name` is `none` under reduced motion and `spin` otherwise.

## 7. Deviations from the reference and why
1. No portfolio content was copied (names, the freelance stamp, location and coordinates, contact details, socials, "Let's work together", "Let's Talk"). Only the visual language was requested.
2. No remote assets (Tailwind CDN, unpkg lucide, Unsplash, web fonts). The demo must run offline from the local Docker stack. Photography is replaced by a CSS/SVG abstract graphic, and icons come from the pinned `lucide-react` package.
3. Small informational text is never neutral-500/600 on #050505, because those measure 4.30 and 2.61:1 and fail 4.5:1. The minimum is neutral-400 (8.08:1).
4. Primary buttons use black text on #FF3000, because white measures 3.70:1 and fails for small text. White on the accent appears only at manifesto display size (large text, ≥ 3:1).
5. Status colours are separate from the accent (green, amber, rose, sky, violet, teal), and every status carries a text label and an icon, so colour is never the only signal.
6. Scrollbars stay visible (`scrollbar-width: thin`, dark thumb). Hiding them removes an affordance.
7. The header has no `mix-blend-difference`; it is a translucent #050505 bar with blur and a hairline, which keeps text contrast predictable. Below 768px the header (which wraps to two rows to keep the account menu and AI mode visible) scrolls with the page instead of sticking, so it doesn't cover a quarter of a phone screen.
8. Nothing is revealed only on hover. The reference hides service descriptions until hover; here they are always visible, and hover/focus-within only adds decoration. That works for keyboard and touch.
9. Reduced motion is honoured (see section 6).
10. Every interactive element has a visible accent focus ring. The Dialog keeps its focus trap, and the mobile menu traps focus, closes on Escape and restores focus to its trigger.
11. UX changes: `/` is now a public landing page (hero, problem, how it works, who it's for, trust and privacy, roadmap and a "Try the demo" sign-in call to action) instead of an auto-redirect; signing in happens on `/login`, and the top-bar account menu switches or signs out the demo persona. The audit log is a labelled timeline instead of a table, with the same seven data points, each labelled. The fairness tables became focusable scroll regions to fix the axe finding.
12. The top-bar role-switcher `<select>` is replaced by an account menu. It uses the disclosure pattern (a button with `aria-expanded` plus a panel of ordinary buttons) rather than an ARIA `role="menu"`: it is simpler, fully keyboard operable (Tab, Enter, Escape with focus restore) and works with screen readers in browse mode, where ARIA menus need application-mode keyboard handling.

## 8. Verification record
- `npm run lint`, `npm run typecheck` and `npm run build` in `frontend/` all pass, building all 9 app routes plus `/_not-found`.
- `docker compose up -d --build`: web `http://127.0.0.1:3000/` returns HTTP 200, and the API returns 200. `docker compose run --rm backend pytest -q` reports 247 passed.
- `node .agents/tasks/restyle-walkthrough.mjs` reports 221 PASS / 0 FAIL against the Docker stack in headless Chromium (puppeteer-core 25.15.0 + chrome-headless-shell). It covers the full demo-script section 2 (R-SHELL, R-SME, R-BUY, R-RES, R-DEC, R-AUD, R-RDY, R-ADM, R-MOB, R-CON), the restyle checks S-1…S-9, computed-style checks (canvas, uppercase semibold headings, mono accent section index, manifesto accent, circular buttons, hairline header) and axe. It produced 0 console errors and 0 non-local requests. It starts and ends with a demo reset.
- Viewport-only screenshots (never full-page) of every page at 1280x800 and 390x844 are in `.agents/tasks/restyle-shots/` (local evidence, not committed).
- Landing, sign-in and pagination: `node .agents/tasks/landing-login-walkthrough.mjs` (supersedes the restyle walkthrough, whose role-switcher checks no longer apply) reports 300 PASS / 0 FAIL. It re-runs every demo-script section 2 check through the sign-in page and the account menu, adds the landing (S-1), sign-in and account-menu (L-1…L-6) and pagination checks, finds 0 axe violations on `/`, `/login` and every workspace page at 1280 and 390, and has 0 console errors and 0 non-local requests. `pytest -q` reports 269 passed.
