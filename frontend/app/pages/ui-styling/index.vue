<script setup lang="ts">
useHead({
  title: 'TripPlannerAgent UI Styling Boards',
})
</script>

<template>
  <main class="mx-auto flex min-h-[80vh] w-full max-w-5xl flex-col gap-6 px-4 py-10 sm:px-6">
    <section class="rounded-2xl border border-border bg-card p-6 shadow-sm">
      <p class="text-primary text-xs font-semibold tracking-[0.08em] uppercase">UI Styling</p>
      <h1 class="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Dev Design Boards
      </h1>
      <p class="text-muted-foreground mt-3 max-w-3xl text-sm sm:text-base">
        Internal design-reference pages used for implementation alignment and Figma capture.
      </p>
    </section>

    <section class="grid gap-4 md:grid-cols-2">
      <UiCard class="border-border/80">
        <UiCardHeader>
          <UiCardTitle>TripPlanner Style Guide</UiCardTitle>
          <UiCardDescription>
            Visual translation of `.figma/style-guide.md` and `.figma/design-system-rules.md`.
          </UiCardDescription>
        </UiCardHeader>
        <UiCardFooter>
          <NuxtLink to="/ui-styling/style-guide">
            <UiButton>Open Board</UiButton>
          </NuxtLink>
        </UiCardFooter>
      </UiCard>
    </section>
  </main>
</template>
