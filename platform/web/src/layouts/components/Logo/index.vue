<script lang="ts" setup>
import { useLayoutMode } from "@@/composables/useLayoutMode"

interface Props {
  collapse?: boolean
}

const { collapse = true } = defineProps<Props>()

const { isTop } = useLayoutMode()
</script>

<template>
  <div class="layout-logo-container" :class="{ collapse, 'layout-mode-top': isTop }">
    <router-link to="/crawlee/tasks" class="logo-link">
      <span class="logo-mark" aria-hidden="true">G</span>
      <span v-if="!collapse" class="logo-word">Goose</span>
    </router-link>
  </div>
</template>

<style lang="scss" scoped>
.layout-logo-container {
  position: relative;
  width: 100%;
  height: var(--v3-navigationbar-height);
  line-height: var(--v3-navigationbar-height);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background-color: var(--v3-sidebar-menu-bg-color);
  border-bottom: 1px solid var(--v3-sidebar-border-right);
}

.layout-mode-top {
  height: var(--v3-navigationbar-height);
  line-height: var(--v3-navigationbar-height);
  border-bottom: none;
  background-color: var(--v3-header-bg-color);
}

.logo-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: inherit;
  text-decoration: none;
}

.logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 15px;
  color: #fff;
  background: linear-gradient(135deg, #f59e0b 0%, #eab308 100%);
  flex-shrink: 0;
}

.logo-word {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--v3-sidebar-menu-text-color);
  white-space: nowrap;
}

.collapse {
  .logo-word {
    display: none;
  }
}
</style>
