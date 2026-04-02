<script lang="ts" setup>
import type { CrawleeTaskListRow } from "@@/apis/crawlee/type"
import {
  createTaskApi,
  fetchTasksApi
} from "@@/apis/crawlee"
import {
  CircleCheck,
  Filter,
  Lock,
  QuestionFilled,
  Search
} from "@element-plus/icons-vue"
import { useRouter } from "vue-router"

const router = useRouter()

const loading = ref(false)
const tasks = ref<CrawleeTaskListRow[]>([])
const searchQuery = ref("")
const lastRunStatusFilter = ref<string>("all")
const modifiedSortDesc = ref(true)
const pageSize = ref(20)
const page = ref(1)
const goToPageInput = ref("1")
const createDialogVisible = ref(false)
const newActorName = ref("")
const creating = ref(false)

const smartCreateEnabled = import.meta.env.VITE_ENABLE_SMART_TASK_CREATE !== "false"

function goSmartCreate() {
  router.push({ name: "CrawleeSmartCreate" })
}

function fileSafeName(name: string) {
  return name.trim().replace(/[^\w\u4E00-\u9FA5-]+/g, "_").replace(/_+/g, "_") || "task"
}

function actorSlug(row: CrawleeTaskListRow) {
  const slug = fileSafeName(row.name || "actor")
  const short = row.id.replace(/-/g, "").slice(0, 8)
  return `goose/${slug}-${short}`
}

function actorInitials(row: CrawleeTaskListRow) {
  const name = row.name?.trim() ?? "GA"
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0]!.slice(0, 1) + parts[1]!.slice(0, 1)).toUpperCase()
  return name.slice(0, 2).toUpperCase() || "GA"
}

function formatModifiedTs(s: string | null | undefined) {
  if (!s) return "—"
  return s.replace("T", " ").slice(0, 19)
}

function formatLastRunTs(s: string | null | undefined) {
  if (!s) return "—"
  return s.replace("T", " ").slice(0, 19)
}

function formatListRunDuration(sec: number | null | undefined) {
  if (sec == null || !Number.isFinite(sec)) return "—"
  return `${Math.max(0, Math.round(sec))} s`
}

function listRunStatusLabel(status: string | null | undefined) {
  if (!status) return "—"
  const m: Record<string, string> = {
    succeeded: "Succeeded",
    failed: "Failed",
    running: "Running",
    queued: "Queued",
    cancelled: "Cancelled",
    limit_exceeded: "Limit exceeded"
  }
  return m[status] ?? status.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

function listRunStatusKind(status: string | null | undefined): "ok" | "bad" | "run" | "wait" | "neutral" {
  if (status === "succeeded") return "ok"
  if (status === "failed" || status === "limit_exceeded") return "bad"
  if (status === "running") return "run"
  if (status === "queued") return "wait"
  return "neutral"
}

async function load() {
  loading.value = true
  try {
    tasks.value = await fetchTasksApi()
  } finally {
    loading.value = false
  }
}

const tasksFiltered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  let list = [...tasks.value]
  if (q) {
    list = list.filter((row) => {
      const slug = actorSlug(row).toLowerCase()
      return row.name.toLowerCase().includes(q) || slug.includes(q) || row.id.toLowerCase().includes(q)
    })
  }
  const st = lastRunStatusFilter.value
  if (st !== "all") {
    list = list.filter(row => (row.last_run_status ?? "") === st)
  }
  list.sort((a, b) => {
    const ta = Date.parse(a.updated_at || "")
    const tb = Date.parse(b.updated_at || "")
    const va = Number.isFinite(ta) ? ta : 0
    const vb = Number.isFinite(tb) ? tb : 0
    return modifiedSortDesc.value ? vb - va : va - vb
  })
  return list
})

const pageTotal = computed(() => {
  const n = tasksFiltered.value.length
  const ps = pageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const pagedTasks = computed(() => {
  const ps = pageSize.value
  const p = Math.min(page.value, pageTotal.value)
  const start = (p - 1) * ps
  return tasksFiltered.value.slice(start, start + ps)
})

watch([tasksFiltered, pageSize], () => {
  if (page.value > pageTotal.value) page.value = pageTotal.value
  if (page.value < 1) page.value = 1
  goToPageInput.value = String(page.value)
})

watch(pageSize, () => {
  page.value = 1
  goToPageInput.value = "1"
})

watch(searchQuery, () => {
  page.value = 1
})

watch(lastRunStatusFilter, () => {
  page.value = 1
})

function goPageFromInput() {
  const n = Number.parseInt(goToPageInput.value, 10)
  if (!Number.isFinite(n)) return
  page.value = Math.min(pageTotal.value, Math.max(1, n))
  goToPageInput.value = String(page.value)
}

function stepPage(delta: number) {
  page.value = Math.min(pageTotal.value, Math.max(1, page.value + delta))
  goToPageInput.value = String(page.value)
}

function toggleModifiedSort() {
  modifiedSortDesc.value = !modifiedSortDesc.value
}

function openTask(row: CrawleeTaskListRow) {
  router.push({ name: "CrawleeTaskDetail", params: { taskId: row.id } })
}

function openTaskTab(row: CrawleeTaskListRow, tab: string) {
  router.push({ name: "CrawleeTaskDetail", params: { taskId: row.id }, query: { tab } })
}

function openDevelopDialog() {
  newActorName.value = ""
  createDialogVisible.value = true
}

async function submitCreate() {
  if (!newActorName.value.trim()) {
    ElMessage.warning("Enter an Actor name")
    return
  }
  creating.value = true
  try {
    await createTaskApi({ name: newActorName.value.trim(), description: "" })
    ElMessage.success("Actor created")
    createDialogVisible.value = false
    newActorName.value = ""
    await load()
  } finally {
    creating.value = false
  }
}

function pricingFilterStub() {
  ElMessage.info("Pricing model filter (coming soon)")
}

function onStatusFilterCommand(c: string) {
  lastRunStatusFilter.value = c
  page.value = 1
}

const actorCountLabel = computed(() => {
  const n = tasksFiltered.value.length
  return n === 1 ? "1 task" : `${n} tasks`
})

const lastRunStatusFilterLabel = computed(() => {
  if (lastRunStatusFilter.value === "all") return "Last run status"
  return listRunStatusLabel(lastRunStatusFilter.value)
})

onMounted(() => load())
</script>

<template>
  <div class="tasks-list-page">
    <header class="tasks-list-header">
      <div class="tasks-list-title-row">
        <div class="tasks-list-title-block">
          <h1 class="tasks-list-title">
            我的任务
          </h1>
          <el-tooltip content="Each Actor is a versioned Crawlee task you can build and run." placement="bottom">
            <el-icon class="tasks-list-help">
              <QuestionFilled />
            </el-icon>
          </el-tooltip>
        </div>
        <div class="tasks-list-header-actions">
          <div class="tasks-list-action-btns">
            <el-button
              v-if="smartCreateEnabled"
              type="success"
              plain
              class="tasks-btn-smart"
              @click="goSmartCreate"
            >
              智能创建
            </el-button>
            <el-button type="primary" class="tasks-btn-develop" @click="openDevelopDialog">
              代码创建
            </el-button>
          </div>
          <p class="tasks-list-count">
            {{ actorCountLabel }}
          </p>
        </div>
      </div>
    </header>

    <div class="tasks-list-toolbar">
      <el-input
        v-model="searchQuery"
        class="tasks-search-input"
        placeholder="Search by Actor name"
        clearable
        :prefix-icon="Search"
      />
      <el-dropdown trigger="click" @command="onStatusFilterCommand">
        <el-button class="tasks-filter-btn">
          <el-icon class="tasks-filter-ico">
            <Filter />
          </el-icon>
          {{ lastRunStatusFilterLabel }}
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="all">
              All statuses
            </el-dropdown-item>
            <el-dropdown-item command="succeeded">
              Succeeded
            </el-dropdown-item>
            <el-dropdown-item command="failed">
              Failed
            </el-dropdown-item>
            <el-dropdown-item command="running">
              Running
            </el-dropdown-item>
            <el-dropdown-item command="queued">
              Queued
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button class="tasks-filter-btn" @click="pricingFilterStub">
        <el-icon class="tasks-filter-ico">
          <Filter />
        </el-icon>
        Pricing model
      </el-button>
    </div>

    <div v-loading="loading" class="tasks-table-card">
      <el-table
        :data="pagedTasks"
        class="tasks-data-table"
        size="small"
        border
        empty-text="暂无 Actor，请使用「代码创建」新建。"
        @row-dblclick="openTask"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column min-width="280">
          <template #header>
            <span class="tasks-th-sort">Name <span class="tasks-sort-caret">⇅</span></span>
          </template>
          <template #default="{ row }">
            <div class="tasks-name-cell">
              <div class="tasks-avatar" :title="actorInitials(row)">
                {{ actorInitials(row) }}
              </div>
              <div class="tasks-name-text">
                <el-button link type="primary" class="tasks-name-title" @click.stop="openTask(row)">
                  {{ row.name }}
                </el-button>
                <div class="tasks-name-meta">
                  <span class="tasks-slug">{{ actorSlug(row) }}</span>
                  <el-icon class="tasks-lock-ico">
                    <Lock />
                  </el-icon>
                  <span class="tasks-own-label">Own</span>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Modified at" width="168">
          <template #header>
            <button type="button" class="tasks-th-sort-btn" @click="toggleModifiedSort">
              <span class="tasks-th-sort">Modified at <span class="tasks-sort-caret active">{{ modifiedSortDesc ? "▼" : "▲" }}</span></span>
            </button>
          </template>
          <template #default="{ row }">
            {{ formatModifiedTs(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Total builds" width="112" align="right">
          <template #default="{ row }">
            <el-button link type="primary" class="tasks-num-link" @click.stop="openTaskTab(row, 'builds')">
              {{ row.total_builds ?? 0 }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="Default build" min-width="140">
          <template #default="{ row }">
            <el-button
              v-if="row.default_build_display && row.default_build_display !== '—'"
              link
              type="primary"
              class="tasks-num-link"
              @click.stop="openTaskTab(row, 'builds')"
            >
              {{ row.default_build_display }}
            </el-button>
            <span v-else class="tasks-dash">—</span>
          </template>
        </el-table-column>
        <el-table-column label="Total runs" width="104" align="right">
          <template #default="{ row }">
            <el-button link type="primary" class="tasks-num-link" @click.stop="openTaskTab(row, 'runs')">
              {{ row.total_runs ?? 0 }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="Last run" width="168">
          <template #default="{ row }">
            {{ formatLastRunTs(row.last_run_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Last run status" min-width="160">
          <template #default="{ row }">
            <span
              v-if="row.last_run_status"
              class="tasks-status-pill"
              :class="`tasks-status-pill--${listRunStatusKind(row.last_run_status)}`"
            >
              <el-icon v-if="row.last_run_status === 'succeeded'" class="tasks-status-pill-ico">
                <CircleCheck />
              </el-icon>
              {{ listRunStatusLabel(row.last_run_status) }}
            </span>
            <span v-else class="tasks-dash">—</span>
          </template>
        </el-table-column>
        <el-table-column label="Last run duration" width="130" align="right">
          <template #default="{ row }">
            {{ formatListRunDuration(row.last_run_duration_sec) }}
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="tasks-table-footer">
      <div class="tasks-footer-left">
        <span class="tasks-footer-label">Items per page:</span>
        <el-select v-model="pageSize" size="small" class="tasks-page-size-select">
          <el-option :value="10" label="10" />
          <el-option :value="20" label="20" />
          <el-option :value="50" label="50" />
        </el-select>
      </div>
      <div class="tasks-footer-right">
        <span class="tasks-footer-label">Go to page:</span>
        <el-input v-model="goToPageInput" class="tasks-go-input" size="small" :disabled="pageTotal <= 1" @keyup.enter="goPageFromInput" />
        <el-button size="small" :disabled="pageTotal <= 1" @click="goPageFromInput">
          Go
        </el-button>
        <div class="tasks-pager">
          <el-button size="small" :disabled="page <= 1" @click="stepPage(-1)">
            &lt;
          </el-button>
          <span class="tasks-page-num">{{ page }}</span>
          <el-button size="small" :disabled="page >= pageTotal" @click="stepPage(1)">
            &gt;
          </el-button>
        </div>
      </div>
    </div>

    <el-dialog v-model="createDialogVisible" title="代码创建" width="440px" destroy-on-close>
      <el-input v-model="newActorName" placeholder="Actor name" maxlength="255" show-word-limit @keyup.enter="submitCreate" />
      <template #footer>
        <el-button @click="createDialogVisible = false">
          Cancel
        </el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">
          Create
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
$apify-blue: #0050ff;
$apify-border: #e5e7eb;

.tasks-list-page {
  padding: 8px 24px 32px;
  max-width: 1400px;
  font-weight: 600;
}

.tasks-list-header {
  margin-bottom: 18px;
}

.tasks-list-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.tasks-list-title-block {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.tasks-list-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #111827;
}

.tasks-list-help {
  font-size: 18px;
  color: #9ca3af;
  cursor: help;
}

.tasks-list-header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.tasks-list-action-btns {
  display: inline-flex;
  gap: 10px;
}

.tasks-btn-develop {
  font-weight: 600;
  padding: 10px 18px;
  background: $apify-blue !important;
  border-color: $apify-blue !important;
}

.tasks-list-count {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.tasks-list-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.tasks-search-input {
  max-width: 360px;
  flex: 1;
  min-width: 200px;
}

.tasks-filter-btn {
  font-weight: 600;
  border-color: #d1d5db;
  color: #374151;
  background: #fff;
}

.tasks-filter-ico {
  margin-right: 6px;
  font-size: 14px;
  vertical-align: middle;
}

.tasks-table-card {
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.tasks-data-table :deep(.el-table__row) {
  cursor: pointer;
}

.tasks-data-table :deep(td),
.tasks-data-table :deep(th) {
  border-color: #f0f1f3;
}

.tasks-data-table :deep(.cell) {
  font-weight: 600;
}

.tasks-th-sort {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 700;
}

.tasks-th-sort-btn {
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.tasks-sort-caret {
  font-size: 10px;
  color: #9ca3af;
}

.tasks-sort-caret.active {
  color: $apify-blue;
}

.tasks-name-cell {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.tasks-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.02em;
}

.tasks-name-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tasks-name-title {
  font-size: 14px;
  font-weight: 700;
  padding: 0 !important;
  height: auto !important;
  justify-content: flex-start;
}

.tasks-name-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.tasks-slug {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.tasks-lock-ico {
  font-size: 12px;
  color: #9ca3af;
}

.tasks-own-label {
  color: #374151;
}

.tasks-num-link {
  font-weight: 700;
  padding: 0 !important;
  height: auto !important;
}

.tasks-dash {
  color: #9ca3af;
  font-weight: 600;
}

.tasks-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}

.tasks-status-pill--ok {
  background: #dcfce7;
  color: #166534;
}

.tasks-status-pill--bad {
  background: #fee2e2;
  color: #991b1b;
}

.tasks-status-pill--run {
  background: #ffedd5;
  color: #9a3412;
}

.tasks-status-pill--wait {
  background: #f3f4f6;
  color: #4b5563;
}

.tasks-status-pill--neutral {
  background: #f3f4f6;
  color: #374151;
}

.tasks-status-pill-ico {
  font-size: 14px;
  flex-shrink: 0;
}

.tasks-table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 0 0;
}

.tasks-footer-left,
.tasks-footer-right {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tasks-footer-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.tasks-page-size-select {
  width: 88px;
}

.tasks-go-input {
  width: 52px;
}

.tasks-go-input :deep(.el-input__inner) {
  text-align: center;
}

.tasks-pager {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
}

.tasks-page-num {
  min-width: 24px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
}
</style>
