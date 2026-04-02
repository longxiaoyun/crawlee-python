<script lang="ts" setup>
import type { EChartsCoreOption } from "echarts/core"
import { BarChart, LineChart } from "echarts/charts"
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent
} from "echarts/components"
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import VChart from "vue-echarts"

const props = withDefaults(
  defineProps<{
    option: EChartsCoreOption
    height?: string
  }>(),
  { height: "220px" }
)

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent
])
</script>

<template>
  <VChart
    class="monitoring-chart"
    :style="{ height: props.height }"
    :option="props.option"
    autoresize
  />
</template>

<style scoped lang="scss">
.monitoring-chart {
  width: 100%;
  min-height: 160px;
}
</style>
