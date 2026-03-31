# TripPlannerAgent — Frontend Style Guide

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [Color System](#color-system)
  - [Core Palette — Light Mode](#core-palette--light-mode)
  - [Core Palette — Dark Mode](#core-palette--dark-mode)
  - [Semantic Colors](#semantic-colors)
  - [Color Usage Guidelines](#color-usage-guidelines)
- [Typography](#typography)
  - [Font Stack](#font-stack)
  - [Type Scale](#type-scale)
  - [Typography Rules](#typography-rules)
- [Spacing & Layout](#spacing--layout)
  - [Spacing Scale](#spacing-scale)
  - [Layout Patterns](#layout-patterns)
  - [Grid & Container](#grid--container)
  - [Responsive Breakpoints](#responsive-breakpoints)
- [Borders & Corners](#borders--corners)
- [Shadows & Elevation](#shadows--elevation)
- [Iconography](#iconography)
- [Animations & Motion](#animations--motion)
- [Component Styling Conventions](#component-styling-conventions)
  - [Buttons](#buttons)
  - [Cards](#cards)
  - [Badges](#badges)
  - [Chat Messages](#chat-messages)
  - [Inputs](#inputs)
  - [Toasts & Notifications](#toasts--notifications)
- [Interaction States](#interaction-states)
- [Empty & Loading States](#empty--loading-states)
- [Accessibility](#accessibility)
- [Anti-Patterns](#anti-patterns)

---

## Design Philosophy

TripPlannerAgent is a conversational AI tool for Airbnb trip planning and cost analysis. The visual language should feel like **a capable, trusted travel assistant**: clean, information-dense, and efficient. Every design decision serves the data — listings, costs, and comparisons.

**Guiding principles:**

1. **Clarity over decoration** — Trip planning involves complex data (costs, dates, amenity comparisons). Prioritize scannability and hierarchy. Decorative elements must never obscure functional information.
2. **Data-dense but approachable** — Listing cards pack key info (title, price, beds, rating, amenities) without feeling cluttered. Visual hierarchy is nonnegotiable.
3. **Conversational flow** — The UI is a chat. Designs should feel like a conversation — streaming responses, progressive disclosure, structured data appearing inline.
4. **Cost-focused** — Per-person cost is the primary metric. Total cost is secondary. Nightly rate is context. The visual hierarchy must reflect this priority.
5. **Streaming-native** — Design for incremental disclosure. Results appear as the agent discovers them, not all at once.

---

## Color System

TripPlannerAgent uses an OKLCH color system with full **light and dark mode** support. All tokens are CSS custom properties defined in `app/assets/css/main.css`.

### Core Palette — Light Mode

Defined in `:root`.

| Token                    | OKLCH Value                  | Description                                 |
| ------------------------ | ---------------------------- | ------------------------------------------- |
| `--background`           | `oklch(1 0 0)`               | Pure white page background                  |
| `--foreground`           | `oklch(0.129 0.042 264.695)` | Deep slate — primary text color             |
| `--card`                 | `oklch(1 0 0)`               | Card surface — same as background           |
| `--card-foreground`      | `oklch(0.129 0.042 264.695)` | Card text — same as foreground              |
| `--primary`              | `oklch(0.609 0.126 221.723)` | Cyan-600 — brand accent, CTAs, focus rings  |
| `--primary-foreground`   | `oklch(0.985 0 0)`           | White — text on primary backgrounds         |
| `--secondary`            | `oklch(0.968 0.007 247.896)` | Subtle slate — secondary backgrounds        |
| `--secondary-foreground` | `oklch(0.208 0.042 265.755)` | Dark slate — text on secondary backgrounds  |
| `--muted`                | `oklch(0.968 0.007 247.896)` | Muted backgrounds — empty states, subtle UI |
| `--muted-foreground`     | `oklch(0.554 0.046 257.417)` | Muted text — timestamps, secondary labels   |
| `--accent`               | `oklch(0.968 0.007 247.896)` | Accent surface — hoverable elements         |
| `--accent-foreground`    | `oklch(0.208 0.042 265.755)` | Text on accent surfaces                     |
| `--border`               | `oklch(0.929 0.013 255.508)` | Cool slate — borders, dividers              |
| `--input`                | `oklch(0.929 0.013 255.508)` | Input borders — matches general border      |
| `--ring`                 | `oklch(0.609 0.126 221.723)` | Focus ring — matches primary cyan           |

### Core Palette — Dark Mode

Defined in `.dark`. Surfaces invert: deep slate backgrounds with lighter elevated cards. Primary cyan shifts brighter for readability. Refer to `app/assets/css/main.css` for full dark mode values.

### Semantic Colors

Defined in both light and dark modes. Dark mode variants are brighter for contrast on dark surfaces.

| Token                      | Usage (Light)                               | Light OKLCH                  |
| -------------------------- | ------------------------------------------- | ---------------------------- |
| `--destructive`            | Errors, failures, destructive actions       | `oklch(0.577 0.245 27.325)`  |
| `--destructive-foreground` | Text on destructive backgrounds             | `oklch(0.985 0 0)`           |
| `--success`                | Completed operations, successful results    | `oklch(0.596 0.145 163.225)` |
| `--success-foreground`     | Text on success backgrounds                 | `oklch(0.985 0 0)`           |
| `--warning`                | Rate limiting, scraping cautions, attention | `oklch(0.769 0.188 70.08)`   |
| `--warning-foreground`     | Text on warning backgrounds                 | `oklch(0.208 0.042 265.755)` |
| `--info`                   | Informational toasts, tool progress badges  | `oklch(0.685 0.169 237.323)` |
| `--info-foreground`        | Text on info backgrounds                    | `oklch(0.985 0 0)`           |

### Color Usage Guidelines

- **Primary cyan** is the brand color — use for CTAs, active nav elements, focus rings, and highlighted metrics. Do not overuse; it should guide the eye, not overwhelm.
- **Background** is pure white (light) or deep slate (dark). Cards share the background color; elevation is created via borders and shadows, not background contrast.
- **Semantic colors are for status only** — `success` for completed actions, `destructive` for errors, `warning` for rate limiting or anti-bot cautions, `info` for progress indicators.
- **Use token classes exclusively** — `bg-primary`, `text-foreground`, `border-border`. Never hardcode OKLCH values or hex strings in component code.
- **Text hierarchy**: `text-foreground` for primary text, `text-muted-foreground` for timestamps and secondary labels. Never use arbitrary gray values.
- **Both modes must work** — Always test designs in light and dark. If a color doesn't map to a token, it will break in one mode.

---

## Typography

### Font Stack

| Role    | Font Family          | Fallback Stack                         |
| ------- | -------------------- | -------------------------------------- |
| **All** | Inter (system stack) | `system-ui, -apple-system, sans-serif` |

TripPlannerAgent uses a single font stack — the Tailwind default system font. No decorative heading font. The interface is functional and data-dense; hierarchy is created through weight and size, not font family.

### Type Scale

| Role              | Tailwind Class | Size | Weight                | Usage                                         |
| ----------------- | -------------- | ---- | --------------------- | --------------------------------------------- |
| **Page Title**    | `text-2xl`     | 24px | `font-bold` (700)     | App header branding                           |
| **Section Title** | `text-xl`      | 20px | `font-semibold` (600) | Week headers, result group titles             |
| **Card Title**    | `text-lg`      | 18px | `font-semibold` (600) | Listing names, cost table headers             |
| **Subtitle**      | `text-base`    | 16px | `font-medium` (500)   | Sub-headings, emphasized labels               |
| **Body**          | `text-sm`      | 14px | `font-normal` (400)   | Chat messages, descriptions, listing details  |
| **Body Small**    | `text-xs`      | 12px | `font-normal` (400)   | Timestamps, helper text, secondary metadata   |
| **Caption**       | `text-xs`      | 12px | `font-semibold` (600) | Badge labels, tool status indicators          |
| **Cost/Price**    | `text-lg`      | 18px | `font-semibold` (600) | Per-person costs, nightly rates, total prices |
| **Button Label**  | `text-sm`      | 14px | `font-medium` (500)   | All button text                               |

### Typography Rules

- **Single font stack** — no heading vs body font distinction. Hierarchy comes from weight and size.
- **Line height**: Tailwind defaults (`leading-normal` for body, `leading-tight` for headings).
- **Chat messages** use `text-sm` — the chat is data-dense and the primary interface.
- **Cost figures are prominent** — `text-lg font-semibold` makes them the most visible element in listing cards and cost tables.
- **Text color hierarchy**: `text-foreground` for primary text, `text-muted-foreground` for secondary text. Always use semantic token classes.
- **Never underline text** except actual links on hover.

---

## Spacing & Layout

### Spacing Scale

Use Tailwind's 4px-based spacing scale consistently:

| Token | Value | Usage                                                      |
| ----- | ----- | ---------------------------------------------------------- |
| `1`   | 4px   | Icon-to-text gaps, tight internal padding                  |
| `2`   | 8px   | Badge padding, compact element spacing, message bubble gap |
| `3`   | 12px  | Input padding, small card internal spacing                 |
| `4`   | 16px  | Card padding, standard element gap, chat message spacing   |
| `5`   | 20px  | Grid gaps between listing cards                            |
| `6`   | 24px  | Card padding (large), section margin                       |
| `8`   | 32px  | Section spacing, page padding                              |
| `10`  | 40px  | Large section gaps                                         |
| `12`  | 48px  | Page top/bottom margin                                     |

### Layout Patterns

- **Chat message list**: `flex flex-col gap-4` — vertical stack of message bubbles, consistent gap.
- **Chat content area**: `max-w-3xl mx-auto` — centered, constrained width for readability.
- **Listing cards in chat**: Stacked vertically within agent message bubbles; on wider screens, can sit side-by-side via `grid grid-cols-1 md:grid-cols-2 gap-4`.
- **Cost table rows**: `flex items-center justify-between` or table layout with `space-y-2`.
- **Full-height layout**: `min-h-screen flex flex-col` — header at top, chat area fills remaining space, input fixed at bottom.

### Grid & Container

| Context           | Container Width | Padding        |
| ----------------- | --------------- | -------------- |
| Chat message area | `max-w-3xl`     | `px-4`         |
| Chat input        | `max-w-3xl`     | `px-4`         |
| Header            | full width      | `px-4 sm:px-6` |
| Listing card grid | within message  | `gap-4`        |
| Cost table        | within message  | `p-4`          |

### Responsive Breakpoints

TripPlannerAgent is designed **desktop-first** (primary use is trip planning on a computer) but must work on all sizes:

| Breakpoint | Tailwind Prefix | Width    | Layout Changes                                             |
| ---------- | --------------- | -------- | ---------------------------------------------------------- |
| Default    | (none)          | < 640px  | Single column, stacked listing cards, full-width input     |
| `sm:`      |                 | ≥ 640px  | Wider message bubbles, horizontal badges                   |
| `md:`      |                 | ≥ 768px  | Side-by-side listing cards, expanded cost tables           |
| `lg:`      |                 | ≥ 1024px | `max-w-3xl` chat area, comfortable whitespace              |
| `xl:`      |                 | ≥ 1280px | Generous side margins, possible future sidebar for history |

---

## Borders & Corners

All border-radius values derive from `--radius: 0.625rem` (10px) defined in `main.css`:

| Element            | Computed Radius        | Tailwind Class |
| ------------------ | ---------------------- | -------------- |
| **Buttons**        | `calc(--radius - 2px)` | `rounded-md`   |
| **Cards**          | `calc(--radius + 4px)` | `rounded-xl`   |
| **Inputs**         | `calc(--radius - 2px)` | `rounded-md`   |
| **Badges**         | `calc(--radius - 2px)` | `rounded-md`   |
| **Chat bubbles**   | `var(--radius)`        | `rounded-lg`   |
| **Modals/Dialogs** | `calc(--radius + 4px)` | `rounded-xl`   |

**Rule**: TripPlannerAgent favors consistent, moderate rounding — not sharp, not pillowed. Badges are `rounded-md` (not `rounded-full`) per the actual CVA definitions.

Borders:

- Default border: `border border-border` (OKLCH slate token)
- Dividers: `border-t border-border` or `divide-y divide-border`
- Focus ring: `ring-1 ring-ring` (primary cyan)

---

## Shadows & Elevation

Subtle, standard Tailwind shadows — no custom warm-tinted shadows:

| Level       | Tailwind Class | Usage                                        |
| ----------- | -------------- | -------------------------------------------- |
| **None**    | `shadow-none`  | Flat elements, inline content, chat bubbles  |
| **Default** | `shadow`       | Cards at rest (per Card.vue)                 |
| **Small**   | `shadow-sm`    | Inputs, subtle elevation                     |
| **Medium**  | `shadow-md`    | Cards on hover, dropdowns, floating elements |
| **Large**   | `shadow-lg`    | Modals, overlays                             |

- Cards use `shadow` at rest (defined in Card.vue component).
- Interactive cards can transition to `shadow-md` on hover with `transition-shadow duration-200`.
- Shadows work equally well in light and dark mode — no warm tinting needed.

---

## Iconography

- **Library**: Lucide icons via `lucide-vue-next` (direct component imports)
- **Style**: Outline icons — consistent stroke width, clean geometry
- **Usage**: `<Send :size="20" />` — import the icon component directly from `lucide-vue-next`
- **Sizing**: `:size="16"` inline, `:size="20"` in buttons, `:size="24"` standalone or headings
- **Color**: Inherits parent text color. Use `text-primary` for brand-emphasized icons, `text-muted-foreground` for subtle icons.
- **Touch targets**: Icon-only buttons must be at least 44×44px total (padding included)

### Key Icons

| Context        | Icon           | Usage                          |
| -------------- | -------------- | ------------------------------ |
| Send message   | `Send`         | Chat input send button         |
| Agent thinking | `Loader2`      | Animated spin during streaming |
| Airbnb link    | `ExternalLink` | Open listing in new tab        |
| Rating         | `Star`         | Listing rating display         |
| Beds           | `Bed`          | Bed count badge                |
| Location       | `MapPin`       | Neighborhood label             |
| Price          | `DollarSign`   | Cost breakdown header          |
| Error          | `AlertCircle`  | Error state indicator          |
| Success        | `CheckCircle`  | Completed search               |
| Search         | `Search`       | Searching tool badge           |
| Calendar       | `Calendar`     | Check-in / check-out dates     |
| Participants   | `Users`        | Participant count              |

---

## Animations & Motion

### Transition Patterns

| Trigger                | Animation               | Implementation                      |
| ---------------------- | ----------------------- | ----------------------------------- |
| **Page transition**    | Gentle fade (200ms)     | Vue `<Transition>` on `<NuxtPage>`  |
| **Chat message enter** | Fade + slide-up (300ms) | CSS `@keyframes` transition         |
| **Streaming dots**     | Looping pulse           | CSS `@keyframes` with `ease-in-out` |
| **Toast enter**        | Slide from top (300ms)  | Sonner built-in                     |
| **Button hover**       | Background transition   | `transition-colors duration-150`    |
| **Card hover shadow**  | Shadow elevation        | `transition-shadow duration-200`    |
| **Button press**       | Slight scale-down       | `active:scale-[0.98]`               |

### Motion Guidelines

- **Duration**: 150–300ms for micro-interactions, 200–400ms for larger transitions.
- **Maximum**: 400ms. Nothing should feel sluggish.
- **Easing**: `ease-out` for entrances, `ease-in` for exits, `ease-in-out` for state changes.
- **Loading**: Use Skeleton components for data loading, `Loader2` spinner for inline button loading, animated `StreamingDots` for agent thinking state.
- **Restraint**: Animation should feel natural. If it draws attention to itself, it's too much.
- **Reduced motion**: Respect `prefers-reduced-motion` — use instant transitions and disable pulsing animations.

---

## Component Styling Conventions

### Buttons

Buttons use CVA variants from `app/components/ui/button/index.ts`:

| Variant         | Background    | Text                   | Usage                                      |
| --------------- | ------------- | ---------------------- | ------------------------------------------ |
| **default**     | `primary`     | `primary-foreground`   | Main CTAs: Send message, Start search      |
| **secondary**   | `secondary`   | `secondary-foreground` | Secondary actions: View listing, Copy link |
| **outline**     | `background`  | token text + border    | Tertiary: filter toggles, sort options     |
| **ghost**       | transparent   | `accent-foreground`    | Subtle: Close, Dismiss, icon-only buttons  |
| **destructive** | `destructive` | `destructive-fg`       | Dangerous: Clear chat, Cancel search       |
| **link**        | transparent   | `primary`              | Inline text links: Airbnb listing URL      |

Sizes: `default` (h-9), `xs` (h-7), `sm` (h-8), `lg` (h-10), `icon` (h-9 w-9), `icon-sm` (size-8), `icon-lg` (size-10).

- Hover: Background shifts per variant (built into CVA).
- Active: `active:scale-[0.98]` for tactile feedback.
- Disabled: `opacity-50`, `pointer-events-none`.
- All buttons: `rounded-md text-sm font-medium`.

### Cards

From `app/components/ui/card/Card.vue`:

- **Classes**: `rounded-xl border bg-card text-card-foreground shadow`
- **Padding**: CardContent uses `p-6` default, `pt-0` when below CardHeader
- **Hover** (interactive cards): `hover:shadow-md transition-shadow duration-200`
- **Dark mode**: `bg-card` automatically adjusts via CSS variables

Listing cards compose Card with CardHeader (title + badges), CardContent (details + cost), and CardFooter (Airbnb link).

### Badges

From `app/components/ui/badge/index.ts`:

- **Shape**: `rounded-md` (not `rounded-full`)
- **Size**: `text-xs font-semibold px-2.5 py-0.5`
- **Variants**:
  - `default` — Primary background. Use for ranking badges (Best Price, Best Value, Best Location).
  - `secondary` — Subtle background. Use for amenity tags (AC, W/D, Pool, Rooftop).
  - `destructive` — Red background. Use for error states, anti-bot detected.
  - `outline` — Bordered, no fill. Use for neutral metadata (bed/bath count, neighborhood).

### Chat Messages

The chat is the primary interface. Message styling must distinguish user from agent:

| Element           | User Message                         | Agent Message                        |
| ----------------- | ------------------------------------ | ------------------------------------ |
| **Alignment**     | Right-aligned                        | Left-aligned                         |
| **Background**    | `bg-primary text-primary-foreground` | `bg-muted text-foreground`           |
| **Border radius** | `rounded-lg`                         | `rounded-lg`                         |
| **Max width**     | ~70% of chat area                    | ~85% of chat area (more content)     |
| **Content**       | Plain text                           | Markdown + ListingCards + CostTables |

Agent messages can embed structured components (ListingCard, CostTable, WeekSummary) inline within the message bubble.

### Inputs

The chat input is the primary input — fixed to the bottom of the viewport:

- **Chat input**: `rounded-lg border border-input bg-background text-sm` with `focus:ring-1 focus:ring-ring`
- **Send button**: Icon-only button (`Send` icon) aligned right within the input container. Primary variant when text is present, ghost when empty.
- **Disabled state**: During streaming — `opacity-50 pointer-events-none` on input and send button.

### Toasts & Notifications

In-app toasts via vue-sonner (Sonner component):

| Type        | Icon            | Token Color   | Example                                |
| ----------- | --------------- | ------------- | -------------------------------------- |
| **Success** | `CheckCircle`   | `success`     | "Search completed — 5 listings found"  |
| **Error**   | `AlertCircle`   | `destructive` | "Agent connection failed"              |
| **Info**    | `Info`          | `info`        | "Switching to cached scraping mode"    |
| **Warning** | `AlertTriangle` | `warning`     | "Rate limited by Airbnb — retrying..." |

---

## Interaction States

Every interactive element must have clearly distinguishable states:

| State         | Visual Treatment                                                |
| ------------- | --------------------------------------------------------------- |
| **Default**   | Base styling as defined in component section                    |
| **Hover**     | Subtle background shift or shadow increase; `transition` always |
| **Focus**     | `ring-1 ring-ring` — visible cyan focus ring for keyboard nav   |
| **Active**    | Slightly darker background; `scale-[0.98]` for tactile feedback |
| **Disabled**  | `opacity-50 pointer-events-none`; no hover/focus effects        |
| **Loading**   | `Loader2` spinner replacing text; button width remains stable   |
| **Streaming** | Pulsing dots indicator; tool usage badge updates in real time   |
| **Selected**  | Primary accent — border or background tint from `primary` token |

---

## Empty & Loading States

### Empty States

Empty states should be encouraging and actionable:

| Context                   | Message Example                                       | Visual                        |
| ------------------------- | ----------------------------------------------------- | ----------------------------- |
| **No conversations**      | "Ready to plan your trip? Try asking about listings." | Subtle icon + example prompts |
| **No search results**     | "No listings matched your criteria — try adjusting."  | Search icon + retry CTA       |
| **Agent error**           | "Something went wrong — check your connection."       | AlertCircle icon + retry      |
| **Streaming interrupted** | "The search was interrupted — try again."             | Warning badge + retry CTA     |

- Center the message vertically in the chat area
- Include 2-3 example prompts as clickable chips or suggestions
- Use muted icon + `text-muted-foreground` text
- Include a CTA button for the most relevant action

### Loading States

- **Agent streaming**: `StreamingDots` component (animated dots) + `ToolBadge` showing current operation (Searching, Parsing, Calculating, Ranking)
- **Data fetching**: shadcn-vue Skeleton components matching the layout being loaded
- **Button submitting**: Replace text with `Loader2` spinner; keep button width stable
- **Never show a blank white screen** — always show either a skeleton, loader, or the streaming indicator

---

## Accessibility

- **Color contrast**: All text meets WCAG 2.1 AA (4.5:1 body text, 3:1 large text) in **both light and dark modes**. OKLCH tokens have been selected to maintain contrast across modes.
- **Focus indicators**: Visible `ring-1 ring-ring` (cyan) on all interactive elements. Never remove focus outlines.
- **Touch targets**: Minimum 44×44px for all tappable elements on mobile.
- **Keyboard navigation**: All interactive elements are keyboard-navigable via Reka UI primitives (built into shadcn-vue).
- **ARIA labels**: Icon-only buttons must have `aria-label`. Agent status badges should have descriptive text (e.g., `aria-label="Agent status: searching Airbnb"`).
- **Streaming accessibility**: Agent message area uses `aria-live="polite"` for screen reader updates during streaming.
- **Reduced motion**: Respect `prefers-reduced-motion` — disable streaming dot animation, use instant transitions.

---

## Anti-Patterns

Explicit things to **avoid** in TripPlannerAgent's frontend:

- **No hardcoded colors** — Always use CSS variable tokens via Tailwind classes (`bg-primary`, `text-foreground`). Never inline OKLCH, hex, or rgb values.
- **No missing dark mode** — Every screen must work in both light and dark. If you use a color, it must come from a token that has both mode definitions.
- **No inline styles** — All styling via Tailwind CSS utilities, using `cn()` for conditionals.
- **No custom CSS** beyond `main.css` token definitions and `@keyframes` — no `.scss`, no CSS modules.
- **No animations over 400ms** — Keep everything snappy and natural.
- **No decorative icons** — Every icon must convey meaning or indicate an action.
- **No text truncation on listing names** — Listing titles should always be fully visible in cards.
- **No color for meaning alone** — Always pair color with text labels (e.g., status badges show both color AND text).
- **No `$fetch` in components** — Use TanStack Query composables with auto-generated API client functions.
- **No server data in Pinia** — Pinia is for UI-only state. TanStack Query owns all server data.
- **No generic spinners for streaming** — Use `StreamingDots` + `ToolBadge` to show agent progress with context.
- **No cost truncation** — All cost figures (per-person, total, fees) must be fully visible; never hide behind ellipsis or overflow.
