<script lang="ts" setup>
import { Connection } from "@element-plus/icons-vue"

defineOptions({
  name: "ProxyPoolIndex"
})
</script>

<template>
  <div class="app-container">
    <el-card shadow="never">
      <template #header>
        <span class="card-title">代理 IP 池</span>
      </template>
      <el-empty description="代理池管理即将接入：导入/健康检查/轮换策略等">
        <template #image>
          <el-icon :size="56" color="var(--el-text-color-secondary)">
            <Connection />
          </el-icon>
        </template>
      </el-empty>
    </el-card>
  </div>
</template>

<style lang="scss" scoped>
.app-container {
  padding: 16px;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
}
</style>
