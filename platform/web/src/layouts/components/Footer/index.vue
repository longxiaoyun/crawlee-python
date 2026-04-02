<script lang="ts" setup>
const year = new Date().getFullYear()
</script>

<template>
  <footer class="layout-footer">
    © {{ year }} Goose
  </footer>
</template>

<style lang="scss" scoped>
.layout-footer {
  width: 100%;
  min-height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-placeholder);
}
</style>
