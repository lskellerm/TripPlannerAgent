<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Loader2, MapPin, Search, Send } from 'lucide-vue-next'

const toc = [
  { id: 'design-philosophy', label: 'Design Philosophy' },
  { id: 'color-system', label: 'Color System' },
  { id: 'typography', label: 'Typography' },
  { id: 'spacing-layout', label: 'Spacing & Layout' },
  { id: 'borders-corners', label: 'Borders & Corners' },
  { id: 'shadows-elevation', label: 'Shadows & Elevation' },
  { id: 'iconography', label: 'Iconography' },
  { id: 'animations-motion', label: 'Animations & Motion' },
  { id: 'component-conventions', label: 'Component Conventions' },
  { id: 'interaction-states', label: 'Interaction States' },
  { id: 'empty-loading', label: 'Empty & Loading States' },
  { id: 'accessibility', label: 'Accessibility' },
  { id: 'anti-patterns', label: 'Anti-Patterns' },
]

const principles = [
  'Clarity over decoration',
  'Data-dense but approachable',
  'Conversational flow for planning',
  'Per-person cost hierarchy first',
  'Streaming-first result presentation',
]

const corePaletteLight = [
  {
    name: 'Background',
    token: '--background',
    value: 'oklch(1 0 0)',
    usage: 'Main page surface',
  },
  {
    name: 'Foreground',
    token: '--foreground',
    value: 'oklch(0.129 0.042 264.695)',
    usage: 'Primary text',
  },
  {
    name: 'Card',
    token: '--card',
    value: 'oklch(1 0 0)',
    usage: 'Card surfaces',
  },
  {
    name: 'Primary',
    token: '--primary',
    value: 'oklch(0.609 0.126 221.723)',
    usage: 'CTAs and active emphasis',
  },
  {
    name: 'Secondary',
    token: '--secondary',
    value: 'oklch(0.968 0.007 247.896)',
    usage: 'Subtle backgrounds',
  },
  {
    name: 'Muted Foreground',
    token: '--muted-foreground',
    value: 'oklch(0.554 0.046 257.417)',
    usage: 'Secondary labels and metadata',
  },
  {
    name: 'Border',
    token: '--border',
    value: 'oklch(0.929 0.013 255.508)',
    usage: 'Dividers and outlines',
  },
  {
    name: 'Ring',
    token: '--ring',
    value: 'oklch(0.609 0.126 221.723)',
    usage: 'Keyboard focus ring',
  },
]

const corePaletteDark = [
  {
    name: 'Background',
    token: '--background',
    value: 'oklch(0.129 0.042 264.695)',
    usage: 'Dark mode canvas',
  },
  {
    name: 'Foreground',
    token: '--foreground',
    value: 'oklch(0.984 0.003 247.858)',
    usage: 'Primary text in dark mode',
  },
  {
    name: 'Card',
    token: '--card',
    value: 'oklch(0.208 0.042 265.755)',
    usage: 'Elevated surfaces',
  },
  {
    name: 'Primary',
    token: '--primary',
    value: 'oklch(0.715 0.143 215.221)',
    usage: 'Readable cyan accent',
  },
  {
    name: 'Secondary',
    token: '--secondary',
    value: 'oklch(0.279 0.041 260.031)',
    usage: 'Muted dark surface',
  },
  {
    name: 'Muted Foreground',
    token: '--muted-foreground',
    value: 'oklch(0.704 0.04 256.788)',
    usage: 'Support text in dark mode',
  },
  {
    name: 'Border',
    token: '--border',
    value: 'oklch(1 0 0 / 10%)',
    usage: 'Low-contrast dark borders',
  },
  {
    name: 'Ring',
    token: '--ring',
    value: 'oklch(0.609 0.126 221.723)',
    usage: 'Focus indication',
  },
]

const semanticColors = [
  {
    name: 'Destructive',
    token: '--destructive',
    light: 'oklch(0.577 0.245 27.325)',
    dark: 'oklch(0.704 0.191 22.216)',
    usage: 'Errors and destructive actions',
  },
  {
    name: 'Success',
    token: '--success',
    light: 'oklch(0.596 0.145 163.225)',
    dark: 'oklch(0.765 0.177 163.223)',
    usage: 'Completed states',
  },
  {
    name: 'Warning',
    token: '--warning',
    light: 'oklch(0.769 0.188 70.08)',
    dark: 'oklch(0.828 0.189 84.429)',
    usage: 'Rate-limit and caution states',
  },
  {
    name: 'Info',
    token: '--info',
    light: 'oklch(0.685 0.169 237.323)',
    dark: 'oklch(0.746 0.16 232.661)',
    usage: 'Tool progress and status',
  },
]

const agentStatusTokens = [
  {
    status: 'searching',
    token: 'info',
    sample: 'Searching listings',
    badgeClass: 'border-transparent bg-info text-info-foreground',
  },
  {
    status: 'parsing',
    token: 'info',
    sample: 'Parsing listing fields',
    badgeClass: 'border-transparent bg-info text-info-foreground',
  },
  {
    status: 'calculating',
    token: 'primary',
    sample: 'Calculating per-person cost',
    badgeClass: 'border-transparent bg-primary text-primary-foreground',
  },
  {
    status: 'ranking',
    token: 'primary',
    sample: 'Ranking recommendations',
    badgeClass: 'border-transparent bg-primary text-primary-foreground',
  },
  {
    status: 'complete',
    token: 'success',
    sample: 'Result ready',
    badgeClass: 'border-transparent bg-success text-success-foreground',
  },
  {
    status: 'error',
    token: 'destructive',
    sample: 'Tool request failed',
    badgeClass: 'border-transparent bg-destructive text-destructive-foreground',
  },
  {
    status: 'rate-limited',
    token: 'warning',
    sample: 'Switching to cached response',
    badgeClass: 'border-transparent bg-warning text-warning-foreground',
  },
]

const typeScale = [
  {
    role: 'Page Title',
    token: 'text-2xl',
    size: '24px',
    weight: '700',
    usage: 'Top-level headings',
  },
  {
    role: 'Section Title',
    token: 'text-xl',
    size: '20px',
    weight: '600',
    usage: 'Section headers',
  },
  {
    role: 'Card Title',
    token: 'text-lg',
    size: '18px',
    weight: '600',
    usage: 'Listing/cost card titles',
  },
  {
    role: 'Subtitle',
    token: 'text-base',
    size: '16px',
    weight: '500',
    usage: 'Emphasized labels',
  },
  {
    role: 'Body',
    token: 'text-sm',
    size: '14px',
    weight: '400',
    usage: 'Message and support copy',
  },
  {
    role: 'Body Small',
    token: 'text-xs',
    size: '12px',
    weight: '400',
    usage: 'Metadata and helper text',
  },
  {
    role: 'Caption',
    token: 'text-xs',
    size: '12px',
    weight: '600',
    usage: 'Badge labels and status chips',
  },
  {
    role: 'Cost/Price',
    token: 'text-lg',
    size: '18px',
    weight: '600',
    usage: 'Per-person and total costs',
  },
  {
    role: 'Button Label',
    token: 'text-sm',
    size: '14px',
    weight: '500',
    usage: 'All button text',
  },
]

const spacingScale = [
  { token: '1', px: '4px', usage: 'Tight icon-text spacing' },
  { token: '2', px: '8px', usage: 'Compact chips and badges' },
  { token: '3', px: '12px', usage: 'Input and small card padding' },
  { token: '4', px: '16px', usage: 'Base section and card spacing' },
  { token: '5', px: '20px', usage: 'Grid gaps and medium separation' },
  { token: '6', px: '24px', usage: 'Card interior spacing' },
  { token: '8', px: '32px', usage: 'Section rhythm' },
  { token: '10', px: '40px', usage: 'Large section separation' },
  { token: '12', px: '48px', usage: 'Page top/bottom spacing' },
]

const breakpoints = [
  { label: 'Default', width: '< 640px', behavior: 'Single-column, full-width controls' },
  { label: 'sm', width: '>= 640px', behavior: 'Wider messages and horizontal chip rows' },
  { label: 'md', width: '>= 768px', behavior: 'Two-column listing/card patterns' },
  { label: 'lg', width: '>= 1024px', behavior: 'max-w-3xl chat content width' },
  { label: 'xl', width: '>= 1280px', behavior: 'Generous side margins for readability' },
]

const radiusRules = [
  { item: 'Buttons', token: 'rounded-md', value: 'calc(--radius - 2px)' },
  { item: 'Inputs', token: 'rounded-md', value: 'calc(--radius - 2px)' },
  { item: 'Cards', token: 'rounded-xl', value: 'calc(--radius + 4px)' },
  { item: 'Chat Bubbles', token: 'rounded-lg', value: 'var(--radius)' },
  { item: 'Badges', token: 'rounded-md', value: 'calc(--radius - 2px)' },
]

const elevationRules = [
  { level: 'None', token: 'shadow-none', usage: 'Flat inline content' },
  { level: 'Small', token: 'shadow-sm', usage: 'Inputs and lightweight controls' },
  { level: 'Default', token: 'shadow', usage: 'Cards at rest (default pattern)' },
  { level: 'Medium', token: 'shadow-md', usage: 'Interactive hover state' },
  { level: 'Large', token: 'shadow-lg', usage: 'Dialogs and overlays' },
]

const componentRules = [
  {
    name: 'Buttons',
    detail: 'Use default, secondary, outline, ghost, and destructive variants from ui/button.',
  },
  {
    name: 'Cards',
    detail: 'Card surfaces use border + shadow for elevation, not heavy background contrast.',
  },
  {
    name: 'Badges',
    detail: 'Use variant classes for metadata and status tags; keep text concise.',
  },
  {
    name: 'Inputs',
    detail: 'Focus-visible ring uses --ring token; placeholder text uses muted foreground.',
  },
  {
    name: 'Chat Blocks',
    detail: 'Agent responses can embed listing cards and cost summaries inline.',
  },
]

const motionPatterns = [
  {
    name: 'Streaming Dots',
    detail: 'Use subtle, short-loop typing indicators while the AI response is building.',
  },
  {
    name: 'Progress Badges',
    detail: 'Status badges update from searching -> parsing -> calculating -> complete.',
  },
  {
    name: 'Card Hover',
    detail: 'Use transition-shadow with light translate for discoverability only.',
  },
]

const interactionStates = [
  'Hover: small tonal shift or shadow increase, never drastic color jumps.',
  'Focus: visible ring color from --ring with preserved contrast in both themes.',
  'Disabled: reduced opacity and no pointer affordance, while remaining readable.',
  'Pressed: slightly darker surface or reduced elevation to indicate commitment.',
]

const emptyLoadingRules = [
  'Empty state copy should suggest a clear next prompt or trip-planning action.',
  'Skeleton loading should mirror final card/message anatomy to prevent layout shift.',
  'Streaming responses should progressively reveal content, not replace entire blocks.',
]

const accessibilityRules = [
  'Maintain WCAG 2.1 AA contrast for all text and status indicators.',
  'Keep icon-only actions at 44x44px minimum target size.',
  'Never rely on color alone for state communication.',
  'Preserve predictable focus order and visible focus indicators.',
]

const antiPatterns = [
  'Hardcoded hex/OKLCH values inside component markup.',
  'Overdecorated dashboards that hide key cost and ranking information.',
  'Deeply nested tables when a simpler card + row layout is clearer.',
  'Animations that delay reading or interfere with streamed content.',
]
</script>

<template>
  <main class="guide-shell">
    <div class="guide-canvas" aria-hidden="true"></div>

    <section id="design-philosophy" class="panel hero">
      <p class="eyebrow">TripPlannerAgent Frontend Style Guide</p>
      <h1>Token-Driven UI Language for Conversational Trip Planning</h1>
      <p class="hero-copy">
        Visual board generated from `.figma/style-guide.md` and `.figma/design-system-rules.md`.
        This is the design reference for color, typography, spacing, component behavior, and
        interaction states in `app/pages/ui-styling`.
      </p>
      <div class="chips">
        <article v-for="principle in principles" :key="principle" class="chip">
          {{ principle }}
        </article>
      </div>
    </section>

    <nav class="panel toc" aria-label="Style guide sections">
      <a v-for="section in toc" :key="section.id" :href="`#${section.id}`" class="toc-link">
        {{ section.label }}
      </a>
    </nav>

    <section id="color-system" class="panel">
      <header class="panel-header">
        <h2>Color System</h2>
        <p>Core token palettes for light/dark themes and semantic status mappings.</p>
      </header>

      <h3>Core Palette - Light Mode</h3>
      <div class="swatch-grid">
        <article
          v-for="token in corePaletteLight"
          :key="`light-${token.token}`"
          class="swatch-card"
        >
          <div class="swatch" :style="{ backgroundColor: token.value }"></div>
          <div class="swatch-meta">
            <h4>{{ token.name }}</h4>
            <p>{{ token.token }}</p>
            <p>{{ token.value }}</p>
            <p>{{ token.usage }}</p>
          </div>
        </article>
      </div>

      <h3>Core Palette - Dark Mode</h3>
      <div class="swatch-grid">
        <article v-for="token in corePaletteDark" :key="`dark-${token.token}`" class="swatch-card">
          <div class="swatch" :style="{ backgroundColor: token.value }"></div>
          <div class="swatch-meta">
            <h4>{{ token.name }}</h4>
            <p>{{ token.token }}</p>
            <p>{{ token.value }}</p>
            <p>{{ token.usage }}</p>
          </div>
        </article>
      </div>

      <h3>Semantic Colors</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Token</th>
              <th>Light</th>
              <th>Dark</th>
              <th>Usage</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="token in semanticColors" :key="token.token">
              <td>{{ token.name }}</td>
              <td>{{ token.token }}</td>
              <td>{{ token.light }}</td>
              <td>{{ token.dark }}</td>
              <td>{{ token.usage }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3>Agent Status Tokens</h3>
      <div class="status-grid">
        <article v-for="status in agentStatusTokens" :key="status.status" class="status-card">
          <UiBadge :class="status.badgeClass">
            {{ status.status }}
          </UiBadge>
          <p class="status-token">token: {{ status.token }}</p>
          <p class="status-copy">{{ status.sample }}</p>
        </article>
      </div>
    </section>

    <section id="typography" class="panel">
      <header class="panel-header">
        <h2>Typography</h2>
        <p>Single system stack with hierarchy created by size and weight, not font switching.</p>
      </header>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Role</th>
              <th>Token</th>
              <th>Size</th>
              <th>Weight</th>
              <th>Usage</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in typeScale" :key="row.role">
              <td>{{ row.role }}</td>
              <td>{{ row.token }}</td>
              <td>{{ row.size }}</td>
              <td>{{ row.weight }}</td>
              <td>{{ row.usage }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="type-sample">
        <p class="sample-eyebrow">Conversation Excerpt</p>
        <p class="sample-heading">3 best-rated Roma Norte listings for 4 adults</p>
        <p class="sample-body">
          Found 5 matches. Cheapest option is $386 per person total. Best-rated option is 4.93 with
          rooftop access and dedicated workspace.
        </p>
        <p class="sample-price">$55.09 per person / night</p>
      </div>
    </section>

    <section id="spacing-layout" class="panel">
      <header class="panel-header">
        <h2>Spacing & Layout</h2>
        <p>4px spacing rhythm and responsive constraints tuned for chat-driven data exploration.</p>
      </header>

      <h3>Spacing Scale</h3>
      <div class="spacing-grid">
        <article v-for="space in spacingScale" :key="space.token" class="spacing-card">
          <div class="bar" :style="{ width: space.px }"></div>
          <h4>Token {{ space.token }} - {{ space.px }}</h4>
          <p>{{ space.usage }}</p>
        </article>
      </div>

      <h3>Responsive Breakpoints</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Breakpoint</th>
              <th>Width</th>
              <th>Layout Shift</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bp in breakpoints" :key="bp.label">
              <td>{{ bp.label }}</td>
              <td>{{ bp.width }}</td>
              <td>{{ bp.behavior }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel two-col">
      <div id="borders-corners">
        <header class="panel-header">
          <h2>Borders & Corners</h2>
          <p>Corner radii derive from `--radius` and map directly to Tailwind utilities.</p>
        </header>
        <div class="stack">
          <article v-for="rule in radiusRules" :key="rule.item" class="mini-card">
            <h4>{{ rule.item }}</h4>
            <p>{{ rule.token }} - {{ rule.value }}</p>
          </article>
        </div>
      </div>

      <div id="shadows-elevation">
        <header class="panel-header">
          <h2>Shadows & Elevation</h2>
          <p>Use subtle, consistent elevation levels across cards, controls, and overlays.</p>
        </header>
        <div class="stack">
          <article v-for="rule in elevationRules" :key="rule.level" class="mini-card">
            <h4>{{ rule.level }} - {{ rule.token }}</h4>
            <p>{{ rule.usage }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="iconography" class="panel two-col">
      <div>
        <header class="panel-header">
          <h2>Iconography</h2>
          <p>Lucide outline icons with semantic color and clear touch-target sizing.</p>
        </header>
        <div class="icon-grid">
          <article class="icon-card">
            <Send :size="20" />
            <p>Send</p>
          </article>
          <article class="icon-card">
            <Search :size="20" />
            <p>Search</p>
          </article>
          <article class="icon-card">
            <Loader2 :size="20" class="animate-spin" />
            <p>Loading</p>
          </article>
          <article class="icon-card">
            <CheckCircle2 :size="20" />
            <p>Success</p>
          </article>
          <article class="icon-card">
            <AlertTriangle :size="20" />
            <p>Warning</p>
          </article>
          <article class="icon-card">
            <MapPin :size="20" />
            <p>Location</p>
          </article>
        </div>
      </div>

      <div id="animations-motion">
        <header class="panel-header">
          <h2>Animations & Motion</h2>
          <p>Feedback motion should support understanding, never compete with content.</p>
        </header>
        <div class="stack">
          <article v-for="motion in motionPatterns" :key="motion.name" class="mini-card">
            <h4>{{ motion.name }}</h4>
            <p>{{ motion.detail }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="component-conventions" class="panel">
      <header class="panel-header">
        <h2>Component Styling Conventions</h2>
        <p>Reference usage of shadcn-vue primitives and TripPlanner-specific chat patterns.</p>
      </header>

      <div class="component-demo-grid">
        <UiCard class="demo-card">
          <UiCardHeader>
            <UiCardTitle>Button Variants</UiCardTitle>
            <UiCardDescription
              >Use semantic variants from `app/components/ui/button`.</UiCardDescription
            >
          </UiCardHeader>
          <UiCardContent class="demo-row">
            <UiButton>Default</UiButton>
            <UiButton variant="secondary">Secondary</UiButton>
            <UiButton variant="outline">Outline</UiButton>
            <UiButton variant="ghost">Ghost</UiButton>
            <UiButton variant="destructive">Destructive</UiButton>
          </UiCardContent>
        </UiCard>

        <UiCard class="demo-card">
          <UiCardHeader>
            <UiCardTitle>Badges and Status</UiCardTitle>
            <UiCardDescription
              >Metadata badges and state chips use consistent token classes.</UiCardDescription
            >
          </UiCardHeader>
          <UiCardContent class="demo-row">
            <UiBadge>Recommended</UiBadge>
            <UiBadge variant="secondary">3 BR</UiBadge>
            <UiBadge variant="outline">Roma Norte</UiBadge>
            <UiBadge variant="destructive">Error</UiBadge>
          </UiCardContent>
        </UiCard>
      </div>

      <div class="rule-grid">
        <article v-for="rule in componentRules" :key="rule.name" class="mini-card">
          <h4>{{ rule.name }}</h4>
          <p>{{ rule.detail }}</p>
        </article>
      </div>
    </section>

    <section id="interaction-states" class="panel">
      <header class="panel-header">
        <h2>Interaction States</h2>
        <p>State behavior must remain consistent in both light and dark themes.</p>
      </header>
      <ul class="bullet-list">
        <li v-for="state in interactionStates" :key="state">{{ state }}</li>
      </ul>
    </section>

    <section id="empty-loading" class="panel two-col">
      <div>
        <header class="panel-header">
          <h2>Empty & Loading States</h2>
          <p>Guide users forward with clear, actionable copy and stable placeholder layout.</p>
        </header>

        <UiCard class="empty-card">
          <UiCardHeader>
            <UiCardTitle class="text-base">No conversation yet</UiCardTitle>
            <UiCardDescription>
              Start with destination, dates, guest count, and budget to begin ranking listings.
            </UiCardDescription>
          </UiCardHeader>
          <UiCardFooter>
            <UiButton size="sm">Try Sample Prompt</UiButton>
          </UiCardFooter>
        </UiCard>

        <ul class="bullet-list compact">
          <li v-for="rule in emptyLoadingRules" :key="rule">{{ rule }}</li>
        </ul>
      </div>

      <div id="accessibility">
        <header class="panel-header">
          <h2>Accessibility</h2>
          <p>Contrast, keyboard flow, and semantics are design requirements, not post-fix tasks.</p>
        </header>
        <ul class="bullet-list compact">
          <li v-for="rule in accessibilityRules" :key="rule">{{ rule }}</li>
        </ul>
      </div>
    </section>

    <section id="anti-patterns" class="panel">
      <header class="panel-header">
        <h2>Anti-Patterns</h2>
        <p>Patterns that conflict with a clear and trustworthy planning experience.</p>
      </header>
      <div class="rule-grid">
        <article v-for="item in antiPatterns" :key="item" class="mini-card warning">
          <p>{{ item }}</p>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(body) {
  margin: 0;
  min-height: 100vh;
}

* {
  box-sizing: border-box;
}

.guide-shell {
  position: relative;
  max-width: 1240px;
  margin: 0 auto;
  padding: 40px 16px 72px;
  display: grid;
  gap: 16px;
}

.guide-canvas {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(circle at 8% 4%, oklch(0.746 0.16 232.661 / 0.2), transparent 36%),
    radial-gradient(circle at 92% 8%, oklch(0.769 0.188 70.08 / 0.12), transparent 32%),
    linear-gradient(180deg, oklch(1 0 0), oklch(0.99 0.002 247));
}

.dark .guide-canvas {
  background:
    radial-gradient(circle at 10% 0%, oklch(0.715 0.143 215.221 / 0.26), transparent 34%),
    radial-gradient(circle at 88% 10%, oklch(0.765 0.177 163.223 / 0.18), transparent 30%),
    linear-gradient(180deg, oklch(0.129 0.042 264.695), oklch(0.155 0.04 264.6));
}

.panel {
  border: 1px solid color-mix(in oklab, var(--border) 92%, transparent);
  border-radius: 20px;
  background: color-mix(in oklab, var(--card) 90%, transparent);
  backdrop-filter: blur(8px);
  padding: 22px;
  box-shadow: 0 12px 30px rgb(18 35 54 / 8%);
}

.hero {
  border-radius: 24px;
  background: linear-gradient(
    132deg,
    color-mix(in oklab, var(--primary) 20%, var(--card)) 0%,
    color-mix(in oklab, var(--info) 18%, var(--card)) 56%,
    color-mix(in oklab, var(--success) 16%, var(--card)) 100%
  );
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
  color: color-mix(in oklab, var(--foreground) 84%, var(--primary) 16%);
}

h1,
h2,
h3,
h4,
p {
  margin: 0;
}

h1 {
  margin-top: 8px;
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.05;
  font-weight: 700;
  color: var(--foreground);
}

h2 {
  font-size: clamp(24px, 2.6vw, 34px);
  line-height: 1.1;
  color: var(--foreground);
}

h3 {
  margin-top: 20px;
  margin-bottom: 12px;
  font-size: 20px;
  line-height: 1.2;
  color: var(--foreground);
}

h4 {
  font-size: 15px;
  line-height: 1.2;
  color: var(--foreground);
}

.hero-copy {
  margin-top: 12px;
  max-width: 820px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--muted-foreground);
}

.chips {
  margin-top: 18px;
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.chip {
  border-radius: 999px;
  border: 1px solid color-mix(in oklab, var(--border) 85%, var(--primary) 15%);
  background: color-mix(in oklab, var(--card) 72%, var(--primary) 28%);
  color: var(--foreground);
  padding: 10px 14px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
}

.toc {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.toc-link {
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--foreground);
  text-decoration: none;
  font-size: 12px;
  font-weight: 600;
  padding: 8px 12px;
  line-height: 1;
}

.toc-link:hover {
  background: color-mix(in oklab, var(--card) 74%, var(--primary) 26%);
}

.panel-header {
  display: grid;
  gap: 6px;
}

.panel-header p {
  color: var(--muted-foreground);
  font-size: 14px;
  line-height: 1.55;
}

.swatch-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.swatch-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  background: var(--card);
}

.swatch {
  min-height: 84px;
  border-bottom: 1px solid var(--border);
}

.swatch-meta {
  padding: 12px;
  display: grid;
  gap: 4px;
}

.swatch-meta p {
  font-size: 12px;
  color: var(--muted-foreground);
  line-height: 1.4;
}

.table-wrap {
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  background: var(--card);
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  text-align: left;
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  color: var(--foreground);
}

th {
  background: color-mix(in oklab, var(--card) 84%, var(--secondary) 16%);
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

tr:last-child td {
  border-bottom: none;
}

.status-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}

.status-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  padding: 12px;
  display: grid;
  gap: 8px;
}

.status-token {
  font-size: 12px;
  color: var(--foreground);
  opacity: 0.9;
}

.status-copy {
  font-size: 12px;
  color: var(--muted-foreground);
}

.type-sample {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: linear-gradient(
    140deg,
    color-mix(in oklab, var(--card) 88%, var(--primary) 12%),
    color-mix(in oklab, var(--card) 86%, var(--secondary) 14%)
  );
  padding: 16px;
}

.sample-eyebrow {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--muted-foreground);
}

.sample-heading {
  margin-top: 6px;
  font-size: clamp(22px, 2.7vw, 30px);
  line-height: 1.15;
  font-weight: 700;
  color: var(--foreground);
}

.sample-body {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--muted-foreground);
}

.sample-price {
  margin-top: 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--foreground);
}

.spacing-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
}

.spacing-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  padding: 12px;
  display: grid;
  gap: 4px;
}

.bar {
  height: 10px;
  min-width: 4px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--primary), var(--info));
}

.spacing-card p {
  font-size: 12px;
  line-height: 1.4;
  color: var(--muted-foreground);
}

.two-col {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stack,
.rule-grid,
.icon-grid,
.component-demo-grid {
  display: grid;
  gap: 10px;
}

.mini-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  padding: 12px;
}

.mini-card p {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--muted-foreground);
}

.icon-grid {
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
}

.icon-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: color-mix(in oklab, var(--card) 88%, var(--secondary) 12%);
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 14px 10px;
  color: var(--foreground);
}

.icon-card p {
  font-size: 11px;
  line-height: 1;
  color: var(--muted-foreground);
}

.component-demo-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.demo-card {
  border-color: color-mix(in oklab, var(--border) 90%, var(--primary) 10%);
}

.demo-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rule-grid {
  margin-top: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.bullet-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

.bullet-list li {
  color: var(--muted-foreground);
  font-size: 14px;
  line-height: 1.5;
}

.bullet-list.compact li {
  font-size: 13px;
}

.empty-card {
  margin-top: 6px;
  border-color: color-mix(in oklab, var(--border) 84%, var(--info) 16%);
  background: color-mix(in oklab, var(--card) 84%, var(--secondary) 16%);
}

.warning {
  border-color: color-mix(in oklab, var(--border) 80%, var(--warning) 20%);
  background: color-mix(in oklab, var(--card) 84%, var(--warning) 16%);
}

@media (max-width: 900px) {
  .two-col {
    grid-template-columns: 1fr;
  }

  .panel {
    padding: 18px;
    border-radius: 18px;
  }

  .guide-shell {
    padding: 28px 14px 56px;
  }
}
</style>
