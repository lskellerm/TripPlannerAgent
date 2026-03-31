# TripPlannerAgent — Figma Design System Rules

## Table of Contents

- [Framework & Stack](#framework--stack)
- [Design Tokens](#design-tokens)
  - [Color System](#color-system)
  - [Agent Status Tokens](#agent-status-tokens)
  - [Tailwind Token Mapping](#tailwind-token-mapping)
- [Typography](#typography)
- [Component Library](#component-library)
  - [Available Components](#available-components)
  - [Button Variants](#button-variants)
  - [Badge Patterns](#badge-patterns)
- [Custom Domain Components](#custom-domain-components)
- [Icon System](#icon-system)
- [Animations & Loading](#animations--loading)
- [Styling Approach](#styling-approach)
- [Project Structure](#project-structure)
- [Layout Shell](#layout-shell)
- [Design-to-Code Translation Rules](#design-to-code-translation-rules)
- [Key Design Conventions](#key-design-conventions)

---

## Framework & Stack

| Layer           | Technology              | Notes                                                          |
| --------------- | ----------------------- | -------------------------------------------------------------- |
| **Framework**   | Nuxt 3 (Vue 3)          | `<script setup lang="ts">` composition API, strict TypeScript  |
| **Styling**     | Tailwind CSS v4         | via `@tailwindcss/vite` plugin                                 |
| **Components**  | shadcn-vue              | Owned in `app/components/ui/`, built on Reka UI                |
| **Primitives**  | Reka UI                 | Headless component primitives under shadcn-vue                 |
| **Icons**       | Lucide                  | via `lucide-vue-next`, outline style                           |
| **State**       | TanStack Query + Pinia  | Server data via TanStack Query; Pinia for UI-only client state |
| **API Client**  | `@hey-api/openapi-ts`   | Auto-generated typed SDK from FastAPI OpenAPI spec             |
| **Router**      | Nuxt file-based routing | `app/pages/`                                                   |
| **Build**       | Vite (via Nuxt)         | SSR mode                                                       |
| **Package Mgr** | pnpm                    | Exclusively — never npm or yarn                                |

---

## Design Tokens

Tokens are defined as OKLCH CSS custom properties in `app/assets/css/main.css` and mapped in `tailwind.config.ts`.

### Color System

TripPlannerAgent uses a cyan-primary / slate-neutral OKLCH color scheme with full **light and dark mode** support.

#### Core Palette (Light Mode — `:root`)

| Token                    | OKLCH Value                  | Usage                                        |
| ------------------------ | ---------------------------- | -------------------------------------------- |
| `--background`           | `oklch(1 0 0)`               | Page background — pure white                 |
| `--foreground`           | `oklch(0.129 0.042 264.695)` | Primary text — deep slate                    |
| `--card`                 | `oklch(1 0 0)`               | Card surfaces                                |
| `--card-foreground`      | `oklch(0.129 0.042 264.695)` | Card text                                    |
| `--primary`              | `oklch(0.609 0.126 221.723)` | Brand cyan — CTAs, active nav, accents       |
| `--primary-foreground`   | `oklch(0.985 0 0)`           | Text on primary backgrounds                  |
| `--secondary`            | `oklch(0.968 0.007 247.896)` | Subtle slate background                      |
| `--secondary-foreground` | `oklch(0.208 0.042 265.755)` | Text on secondary backgrounds                |
| `--muted`                | `oklch(0.968 0.007 247.896)` | Muted backgrounds — empty states, subtle UI  |
| `--muted-foreground`     | `oklch(0.554 0.046 257.417)` | Muted text — timestamps, secondary labels    |
| `--accent`               | `oklch(0.968 0.007 247.896)` | Accent backgrounds — subtle cyan-tinted gray |
| `--accent-foreground`    | `oklch(0.208 0.042 265.755)` | Text on accent backgrounds                   |
| `--border`               | `oklch(0.929 0.013 255.508)` | Borders, dividers — cool slate tone          |
| `--input`                | `oklch(0.929 0.013 255.508)` | Input borders                                |
| `--ring`                 | `oklch(0.609 0.126 221.723)` | Focus ring — matches primary cyan            |

#### Semantic Colors (Light Mode)

| Token                      | OKLCH Value                  | Usage                                              |
| -------------------------- | ---------------------------- | -------------------------------------------------- |
| `--destructive`            | `oklch(0.577 0.245 27.325)`  | Errors, failures, destructive actions              |
| `--destructive-foreground` | `oklch(0.985 0 0)`           | Text on destructive backgrounds                    |
| `--success`                | `oklch(0.596 0.145 163.225)` | Completed operations, successful results           |
| `--success-foreground`     | `oklch(0.985 0 0)`           | Text on success backgrounds                        |
| `--warning`                | `oklch(0.769 0.188 70.08)`   | Rate limiting, scraping cautions, attention states |
| `--warning-foreground`     | `oklch(0.208 0.042 265.755)` | Text on warning backgrounds                        |
| `--info`                   | `oklch(0.685 0.169 237.323)` | Informational toasts, tool usage progress badges   |
| `--info-foreground`        | `oklch(0.985 0 0)`           | Text on info backgrounds                           |

#### Dark Mode (`.dark`)

Dark mode inverts the surface hierarchy (deep slate backgrounds, elevated cards in lighter slate) and shifts primary cyan brighter for readability. All semantic colors shift to brighter variants for contrast on dark surfaces. See `app/assets/css/main.css` for full dark mode token values.

### Agent Status Tokens

The AI agent progresses through distinct states during trip planning. Use semantic colors for status badges:

| Status         | Color Token   | Usage                                               |
| -------------- | ------------- | --------------------------------------------------- |
| `searching`    | `info`        | Agent is searching Airbnb — "🔍 Searching..."       |
| `parsing`      | `info`        | Agent is extracting listing data — "📄 Parsing..."  |
| `calculating`  | `primary`     | Agent is computing costs — "💰 Calculating..."      |
| `ranking`      | `primary`     | Agent is ranking results — "📊 Ranking..."          |
| `complete`     | `success`     | Agent has finished — results displayed              |
| `error`        | `destructive` | Something went wrong — error card with retry        |
| `rate-limited` | `warning`     | Airbnb anti-bot detected — switching to cached mode |

### Tailwind Token Mapping

Tokens map to Tailwind via `var()` references in `tailwind.config.ts`:

```ts
colors: {
  /* Core surface & text */
  background: 'var(--background)',
  foreground: 'var(--foreground)',
  card: {
    DEFAULT: 'var(--card)',
    foreground: 'var(--card-foreground)',
  },

  /* Brand */
  primary: {
    DEFAULT: 'var(--primary)',
    foreground: 'var(--primary-foreground)',
  },
  secondary: {
    DEFAULT: 'var(--secondary)',
    foreground: 'var(--secondary-foreground)',
  },
  accent: {
    DEFAULT: 'var(--accent)',
    foreground: 'var(--accent-foreground)',
  },

  /* Muted */
  muted: {
    DEFAULT: 'var(--muted)',
    foreground: 'var(--muted-foreground)',
  },

  /* Semantic status */
  destructive: {
    DEFAULT: 'var(--destructive)',
    foreground: 'var(--destructive-foreground)',
  },
  success: {
    DEFAULT: 'var(--success)',
    foreground: 'var(--success-foreground)',
  },
  warning: {
    DEFAULT: 'var(--warning)',
    foreground: 'var(--warning-foreground)',
  },
  info: {
    DEFAULT: 'var(--info)',
    foreground: 'var(--info-foreground)',
  },

  /* Interactive */
  border: 'var(--border)',
  input: 'var(--input)',
  ring: 'var(--ring)',
},
borderRadius: {
  sm: 'calc(var(--radius) - 4px)',
  md: 'calc(var(--radius) - 2px)',
  lg: 'var(--radius)',
  xl: 'calc(var(--radius) + 4px)',
},
```

`--radius` is set to `0.625rem` (10px) in `main.css`.

---

## Typography

TripPlannerAgent uses the system font stack (Tailwind defaults — Inter / system-ui). No custom heading font — the interface is functional and data-dense, not decorative.

| Element        | Weight       | Tailwind Classes        | Usage                                          |
| -------------- | ------------ | ----------------------- | ---------------------------------------------- |
| **Page Title** | 700 (bold)   | `text-2xl font-bold`    | App branding header                            |
| **Section**    | 600 (semi)   | `text-xl font-semibold` | Week headers, result section titles            |
| **Card Title** | 600 (semi)   | `text-lg font-semibold` | Listing names, cost table headers              |
| **Subtitle**   | 500 (medium) | `text-base font-medium` | Sub-headings, emphasized labels                |
| **Body**       | 400 (normal) | `text-sm`               | Chat messages, descriptions, form labels       |
| **Body Small** | 400 (normal) | `text-xs`               | Helper text, timestamps, secondary info        |
| **Caption**    | 600 (semi)   | `text-xs font-semibold` | Badge labels, metadata, tool status indicators |
| **Cost/Price** | 600 (semi)   | `text-lg font-semibold` | Per-person costs, nightly rates, total prices  |
| **Button**     | 500 (medium) | `text-sm font-medium`   | All button labels                              |

**Rules**:

- Single font stack — no mixing heading vs body fonts.
- Cost figures are the most prominent text in listing cards — use `font-semibold` at `text-lg`.
- Chat messages use `text-sm` for density — the chat is the primary interface.
- Use `text-foreground` for primary text, `text-muted-foreground` for secondary text.

---

## Component Library

All components live in `app/components/ui/` and are auto-imported by Nuxt via `shadcn-nuxt` module.

### Available Components

| Component  | Import Path                  | Sub-components                                                        |
| ---------- | ---------------------------- | --------------------------------------------------------------------- |
| **Badge**  | `~/app/components/ui/badge`  | Badge                                                                 |
| **Button** | `~/app/components/ui/button` | Button                                                                |
| **Card**   | `~/app/components/ui/card`   | Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter |
| **Input**  | `~/app/components/ui/input`  | Input                                                                 |
| **Sonner** | `~/app/components/ui/sonner` | Toaster (Sonner)                                                      |

Additional shadcn-vue components should be added via `npx shadcn-vue@latest add <component>` as needed.

### Button Variants

```ts
variants: {
  variant: ['default', 'destructive', 'outline', 'secondary', 'ghost', 'link'],
  size: ['default', 'xs', 'sm', 'lg', 'icon', 'icon-sm', 'icon-lg']
}
```

| Variant       | Background    | Text                   | Usage                                         |
| ------------- | ------------- | ---------------------- | --------------------------------------------- |
| `default`     | `primary`     | `primary-foreground`   | Primary CTAs (Send message, Start search)     |
| `secondary`   | `secondary`   | `secondary-foreground` | Secondary actions (View listing, Copy link)   |
| `outline`     | `background`  | text with border       | Tertiary actions, filter toggles              |
| `ghost`       | transparent   | `accent-foreground`    | Subtle actions (Close, Dismiss, icon buttons) |
| `destructive` | `destructive` | `destructive-fg`       | Dangerous actions (Clear chat, Cancel search) |
| `link`        | transparent   | `primary`              | Inline text links (Airbnb listing URL)        |

### Badge Patterns

Badges are `rounded-md` pills with `text-xs font-semibold px-2.5 py-0.5`.

Four variants via CVA:

- **`default`** — Primary background. Use for ranking badges (Best Price, Best Value).
- **`secondary`** — Subtle background. Use for amenity tags (AC, W/D, Pool).
- **`destructive`** — Red background. Use for error states, anti-bot detected.
- **`outline`** — Bordered, no fill. Use for neutral metadata (bed count, bath count, neighborhood).

---

## Custom Domain Components

Beyond shadcn-vue, TripPlannerAgent defines these domain-specific components (to be built):

| Component         | Location               | Purpose                                                                        |
| ----------------- | ---------------------- | ------------------------------------------------------------------------------ |
| **ChatMessage**   | `app/components/chat/` | Renders user or agent message bubble with markdown support                     |
| **ChatInput**     | `app/components/chat/` | Text input + send button, fixed to bottom of chat area                         |
| **ListingCard**   | `app/components/chat/` | Airbnb listing card: title, neighborhood, beds/baths, price, rating, amenities |
| **CostTable**     | `app/components/chat/` | Tabular cost breakdown: total, per-person, per-night, fees                     |
| **WeekSummary**   | `app/components/chat/` | Week header with date range, participant count, best picks                     |
| **ToolBadge**     | `app/components/chat/` | Inline status badge showing current agent tool (Searching, Parsing, etc.)      |
| **StreamingDots** | `app/components/chat/` | Animated typing/thinking indicator for agent responses                         |
| **ErrorCard**     | `app/components/chat/` | Error display with message, suggestions, and retry button                      |

---

## Icon System

- **Library**: Lucide icons via `lucide-vue-next`
- **Style**: Outline only — consistent stroke width, clean geometry
- **Usage**: `<Home :size="20" />` (direct component import from `lucide-vue-next`)
- **Sizing**: `size={16}` (inline), `size={20}` (buttons), `size={24}` (standalone/headings)
- **Color**: Inherits parent text color. Use `text-primary` for brand-emphasized icons, `text-muted-foreground` for subtle icons.
- **Icon-only buttons**: Must be at least 44×44px total (padding included) for touch accessibility

### Common Icons

| Context        | Icon           | Usage                               |
| -------------- | -------------- | ----------------------------------- |
| Send message   | `Send`         | Chat input send button              |
| Agent thinking | `Loader2`      | Animated spinner during streaming   |
| Airbnb link    | `ExternalLink` | Open listing in new tab             |
| Rating         | `Star`         | Listing rating display              |
| Beds           | `Bed`          | Bed count badge                     |
| Location       | `MapPin`       | Neighborhood label                  |
| Price          | `DollarSign`   | Cost breakdown header               |
| Error          | `AlertCircle`  | Error state indicator               |
| Success        | `CheckCircle`  | Completed search, confirmed results |
| Search         | `Search`       | Searching Airbnb tool badge         |
| Calendar       | `Calendar`     | Check-in / check-out dates          |
| Users          | `Users`        | Participant count                   |

---

## Animations & Loading

### Motion Conventions

| Animation Type     | Duration | Easing      | Implementation                   |
| ------------------ | -------- | ----------- | -------------------------------- |
| Page transition    | 200ms    | ease-out    | `<Transition>` on NuxtPage       |
| Chat message enter | 300ms    | ease-out    | CSS `@keyframes` fade + slide-up |
| Streaming dots     | looped   | ease-in-out | CSS `@keyframes` pulse           |
| Hover effect       | 150ms    | ease-in-out | Tailwind `transition-colors`     |
| Card shadow hover  | 200ms    | ease-in-out | `transition-shadow`              |
| Button press       | instant  | —           | `active:scale-[0.98]`            |
| Toast enter        | 300ms    | ease-out    | Sonner built-in                  |

**Maximum animation duration**: 400ms. Nothing should feel sluggish.

### Loading States

- **Agent streaming**: Animated `StreamingDots` component in agent message bubble, plus `ToolBadge` showing current operation
- **Data fetching**: shadcn-vue Skeleton components matching the layout being loaded
- **Button submitting**: Replace button text with `Loader2` spinner icon; keep button width stable
- **Never show a blank white screen** — always show either a loader or skeleton
- Respect `prefers-reduced-motion` — use instant transitions, disable pulsing animations

---

## Styling Approach

- **Methodology**: Tailwind CSS v4 utility-first with OKLCH CSS custom properties for design tokens
- **Token definitions**: `app/assets/css/main.css` (light in `:root`, dark in `.dark`)
- **Component variants**: CVA (class-variance-authority) within shadcn-vue components
- **Conditional classes**: `cn()` utility from `app/lib/utils.ts` (`clsx` + `tailwind-merge`)
- **Responsive**: Mobile-first — base styles target mobile, enhance with `sm:`, `md:`, `lg:` prefixes
- **Dark mode**: Full support via `@custom-variant dark (&:is(.dark *))` in `main.css`
- **No inline styles**: All styling through Tailwind utilities or CSS variables
- **No custom CSS files** beyond token definitions — no `.scss`, no CSS modules

### Visual Style Summary

| Property          | Value                                                  | Tailwind                                               |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------ |
| **Border radius** | `--radius: 0.625rem` (10px base), computed sm/md/lg/xl | `rounded-sm`, `rounded-md`, `rounded-lg`, `rounded-xl` |
| **Shadows**       | Subtle, standard Tailwind shadows                      | `shadow` on cards, `shadow-sm` on inputs               |
| **Borders**       | OKLCH slate border token                               | `border border-border`                                 |
| **Focus rings**   | Primary cyan ring                                      | `ring-1 ring-ring`                                     |
| **Spacing base**  | 4px increments                                         | Tailwind spacing scale                                 |
| **Max content**   | Chat-focused — full height, constrained width          | `max-w-3xl mx-auto` for chat area                      |

---

## Project Structure

```
frontend/
├── app/
│   ├── app.vue                      # Root — NuxtLayout + NuxtPage
│   ├── assets/
│   │   └── css/main.css             # OKLCH token definitions (light + dark)
│   ├── components/
│   │   ├── ui/                      # shadcn-vue primitives (Badge, Button, Card, Input, Sonner)
│   │   └── chat/                    # ChatMessage, ChatInput, ListingCard, CostTable, WeekSummary (to build)
│   ├── composables/                 # TanStack Query wrappers (useChat, etc.)
│   ├── layouts/
│   │   └── default.vue              # Main layout shell (full-height flex column)
│   ├── lib/
│   │   └── utils.ts                 # cn() — clsx + tailwind-merge
│   ├── pages/
│   │   └── index.vue                # Main chat interface
│   ├── plugins/
│   │   └── vue-query.ts             # TanStack Vue Query plugin with defaults
│   └── stores/
│       ├── chat.ts                  # Streaming state (Pinia — UI-only)
│       └── ui.ts                    # Sidebar, modals (Pinia — UI-only)
├── server/
│   └── api/agent/[...path].ts       # Nitro proxy — injects X-API-Key server-side
├── nuxt.config.ts                   # Modules, runtimeConfig, Tailwind v4, Pinia, shadcn
├── tailwind.config.ts               # Token mapping from CSS vars
├── openapi-ts.config.ts             # @hey-api codegen config
├── components.json                  # shadcn-vue config
├── eslint.config.mjs
└── package.json                     # pnpm managed
```

---

## Layout Shell

`layouts/default.vue` — The only layout. TripPlannerAgent is a single-page chat application.

```
┌──────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────┐│
│  │  🏠 TripPlannerAgent      [status indicator] ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │                                              ││
│  │            Chat Message Area                 ││
│  │       (scrollable, auto-scroll down)         ││
│  │       max-w-3xl mx-auto                      ││
│  │                                              ││
│  │  ┌─────────────────────────────────────────┐ ││
│  │  │ 👤 You:                                 │ ││
│  │  │ Find me 3BR listings in Roma Norte,     │ ││
│  │  │ CDMX for May 2-9 for 4 adults          │ ││
│  │  └─────────────────────────────────────────┘ ││
│  │                                              ││
│  │  ┌─────────────────────────────────────────┐ ││
│  │  │ 🤖 Agent:                               │ ││
│  │  │ [ToolBadge: 🔍 Searching Airbnb...]     │ ││
│  │  │                                          │ ││
│  │  │ I found 3 listings:                      │ ││
│  │  │ ┌───────────────────────────────────┐   │ ││
│  │  │ │ [ListingCard]                     │   │ ││
│  │  │ │ Steps from Reforma · 3BR/3BA      │   │ ││
│  │  │ │ ⭐ 4.91 · $220/night · AC, W/D    │   │ ││
│  │  │ └───────────────────────────────────┘   │ ││
│  │  │ ┌───────────────────────────────────┐   │ ││
│  │  │ │ [CostTable]                       │   │ ││
│  │  │ │ Total: $1,542 · Per person: $386  │   │ ││
│  │  │ └───────────────────────────────────┘   │ ││
│  │  └─────────────────────────────────────────┘ ││
│  │                                              ││
│  └──────────────────────────────────────────────┘│
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │ [💬 Type your trip planning request...]  [➤] ││
│  └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

- **Header**: Minimal — app branding + agent connection status. Sticky top.
- **Chat area**: `flex-1 overflow-y-auto` — scrollable, auto-scrolls to newest message. Content centered via `max-w-3xl`.
- **Input area**: Fixed to bottom — text input + send button. Disabled during streaming.
- **No sidebar** in initial phases (possible future addition for trip history).
- **No footer** — the input area IS the bottom of the page.

---

## Design-to-Code Translation Rules

When translating Figma designs into TripPlannerAgent code, follow these rules:

1. **Vue 3 syntax** — Always `<template>` + `<script setup lang="ts">`. Never Options API.
2. **shadcn-vue imports** — Import from `~/app/components/ui/`, not from `node_modules`. Components are auto-imported by Nuxt.
3. **Data fetching** — Use TanStack Query (`useQuery`, `useMutation`) in composables for all server state. Auto-generated API client functions from `~/api/` as `queryFn`. Never hand-write `$fetch` calls for backend endpoints.
4. **State** — Pinia stores for **UI-only state** (streaming flag, sidebar state). Server data is owned by TanStack Query — never duplicate into Pinia.
5. **Class merging** — Use `cn()` from `app/lib/utils.ts` for conditional Tailwind class merging.
6. **Props/Emits** — `defineProps<T>()` and `defineEmits<T>()` — always typed, never runtime-only.
7. **Notifications** — In-app: vue-sonner toasts via the Sonner component.
8. **Streaming** — Agent responses stream via newline-delimited JSON. Client uses `ReadableStream` to parse and render incrementally.
9. **Colors** — Only use CSS variable tokens from `main.css`. Never hardcode hex values. Reference via Tailwind classes: `bg-primary`, `text-muted-foreground`, `border-border`, etc.
10. **Dark mode** — All designs must work in both light and dark mode. Use semantic token classes (e.g., `bg-card`, `text-foreground`) — never raw color values.

---

## Key Design Conventions

### General Rules

- **Chat-first** — The entire UI is a chat interface. All design decisions serve the conversational flow.
- **Desktop-first, responsive down** — Primary use is desktop (1440px), but must work on tablet (768px) and mobile (375px).
- **Data-dense but scannable** — Listing cards pack key info (title, price, beds, rating, amenities) without feeling cluttered. Visual hierarchy is critical.
- **Cost-focused** — Per-person cost is the primary metric. Total cost is secondary. Nightly rate is context. Design the visual hierarchy accordingly.
- **Streaming-native** — Design for incremental disclosure. Results appear as the agent discovers them, not all at once.
- **Dark mode supported** — Full light/dark mode via OKLCH tokens. Both modes must meet contrast requirements.

### Interactive Elements

- All interactive elements must have visible hover, focus, active, and disabled states.
- Focus ring: `ring-1 ring-ring` — always visible for keyboard navigation.
- Touch targets: minimum 44×44px on mobile.
- Disabled state: `opacity-50 pointer-events-none`.

### Content Principles

- **Listing titles** — Never truncated, always fully visible in the card.
- **Costs** in `font-semibold` — functional data labels, prominently sized.
- **Ranking badges** (Best Price, Best Value, etc.) use primary-colored Badge with clear text label.
- **Amenity badges** use secondary Badge variant — compact, scannable list.
- **Status badges** always show both color AND text label — never color alone.
- **Empty states** are encouraging — include a welcome message and example prompts.
- **Error states** are helpful — include what went wrong, what to try, and a retry button.

### Accessibility Minimums

- WCAG 2.1 AA contrast ratios (4.5:1 body text, 3:1 large text) in both light and dark modes
- Keyboard navigation for all interactive elements (Reka UI provides this via shadcn-vue)
- `aria-label` on all icon-only buttons
- `prefers-reduced-motion` respected — disable pulsing animations, use instant transitions
- Screen reader support for streaming status changes (`aria-live` regions)
