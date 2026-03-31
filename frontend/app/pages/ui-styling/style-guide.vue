<script setup lang="ts">
import StyleGuideBoard from '~/components/ui-styling/StyleGuideBoard.vue'

useHead({
  title: 'TripPlannerAgent UI Style Guide',
})

if (import.meta.dev) {
  onMounted(() => {
    if (!window.location.hash.includes('figmacapture=')) {
      return
    }

    if (document.querySelector('script[data-figma-capture="true"]')) {
      return
    }

    const captureScript = document.createElement('script')
    captureScript.src = 'https://mcp.figma.com/mcp/html-to-design/capture.js'
    captureScript.async = true
    captureScript.dataset.figmaCapture = 'true'
    document.head.appendChild(captureScript)
  })
}
</script>

<template>
  <StyleGuideBoard />
</template>
