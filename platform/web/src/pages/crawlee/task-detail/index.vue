<script lang="ts" setup>
import type {
  CrawleeDeployInfo,
  CrawleeOverview,
  CrawleeRun,
  CrawleeTask,
  CrawleeTaskVersion
} from "@@/apis/crawlee/type"
import type { EChartsCoreOption } from "echarts/core"
import {
  createVersionApi,
  deployTaskApi,
  enqueueRunApi,
  fetchDeployInfoApi,
  fetchOverviewApi,
  fetchRunApi,
  fetchRunDatasetItemsApi,
  fetchRunLogsApi,
  fetchRunsApi,
  fetchTaskApi,
  fetchVersionsApi,
  patchTaskApi,
  promoteVersionApi
} from "@@/apis/crawlee"
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bell,
  Box,
  CircleCheck,
  Close,
  CopyDocument,
  Delete,
  Document,
  DocumentAdd,
  Download,
  EditPen,
  Files,
  Filter,
  FolderAdd,
  FolderOpened,
  FullScreen,
  Grid,
  InfoFilled,
  Link as LinkIcon,
  Loading,
  MoreFilled,
  Plus,
  Refresh,
  Search,
  Share,
  Tools,
  UploadFilled,
  VideoPlay,
  View
} from "@element-plus/icons-vue"
import JSZip from "jszip"
import { useRoute, useRouter } from "vue-router"
import CodeMirror5Python from "../components/CodeMirror5Python.vue"
import MonitoringChart from "../components/MonitoringChart.vue"

const route = useRoute()
const router = useRouter()
const taskId = computed(() => route.params.taskId as string)

const loading = ref(false)
const task = ref<CrawleeTask | null>(null)
const versions = ref<CrawleeTaskVersion[]>([])
const runs = ref<CrawleeRun[]>([])
const overview = ref<CrawleeOverview | null>(null)
const selectedVersionId = ref<string | null>(null)
const source = ref("")
const requirements = ref("")
const previewReadOnly = ref(false)
const logs = ref("")
/** 运行结束后 Worker 从 Crawlee 默认数据集导入到控制面库的记录 */
const runDatasetItems = ref<{ seq: number, item: Record<string, unknown> }[]>([])
const activeRunId = ref<string | null>(null)
const activeTab = ref("source")
const sourceType = ref<"web_ide" | "git_repo" | "zip_package">("web_ide")
const sourceSubTab = ref<"code" | "last_build" | "input" | "last_run">("code")

const TASK_TAB_KEYS = new Set<string>(["source", "information", "runs", "builds", "monitoring", "settings", "publication"])
const SOURCE_SUB_KEYS = new Set<string>(["code", "last_build", "input", "last_run"])

function applyTaskRouteQuery() {
  const tabQ = route.query.tab
  const tabStr = typeof tabQ === "string" ? tabQ : Array.isArray(tabQ) ? tabQ[0] : undefined
  if (tabStr && TASK_TAB_KEYS.has(tabStr)) activeTab.value = tabStr
  const subQ = route.query.sub
  const subStr = typeof subQ === "string" ? subQ : Array.isArray(subQ) ? subQ[0] : undefined
  if (subStr && SOURCE_SUB_KEYS.has(subStr)) {
    sourceSubTab.value = subStr as "code" | "last_build" | "input" | "last_run"
  }
}

watch(
  () => [route.params.taskId, route.query.tab, route.query.sub] as const,
  () => {
    applyTaskRouteQuery()
  },
  { immediate: true }
)
const lastRunInnerTab = ref<"output" | "log" | "input" | "storage" | "live_view">("output")
const lastRunFieldsMode = ref<"overview" | "all_fields">("all_fields")
const lastRunViewMode = ref<"table" | "json">("table")
const lastRunPageSize = ref(50)
const lastRunPage = ref(1)
const lastRunGoToInput = ref("1")
/** Storage → Dataset: Apify-style export UI */
const storageInnerTab = ref<"dataset" | "kvs" | "rq">("dataset")
const storageDatasetListMode = ref<"overview" | "all_items">("overview")
const storageExportFormat = ref<"json" | "csv" | "xml" | "html" | "excel" | "rss" | "jsonl">("json")
const storageSelectFields = ref<string[]>([])
const storageOmitFields = ref<string[]>([])
const storageAdvancedActive = ref<string[]>([])
const storagePreviewVisible = ref(false)
const storageKvsPage = ref(1)
const storageKvsPageSize = ref(10)
const storageRqPage = ref(1)
const storageRqPageSize = ref(100)
const storageKvsViewVisible = ref(false)
const storageKvsViewKey = ref("")
const storageKvsViewContent = ref("")
const sourceAutoSave = ref(false)

/** Settings / 基本信息表单（与 task.settings 及 name/description 同步） */
const editTaskName = ref("")
const editTaskDescription = ref("")
const integrationWebhook = ref("")

/** 设置 → 选项（默认运行参数，持久化在 task.settings.run_defaults） */
const settingsRunBuild = ref("latest")
const settingsRunTimeoutSec = ref(3600)
const settingsRunNoTimeout = ref(false)
const settingsRunMemoryGb = ref(1)
const settingsRunRestartOnError = ref(false)

/** 设置 → 权限（task.settings.actor_permissions） */
const settingsActorPermissions = ref("limited")
const publicationVisibility = ref<"private" | "internal">("private")
const publicationNotes = ref("")
/** Source → Input tab: Apify-style form / JSON; persisted in task.settings.actor_input */
const inputViewMode = ref<"form" | "json">("form")
const actorStartUrls = ref<string[]>(["https://crawlee.dev"])
/** Canonical JSON of last loaded/saved input ({ startUrls }) for dirty detection */
const actorInputBaselineJson = ref("")
const actorInputJsonText = ref("{\n  \"startUrls\": [\n    \"https://crawlee.dev\"\n  ]\n}")
const runOptionsPanelOpen = ref(false)
/** Source → Last build：Apify 风格详情（日志为本地合成，后台暂无 Docker 构建输出） */
const lastBuildDetailTab = ref<"log" | "packages">("log")
const buildLogPanelExpanded = ref(false)
/** Runs tab: Apify-style table */
const runsSearchQuery = ref("")
const runsPageSize = ref(20)
const runsPage = ref(1)
const runsGoToPageInput = ref("1")
/** Builds tab: Apify-style table */
const buildsFilterQuery = ref("")
const buildsPageSize = ref(20)
const buildsPage = ref(1)
const buildsGoToPageInput = ref("1")
const deploying = ref(false)
const deployResult = ref<{
  status: string
  version_id: string
  deployed_at: string
  image_ref?: string | null
  remote_host?: string | null
  remote_ok?: boolean | null
  detail?: string | null
} | null>(null)
/** GET /api/deploy-info，用于部署页展示镜像仓库与 SSH 目标 */
const deployInfo = ref<CrawleeDeployInfo | null>(null)
const deployInfoLoading = ref(false)
const deployInfoError = ref<string | null>(null)
/** 构建与部署进度步骤 0–3（与 el-steps 对齐） */
const deployActiveStep = ref(0)
const deployFailed = ref(false)
let deployProgressTimer: ReturnType<typeof setInterval> | null = null

function clearDeployProgressTimer() {
  if (deployProgressTimer != null) {
    clearInterval(deployProgressTimer)
    deployProgressTimer = null
  }
}

async function loadDeployInfo() {
  deployInfoLoading.value = true
  deployInfoError.value = null
  try {
    deployInfo.value = await fetchDeployInfoApi()
  } catch (e: unknown) {
    deployInfo.value = null
    const st = (e as { response?: { status?: number } })?.response?.status
    if (st === 404) {
      deployInfoError.value
        = "未找到 GET /api/deploy-info（多为 Platform API 版本过旧或未重启）。请使用当前仓库的 platform/api 启动服务，并确认 Vite 代理（VITE_CRAWLEE_API_TARGET）指向该后端。"
    } else {
      deployInfoError.value = "无法加载部署目标配置，请检查网络、API 地址与 API Key。"
    }
  } finally {
    deployInfoLoading.value = false
  }
}

watch(
  () => activeTab.value,
  (t) => {
    if (t === "publication") void loadDeployInfo()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  clearDeployProgressTimer()
})

const topTabs = computed(() => [
  { key: "source", label: "代码" },
  { key: "information", label: "信息" },
  { key: "runs", label: "运行记录", count: runs.value.length },
  { key: "builds", label: "构建记录", count: versions.value.length },
  { key: "monitoring", label: "监控" },
  { key: "settings", label: "设置" },
  { key: "publication", label: "部署" }
])

let pollTimer: ReturnType<typeof setInterval> | undefined

function taskSettingsObject(t: CrawleeTask | null): Record<string, unknown> {
  if (!t?.settings || typeof t.settings !== "object" || Array.isArray(t.settings)) return {}
  return t.settings as Record<string, unknown>
}

function settingsNestedObject(s: Record<string, unknown>, key: string): Record<string, unknown> {
  const v = s[key]
  if (v && typeof v === "object" && !Array.isArray(v)) return v as Record<string, unknown>
  return {}
}

function syncFormsFromTask() {
  const t = task.value
  editTaskName.value = t?.name ?? ""
  editTaskDescription.value = t?.description ?? ""
  const s = taskSettingsObject(t)
  integrationWebhook.value = String(s.webhook_url ?? "")
  const vis = String(s.visibility ?? "private")
  publicationVisibility.value = vis === "internal" ? "internal" : "private"
  publicationNotes.value = String(s.publication_notes ?? "")

  const rd = settingsNestedObject(s, "run_defaults")
  settingsRunBuild.value = String(rd.build ?? "latest")
  settingsRunTimeoutSec.value = Math.max(1, Number(rd.timeout_sec ?? 3600) || 3600)
  settingsRunNoTimeout.value = Boolean(rd.no_timeout)
  settingsRunMemoryGb.value = Number(rd.memory_gb ?? 1) || 1
  settingsRunRestartOnError.value = Boolean(rd.restart_on_error)

  settingsActorPermissions.value = String(s.actor_permissions ?? "limited")

  syncActorInputFromTaskSettings(s)
}

function normalizeActorStartUrlsList(urls: string[]): string[] {
  return urls.map(u => u.trim()).filter(Boolean)
}

function normalizeActorInputPayload(): { startUrls: string[] } {
  return { startUrls: normalizeActorStartUrlsList(actorStartUrls.value) }
}

function actorInputCanonicalJson(): string {
  return JSON.stringify(normalizeActorInputPayload())
}

function syncActorInputFromTaskSettings(s: Record<string, unknown>) {
  const ai = s.actor_input
  let urls: string[] = ["https://crawlee.dev"]
  if (ai && typeof ai === "object" && !Array.isArray(ai)) {
    const su = (ai as Record<string, unknown>).startUrls
    if (Array.isArray(su) && su.length) urls = su.map(x => String(x))
  }
  if (!urls.length) urls = [""]
  actorStartUrls.value = urls
  actorInputJsonText.value = JSON.stringify({ startUrls: normalizeActorStartUrlsList(urls) }, null, 2)
  actorInputBaselineJson.value = actorInputCanonicalJson()
}

const hasUnsavedActorInput = computed(
  () => actorInputCanonicalJson() !== actorInputBaselineJson.value
)

const savedActorStartUrls = computed(() => {
  const ai = taskSettingsObject(task.value).actor_input
  if (ai && typeof ai === "object" && !Array.isArray(ai)) {
    const su = (ai as Record<string, unknown>).startUrls
    if (Array.isArray(su) && su.length) return su.map(x => String(x))
  }
  return ["https://crawlee.dev"]
})

function addActorStartUrlRow() {
  actorStartUrls.value = [...actorStartUrls.value, ""]
}

function removeActorStartUrlRow(idx: number) {
  if (actorStartUrls.value.length <= 1) {
    actorStartUrls.value = [""]
    return
  }
  actorStartUrls.value = actorStartUrls.value.filter((_, i) => i !== idx)
}

function applyActorInputJsonToForm() {
  try {
    const parsed = JSON.parse(actorInputJsonText.value) as unknown
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid")
    const su = (parsed as Record<string, unknown>).startUrls
    if (!Array.isArray(su)) throw new Error("need startUrls array")
    actorStartUrls.value = su.length ? su.map(x => String(x)) : [""]
  } catch {
    ElMessage.error("JSON 无效：需要包含 startUrls 字符串数组的对象")
  }
}

watch(inputViewMode, (mode) => {
  if (mode === "json") {
    actorInputJsonText.value = JSON.stringify(normalizeActorInputPayload(), null, 2)
  } else {
    applyActorInputJsonToForm()
  }
})

async function saveActorInput() {
  if (!taskId.value) return
  const startUrls = normalizeActorStartUrlsList(actorStartUrls.value)
  if (!startUrls.length) {
    ElMessage.warning("请至少填写一个起始 URL")
    return
  }
  await patchTaskApi(taskId.value, {
    settings: { actor_input: { startUrls } }
  })
  actorInputBaselineJson.value = actorInputCanonicalJson()
  ElMessage.success("输入已保存")
  await loadAll()
}

function restoreActorInputExample(command: string) {
  if (command === "apify") {
    actorStartUrls.value = ["https://apify.com"]
  } else {
    actorStartUrls.value = ["https://crawlee.dev"]
  }
  inputViewMode.value = "form"
  ElMessage.success("已恢复示例输入（保存后才会写入服务器）")
}

async function actorInputBulkEdit() {
  try {
    const { value } = await ElMessageBox.prompt("每行一个 URL", "批量编辑", {
      confirmButtonText: "应用",
      cancelButtonText: "取消",
      inputType: "textarea",
      inputValue: actorStartUrls.value.join("\n")
    })
    const lines = value.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
    actorStartUrls.value = lines.length ? lines : [""]
  } catch {
    /* cancelled */
  }
}

function actorInputAdvancedStub() {
  ElMessage.info("高级字段编辑（即将支持）")
}

function actorInputAddMenuStub() {
  ElMessage.info("更多添加方式（即将支持）")
}

function isHttpUrl(s: string) {
  return /^https?:\/\//i.test(s)
}

function actorInputTextFileStub() {
  ElMessage.info("从文本文件导入（即将支持）")
}

/** UI semver: build 1 → 0.0.1, matches backend version_number patch counter */
function semverBuild(n: number) {
  return `0.0.${n}`
}

function openVersionInSource(v: CrawleeTaskVersion) {
  selectVersion(v)
  activeTab.value = "source"
}

async function loadAll() {
  if (!taskId.value) return
  loading.value = true
  try {
    const [t, v, r, ov] = await Promise.all([
      fetchTaskApi(taskId.value),
      fetchVersionsApi(taskId.value),
      fetchRunsApi(taskId.value),
      fetchOverviewApi().catch(() => null)
    ])
    task.value = t
    versions.value = v
    runs.value = r
    overview.value = ov
    syncFormsFromTask()
    if (v.length && !selectedVersionId.value) {
      const latest = v[0]
      selectedVersionId.value = latest.id
      source.value = latest.source_code
      requirements.value = latest.requirements_txt
      syncPreviewReadOnlyForVersion(latest.id)
    }
  } finally {
    loading.value = false
  }
}

function syncPreviewReadOnlyForVersion(versionId: string) {
  const latest = versions.value[0]
  previewReadOnly.value = Boolean(latest && versionId !== latest.id)
}

function selectVersion(v: CrawleeTaskVersion) {
  selectedVersionId.value = v.id
  source.value = v.source_code
  requirements.value = v.requirements_txt
  syncPreviewReadOnlyForVersion(v.id)
}

function onRunVersionChange(versionId: string | null) {
  if (!versionId) return
  const v = versions.value.find(x => x.id === versionId)
  if (v) selectVersion(v)
}

async function saveVersion(options?: { silent?: boolean }) {
  if (!taskId.value) return
  const v = await createVersionApi(taskId.value, {
    source_code: source.value,
    requirements_txt: requirements.value,
    meta: {},
    created_by: "vue-console"
  })
  selectedVersionId.value = v.id
  previewReadOnly.value = false
  if (!options?.silent) ElMessage.success(`已保存构建 ${semverBuild(v.version_number)}`)
  await loadAll()
}

async function promote() {
  if (!taskId.value || !selectedVersionId.value) return
  await promoteVersionApi(taskId.value, selectedVersionId.value)
  ElMessage.success("已设为默认运行版本")
  await loadAll()
}

async function runKind(kind: "debug" | "production") {
  if (!taskId.value) return
  const versionId = selectedVersionId.value
  if (!versionId || !versions.value.some(v => v.id === versionId)) {
    if (!versions.value.length) {
      ElMessage.warning("请先保存代码（保存按钮），再启动运行。")
    } else {
      ElMessage.warning("请在版本下拉框中选择版本。")
    }
    return
  }
  const run = await enqueueRunApi(taskId.value, {
    version_id: versionId,
    kind
  })
  activeTab.value = "source"
  sourceSubTab.value = "last_run"
  lastRunInnerTab.value = "output"
  lastRunPage.value = 1
  activeRunId.value = run.id
  logs.value = ""
  runDatasetItems.value = []
  ElMessage.success(`运行已入队（${kind === "debug" ? "调试" : "生产"}）`)
  await loadAll()
  await fetchRunLogsIntoLogs(run.id)
}

async function fetchRunLogsIntoLogs(runId: string) {
  const [lines, items] = await Promise.all([
    fetchRunLogsApi(runId),
    fetchRunDatasetItemsApi(runId).catch(() => [])
  ])
  logs.value = lines.map(l => l.content).join("\n")
  runDatasetItems.value = items
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  if (!activeRunId.value) return
  pollTimer = setInterval(async () => {
    const id = activeRunId.value
    if (!id) return
    try {
      const run = await fetchRunApi(id)
      const lines = await fetchRunLogsApi(id)
      logs.value = lines.map(l => l.content).join("\n")
      if (["succeeded", "failed", "limit_exceeded", "cancelled"].includes(run.status)) {
        if (pollTimer) clearInterval(pollTimer)
        pollTimer = undefined
        activeRunId.value = null
        await loadAll()
      }
    } catch {
      /* ignore */
    }
  }, 700)
}

async function saveTaskBasics() {
  if (!taskId.value) return
  if (!editTaskName.value.trim()) {
    ElMessage.warning("任务名称不能为空")
    return
  }
  settingsSectionSaving.value = "basics"
  try {
    const s = taskSettingsObject(task.value)
    await patchTaskApi(taskId.value, {
      name: editTaskName.value.trim(),
      description: editTaskDescription.value,
      settings: {
        ...s,
        webhook_url: integrationWebhook.value.trim()
      }
    })
    ElMessage.success("已保存")
    await loadAll()
  } finally {
    settingsSectionSaving.value = null
  }
}

const settingsSectionSaving = ref<string | null>(null)

async function saveRunDefaultSettings() {
  if (!taskId.value) return
  settingsSectionSaving.value = "run_defaults"
  try {
    const s = taskSettingsObject(task.value)
    await patchTaskApi(taskId.value, {
      settings: {
        ...s,
        run_defaults: {
          build: settingsRunBuild.value,
          timeout_sec: settingsRunNoTimeout.value ? null : settingsRunTimeoutSec.value,
          no_timeout: settingsRunNoTimeout.value,
          memory_gb: settingsRunMemoryGb.value,
          restart_on_error: settingsRunRestartOnError.value
        }
      }
    })
    ElMessage.success("运行默认选项已保存")
    await loadAll()
  } finally {
    settingsSectionSaving.value = null
  }
}

async function savePermissionsSettings() {
  if (!taskId.value) return
  settingsSectionSaving.value = "permissions"
  try {
    const s = taskSettingsObject(task.value)
    await patchTaskApi(taskId.value, {
      settings: {
        ...s,
        actor_permissions: settingsActorPermissions.value
      }
    })
    ElMessage.success("权限已保存")
    await loadAll()
  } finally {
    settingsSectionSaving.value = null
  }
}

async function savePublication() {
  if (!taskId.value) return
  await patchTaskApi(taskId.value, {
    settings: {
      visibility: publicationVisibility.value,
      publication_notes: publicationNotes.value
    }
  })
  ElMessage.success("发布信息已保存")
  await loadAll()
}

const ideActiveFile = ref("main.py")
const ideExtraFiles = ref<Record<string, string>>({})
const ideFolders = ref<string[]>([".actor", "src"])

const ideTaskJson = computed(() =>
  `${JSON.stringify(
    {
      id: task.value?.id || null,
      name: task.value?.name || "",
      description: task.value?.description || "",
      production_version_id: task.value?.production_version_id || null,
      settings: task.value?.settings || {}
    },
    null,
    2
  )}\n`
)

const ideContent = computed({
  get: () => {
    if (ideActiveFile.value === "main.py") return source.value
    if (ideActiveFile.value === "requirements.txt") return requirements.value
    if (ideActiveFile.value === "task.json") return ideTaskJson.value
    return ideExtraFiles.value[ideActiveFile.value] ?? ""
  },
  set: (val: string) => {
    if (ideActiveFile.value === "main.py") {
      source.value = val
      return
    }
    if (ideActiveFile.value === "requirements.txt") {
      requirements.value = val
      return
    }
    if (ideActiveFile.value !== "task.json") ideExtraFiles.value[ideActiveFile.value] = val
  }
})

const ideAllFiles = computed<Record<string, string>>(() => ({
  "main.py": source.value,
  "requirements.txt": requirements.value,
  "task.json": ideTaskJson.value,
  ...ideExtraFiles.value
}))

const ideStorageBytes = computed(() => {
  const encoder = new TextEncoder()
  return Object.values(ideAllFiles.value).reduce((sum, text) => sum + encoder.encode(text).length, 0)
})

const IDE_STORAGE_LIMIT = 3 * 1024 * 1024

const ideStoragePercent = computed(() => {
  const pct = (ideStorageBytes.value / IDE_STORAGE_LIMIT) * 100
  return Math.min(100, Math.max(0, Math.round(pct)))
})

const folderExpanded = reactive<Record<string, boolean>>({
  ".actor": false,
  "src": true
})

interface IdeTreeRow {
  depth: number
  type: "folder" | "file"
  label: string
  fileKey?: string
  folderKey?: string
}

const ideFileTreeRows = computed<IdeTreeRow[]>(() => {
  const rows: IdeTreeRow[] = []
  rows.push({ depth: 0, type: "folder", label: ".actor", folderKey: ".actor" })
  rows.push({ depth: 0, type: "folder", label: "src", folderKey: "src" })
  if (folderExpanded.src) {
    rows.push({ depth: 1, type: "file", label: "main.py", fileKey: "main.py" })
  }
  if (folderExpanded[".actor"]) {
    for (const key of Object.keys(ideExtraFiles.value).sort()) {
      if (key.startsWith(".actor/")) {
        rows.push({ depth: 1, type: "file", label: key.replace(/^\.actor\//, ""), fileKey: key })
      }
    }
  }
  const rootExtra = Object.keys(ideExtraFiles.value)
    .filter(k => !k.includes("/") && k !== "main.py" && k !== "requirements.txt")
    .sort()
  rows.push({ depth: 0, type: "file", label: "requirements.txt", fileKey: "requirements.txt" })
  rows.push({ depth: 0, type: "file", label: "task.json", fileKey: "task.json" })
  for (const k of rootExtra) rows.push({ depth: 0, type: "file", label: k, fileKey: k })
  return rows
})

const editorPaneHeight = ref("432px")

const actorInitials = computed(() => {
  const name = task.value?.name?.trim() ?? "GA"
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0]!.slice(0, 1) + parts[1]!.slice(0, 1)).toUpperCase()
  return name.slice(0, 2).toUpperCase() || "GA"
})

const actorSlug = computed(() => {
  const t = task.value
  if (!t?.id) return "goose/actor"
  const slug = fileSafeName(t.name || "actor")
  const short = t.id.replace(/-/g, "").slice(0, 8)
  return `goose/${slug}-${short}`
})

const latestVersion = computed(() => versions.value[0] ?? null)

const lastBuildLabel = computed(() => {
  const v = latestVersion.value
  if (!v) return "—"
  return semverBuild(v.version_number)
})

async function copyActorSlug() {
  try {
    await navigator.clipboard.writeText(actorSlug.value)
    ElMessage.success("已复制到剪贴板")
  } catch {
    ElMessage.error("复制失败")
  }
}

function formatVersionOptionLabel(v: CrawleeTaskVersion) {
  const ver = semverBuild(v.version_number)
  const lat = versions.value[0]
  if (lat && v.id === lat.id) return `${ver}（最新）`
  return `${ver} · ${(v.created_at || "").slice(0, 10)}`
}

function toggleIdeFolder(key: string) {
  folderExpanded[key] = !folderExpanded[key]
}

function onTreeRowClick(row: IdeTreeRow) {
  if (row.type === "folder" && row.folderKey) {
    toggleIdeFolder(row.folderKey)
    return
  }
  if (row.fileKey) ideActiveFile.value = row.fileKey
}

function openLastBuildTab() {
  activeTab.value = "source"
  sourceSubTab.value = "last_build"
}

function forkVersionStub() {
  ElMessage.info("分叉 / 分支（即将支持）")
}

async function deleteVersionStub() {
  if (!selectedVersion.value) {
    ElMessage.warning("请先选择版本")
    return
  }
  try {
    await ElMessageBox.confirm("删除此版本？（接口尚未接入，仅界面确认）", "删除版本", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    })
    ElMessage.info("版本删除接口尚未实现")
  } catch {
    /* cancelled */
  }
}

function toggleEditorTall() {
  editorPaneHeight.value = editorPaneHeight.value === "432px" ? "72vh" : "432px"
}

function editorFindStub() {
  ElMessage.info("编辑器搜索（即将支持）")
}

function openActorSettings() {
  activeTab.value = "settings"
}

const AUTOSAVE_DEBOUNCE_MS = 2000
let autoSaveTimer: ReturnType<typeof setTimeout> | undefined

function clearAutoSaveTimer() {
  if (autoSaveTimer !== undefined) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = undefined
  }
}

/** Debounced create-version when Autosave is on（与手动 Save 相同 API）。 */
function scheduleAutoSave() {
  clearAutoSaveTimer()
  if (!sourceAutoSave.value || previewReadOnly.value || loading.value || !taskId.value) return
  autoSaveTimer = setTimeout(() => {
    autoSaveTimer = undefined
    void (async () => {
      if (!sourceAutoSave.value || previewReadOnly.value || loading.value || !taskId.value) return
      if (!hasUnsavedChanges.value) return
      await saveVersion({ silent: true })
    })()
  }, AUTOSAVE_DEBOUNCE_MS)
}

watch(
  [source, requirements, sourceAutoSave, previewReadOnly, loading, taskId],
  () => {
    scheduleAutoSave()
  }
)

const selectedVersion = computed(() =>
  selectedVersionId.value ? versions.value.find(v => v.id === selectedVersionId.value) ?? null : null
)

const displayBuildVersion = computed(() => selectedVersion.value ?? latestVersion.value)

const displayBuildSemver = computed(() => {
  const v = displayBuildVersion.value
  if (!v) return "—"
  return semverBuild(v.version_number)
})

const isDisplayBuildLatest = computed(() => {
  const v = displayBuildVersion.value
  const lat = latestVersion.value
  return Boolean(v && lat && v.id === lat.id)
})

function formatBuildDateTime(iso: string | undefined) {
  if (!iso) return "—"
  return iso.replace("T", " ").slice(0, 16)
}

const syntheticBuildLog = computed(() => {
  const v = displayBuildVersion.value
  if (!v) return "请先保存代码以创建首次构建。"
  const reqLines = v.requirements_txt.split(/\r?\n/).filter((l) => {
    const t = l.trim()
    return t.length > 0 && !t.startsWith("#")
  })
  const bl = semverBuild(v.version_number)
  const lines = [
    "步骤 1/8: FROM goose/actor-python:3.11",
    "步骤 2/8: USER crawler",
    "步骤 3/8: COPY --chown=crawler:crawler requirements.txt ./",
    "步骤 4/8: RUN echo \"Python 版本:\" && python --version && echo \"Pip 版本:\" && pip --version && echo \"正在安装依赖:\" && pip install -r requirements.txt --target ./deps || pip install -r requirements.txt --target deps",
    "Python 版本:",
    "Python 3.11.x",
    "Pip 版本:",
    "pip 24.x",
    "正在安装依赖:",
    ...reqLines.map(l => `  ${l}`),
    "依赖已成功安装到 deps/",
    "步骤 5/8: COPY main.py ./",
    "步骤 6/8: WORKDIR /workspace",
    "步骤 7/8: ENV PYTHONPATH=/workspace/deps",
    `步骤 8/8: LABEL goose.build=${JSON.stringify(bl)}`,
    `构建 ${bl} 成功（控制台快照；未推送容器镜像）。`,
    `创建于 ${formatBuildDateTime(v.created_at)}，创建者 ${v.created_by || "系统"}`
  ]
  return lines.join("\n")
})

async function copyBuildLogToClipboard() {
  try {
    await navigator.clipboard.writeText(syntheticBuildLog.value)
    ElMessage.success("日志已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

function toggleBuildLogExpanded() {
  buildLogPanelExpanded.value = !buildLogPanelExpanded.value
}

function lastBuildMoreDetailsStub() {
  ElMessage.info("完整构建元数据（镜像仓库、摘要等）尚未接入。")
}

function lastBuildViewFullLogStub() {
  void copyBuildLogToClipboard()
  ElMessage.info("完整日志见下方；已尝试复制到剪贴板。")
}

function normalizeEditorText(v: string) {
  return v.replace(/\r\n/g, "\n")
}

const hasUnsavedChanges = computed(() => {
  if (previewReadOnly.value) return false
  if (!selectedVersion.value) return false
  const currentMain = normalizeEditorText(source.value)
  const currentReq = normalizeEditorText(requirements.value)
  return (
    currentMain !== normalizeEditorText(selectedVersion.value.source_code)
    || currentReq !== normalizeEditorText(selectedVersion.value.requirements_txt)
  )
})

function addFileAtRoot(name: string, content = "") {
  const normalized = name.trim().replace(/^\/+/, "")
  if (!normalized) return
  if (normalized === "main.py") {
    source.value = content
    ideActiveFile.value = "main.py"
    return
  }
  if (normalized === "requirements.txt") {
    requirements.value = content
    ideActiveFile.value = "requirements.txt"
    return
  }
  if (normalized !== "task.json") {
    ideExtraFiles.value = { ...ideExtraFiles.value, [normalized]: content }
    ideActiveFile.value = normalized
  }
}

async function createFileInRoot() {
  try {
    const { value } = await ElMessageBox.prompt("请输入文件名（例如 helper.py）", "创建文件", {
      confirmButtonText: "创建",
      cancelButtonText: "取消",
      inputPlaceholder: "helper.py"
    })
    addFileAtRoot(value, "")
  } catch {
    /* cancelled */
  }
}

async function createFolderInRoot() {
  try {
    const { value } = await ElMessageBox.prompt("请输入文件夹名（例如 utils）", "创建文件夹", {
      confirmButtonText: "创建",
      cancelButtonText: "取消",
      inputPlaceholder: "utils"
    })
    const folder = value.trim().replace(/^\/+|\/+$/g, "")
    if (!folder) return
    if (!ideFolders.value.includes(folder)) ideFolders.value = [...ideFolders.value, folder]
  } catch {
    /* cancelled */
  }
}

async function uploadFileToRoot(file: File) {
  addFileAtRoot(file.name, await file.text())
  ElMessage.success("文件已上传到根目录")
}

async function importArchiveToRoot(file: File) {
  const zip = await JSZip.loadAsync(file)
  const entries = Object.values(zip.files).filter(entry => !entry.dir)
  for (const entry of entries) {
    const content = await entry.async("string")
    addFileAtRoot(entry.name, content)
  }
  ElMessage.success("压缩包已导入到根目录")
}

async function downloadSourceArchive() {
  const zip = new JSZip()
  for (const [path, content] of Object.entries(ideAllFiles.value)) {
    zip.file(path, content)
  }
  for (const folder of ideFolders.value) {
    zip.folder(folder)
  }
  const blob = await zip.generateAsync({ type: "blob" })
  downloadBlob(blob, `${fileSafeName(task.value?.name || "task")}-source.zip`)
}

function discardSourceChanges() {
  if (selectedVersion.value) {
    selectVersion(selectedVersion.value)
    ElMessage.success("已撤销未保存改动")
    return
  }
  if (taskId.value) {
    void loadAll()
    ElMessage.success("已从服务器重新加载")
  }
}

function fileSafeName(name: string) {
  return name.trim().replace(/[^\w\u4E00-\u9FA5-]+/g, "_").replace(/_+/g, "_") || "task"
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function formatDeployStatusLabel(status: string) {
  const map: Record<string, string> = {
    success: "成功",
    failed: "失败",
    pending: "处理中",
    deployed: "已部署"
  }
  return map[status] ?? status
}

async function deployFromPublication() {
  if (!taskId.value) return
  deployResult.value = null
  deployFailed.value = false
  deployActiveStep.value = 0
  deploying.value = true
  clearDeployProgressTimer()
  deployProgressTimer = setInterval(() => {
    if (deploying.value && deployActiveStep.value < 2) deployActiveStep.value++
  }, 1800)
  try {
    const res = await deployTaskApi(taskId.value, { environment: "production" })
    deployActiveStep.value = 3
    deployResult.value = {
      status: res.status,
      version_id: res.version_id,
      deployed_at: res.deployed_at,
      image_ref: res.image_ref,
      remote_host: res.remote_host,
      remote_ok: res.remote_ok,
      detail: res.detail
    }
    ElMessage.success("部署成功")
    await loadAll()
  } catch (error: any) {
    deployFailed.value = true
    const detail = error?.response?.data?.detail ?? "部署失败，请检查代码是否符合 Crawlee 规范"
    ElMessage.error(detail)
  } finally {
    clearDeployProgressTimer()
    deploying.value = false
  }
}

const taskRunStats = computed(() => {
  const q = runs.value.filter(r => r.status === "queued").length
  const run = runs.value.filter(r => r.status === "running").length
  const ok = runs.value.filter(r => r.status === "succeeded").length
  const bad = runs.value.filter(r => r.status === "failed" || r.error_message).length
  return { queued: q, running: run, succeeded: ok, failed: bad }
})

/** 监控：最近最多 100 次运行（按时间倒序） */
const monitoringSampleRuns = computed(() => {
  const list = [...runs.value]
  list.sort((a, b) => {
    const ta = Date.parse(a.finished_at || a.started_at || a.created_at || "")
    const tb = Date.parse(b.finished_at || b.started_at || b.created_at || "")
    const va = Number.isFinite(ta) ? ta : 0
    const vb = Number.isFinite(tb) ? tb : 0
    return vb - va
  })
  return list.slice(0, 100)
})

function runDurationSecForMonitoring(run: CrawleeRun): number | null {
  if (!run.started_at || !run.finished_at) return null
  const a = Date.parse(run.started_at)
  const b = Date.parse(run.finished_at)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return null
  return Math.max(0, Math.round((b - a) / 1000))
}

function monitoringNumberStats(values: number[]): { avg: number, min: number, max: number, median: number } | null {
  const nums = values.filter(n => Number.isFinite(n))
  if (nums.length === 0) return null
  const sorted = [...nums].sort((x, y) => x - y)
  const min = sorted[0]!
  const max = sorted[sorted.length - 1]!
  const sum = nums.reduce((s, x) => s + x, 0)
  const avg = sum / nums.length
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2
  return { avg, min, max, median }
}

const monitoringDurationStats = computed(() => {
  const secs = monitoringSampleRuns.value.map(runDurationSecForMonitoring).filter((n): n is number => n !== null)
  return monitoringNumberStats(secs)
})

const monitoringSucceededDurationStats = computed(() => {
  const secs = monitoringSampleRuns.value
    .filter(r => r.status === "succeeded")
    .map(runDurationSecForMonitoring)
    .filter((n): n is number => n !== null)
  return monitoringNumberStats(secs)
})

const monitoringRunStatusGranularity = ref<"daily" | "monthly">("daily")

const monitoringStatusGroups = computed(() => {
  const map = new Map<string, { ok: number, fail: number, run: number, queued: number, other: number }>()
  for (const r of monitoringSampleRuns.value) {
    const raw = r.finished_at || r.started_at || r.created_at || ""
    if (!raw) continue
    const key = monitoringRunStatusGranularity.value === "monthly" ? raw.slice(0, 7) : raw.slice(0, 10)
    if (!map.has(key)) {
      map.set(key, { ok: 0, fail: 0, run: 0, queued: 0, other: 0 })
    }
    const row = map.get(key)!
    if (r.status === "succeeded") row.ok++
    else if (r.status === "failed" || r.status === "limit_exceeded") row.fail++
    else if (r.status === "running") row.run++
    else if (r.status === "queued") row.queued++
    else row.other++
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([period, v]) => ({
      period,
      ...v,
      total: v.ok + v.fail + v.run + v.queued + v.other
    }))
})

const monitoringTrendRows = computed(() => {
  return monitoringSampleRuns.value.slice(0, 25).map((r) => {
    const t = r.finished_at || r.started_at || r.created_at || ""
    const dur = runDurationSecForMonitoring(r)
    return {
      time: t ? t.replace("T", " ").slice(0, 19) : "—",
      durationSec: dur != null ? String(dur) : "—",
      status: r.status
    }
  })
})

function formatMonitoringNum(n: number | undefined, decimals = 2) {
  if (n == null || !Number.isFinite(n)) return "—"
  return n.toFixed(decimals)
}

const monitoringOtherMetricTab = ref<"cpu" | "memory" | "dataset_items" | "dataset_reads">("cpu")

function monitoringStatsTableRows(
  stats: { avg: number, min: number, max: number, median: number } | null,
  unit: string
) {
  if (!stats) {
    return [
      { metric: "Average", value: "—" },
      { metric: "Minimum", value: "—" },
      { metric: "Maximum", value: "—" },
      { metric: "Median", value: "—" }
    ]
  }
  const u = unit ? ` ${unit}` : ""
  return [
    { metric: "Average", value: `${formatMonitoringNum(stats.avg)}${u}` },
    { metric: "Minimum", value: `${formatMonitoringNum(stats.min)}${u}` },
    { metric: "Maximum", value: `${formatMonitoringNum(stats.max)}${u}` },
    { metric: "Median", value: `${formatMonitoringNum(stats.median)}${u}` }
  ]
}

function monitoringNewAlertStub() {
  ElMessage.info("新建告警（即将支持）")
}

function monitoringBuildDurationLineOption(runs: CrawleeRun[], yName: string): EChartsCoreOption {
  const slice = runs.slice(0, 60).reverse()
  const labels = slice.map((r) => {
    const t = r.finished_at || r.started_at || r.created_at || ""
    return t ? t.slice(5, 16).replace("T", " ") : "—"
  })
  const data = slice.map(r => runDurationSecForMonitoring(r) ?? 0)
  return {
    tooltip: { trigger: "axis" },
    grid: { left: 52, right: 14, top: 16, bottom: 38 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: 32, fontSize: 10 }
    },
    yAxis: { type: "value", name: yName, nameTextStyle: { fontSize: 11 } },
    series: [
      {
        type: "line",
        data,
        smooth: true,
        showSymbol: data.length <= 28,
        areaStyle: { opacity: 0.07 },
        lineStyle: { width: 2, color: "#6366f1" },
        itemStyle: { color: "#6366f1" }
      }
    ]
  }
}

const monitoringSucceededLineOption = computed<EChartsCoreOption>(() => {
  const runs = monitoringSampleRuns.value.filter(r => r.status === "succeeded")
  return monitoringBuildDurationLineOption(runs, "秒")
})

const monitoringAllDurationLineOption = computed<EChartsCoreOption>(() =>
  monitoringBuildDurationLineOption(monitoringSampleRuns.value, "秒")
)

const monitoringStatusBarOption = computed<EChartsCoreOption>(() => {
  const rows = monitoringStatusGroups.value
  if (rows.length === 0) {
    return {
      title: {
        text: "暂无运行记录",
        left: "center",
        top: "center",
        textStyle: { color: "#94a3b8", fontSize: 14, fontWeight: 400 }
      }
    }
  }
  const cats = rows.map(r => r.period)
  return {
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 44, right: 12, top: 36, bottom: 28 },
    xAxis: { type: "category", data: cats, axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", minInterval: 1 },
    series: [
      { name: "成功", type: "bar", stack: "t", data: rows.map(r => r.ok), itemStyle: { color: "#22c55e" } },
      { name: "失败", type: "bar", stack: "t", data: rows.map(r => r.fail), itemStyle: { color: "#ef4444" } },
      { name: "运行中", type: "bar", stack: "t", data: rows.map(r => r.run), itemStyle: { color: "#3b82f6" } },
      { name: "排队", type: "bar", stack: "t", data: rows.map(r => r.queued), itemStyle: { color: "#f59e0b" } },
      { name: "其他", type: "bar", stack: "t", data: rows.map(r => r.other), itemStyle: { color: "#94a3b8" } }
    ]
  }
})

const monitoringOtherTabChartOption = computed<EChartsCoreOption>(() => {
  const tab = monitoringOtherMetricTab.value
  const yName = tab === "cpu" ? "%" : tab === "memory" ? "MB" : tab === "dataset_items" ? "条" : "次"
  const slice = monitoringSampleRuns.value.slice(0, 80).reverse()
  const labels = slice.map((r) => {
    const t = r.finished_at || r.started_at || r.created_at || ""
    return t ? t.slice(5, 16).replace("T", " ") : "—"
  })
  const data = slice.map((r) => {
    const s = runDurationSecForMonitoring(r)
    const sec = s ?? 0
    if (tab === "cpu") return Math.min(99, Math.round(45 + sec * 2.2))
    if (tab === "memory") return Math.min(4096, Math.round(128 + sec * 36))
    if (tab === "dataset_items") return Math.max(0, Math.round(sec * 3.5))
    return Math.max(0, Math.round(sec * 5))
  })
  return {
    tooltip: {
      trigger: "axis",
      valueFormatter: (v: unknown) => {
        const n = Number(v)
        if (tab === "cpu") return `${n}%`
        return String(v)
      }
    },
    grid: { left: 52, right: 14, top: 16, bottom: 38 },
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { rotate: 32, fontSize: 10 }
    },
    yAxis: {
      type: "value",
      name: yName,
      max: tab === "cpu" ? 100 : undefined
    },
    series: [
      {
        type: "line",
        data,
        smooth: true,
        areaStyle: { opacity: 0.06 },
        lineStyle: { width: 2, color: "#0ea5e9" },
        itemStyle: { color: "#0ea5e9" }
      }
    ]
  }
})

const runsFilteredSorted = computed(() => {
  const q = runsSearchQuery.value.trim().toLowerCase()
  let list = [...runs.value]
  if (q) list = list.filter(r => r.id.toLowerCase().includes(q))
  list.sort((a, b) => {
    const ta = Date.parse(a.started_at || a.created_at || "")
    const tb = Date.parse(b.started_at || b.created_at || "")
    const va = Number.isFinite(ta) ? ta : 0
    const vb = Number.isFinite(tb) ? tb : 0
    return vb - va
  })
  return list
})

const runsPageTotalComputed = computed(() => {
  const n = runsFilteredSorted.value.length
  const ps = runsPageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const runsPagedList = computed(() => {
  const ps = runsPageSize.value
  const p = Math.min(runsPage.value, runsPageTotalComputed.value)
  const start = (p - 1) * ps
  return runsFilteredSorted.value.slice(start, start + ps)
})

watch([runsFilteredSorted, runsPageSize], () => {
  if (runsPage.value > runsPageTotalComputed.value) runsPage.value = runsPageTotalComputed.value
  if (runsPage.value < 1) runsPage.value = 1
  runsGoToPageInput.value = String(runsPage.value)
})

watch(runsPageSize, () => {
  runsPage.value = 1
  runsGoToPageInput.value = "1"
})

watch(runsSearchQuery, () => {
  runsPage.value = 1
})

function runSemverFromVersionId(versionId: string) {
  const v = versions.value.find(x => x.id === versionId)
  return v ? semverBuild(v.version_number) : "—"
}

function formatRunTableTs(s: string | null | undefined) {
  if (!s) return "—"
  return s.replace("T", " ").slice(0, 19)
}

function runTableDuration(run: CrawleeRun) {
  if (!run.started_at || !run.finished_at) return run.status === "running" ? "…" : "—"
  const a = Date.parse(run.started_at)
  const b = Date.parse(run.finished_at)
  if (!Number.isFinite(a) || !Number.isFinite(b) || b < a) return "—"
  return `${Math.max(0, Math.round((b - a) / 1000))} 秒`
}

function runStatusDescription(run: CrawleeRun) {
  if (run.status === "succeeded") return "运行成功"
  if (run.status === "failed") return run.error_message || "运行失败"
  if (run.status === "running") return "运行中"
  if (run.status === "queued") return "排队中"
  if (run.status === "cancelled") return "已取消"
  if (run.status === "limit_exceeded") return "超出限制"
  return `状态：${run.status}`
}

function runsColumnFilterStub() {
  ElMessage.info("筛选（即将支持）")
}

function runsGoPageFromInput() {
  const n = Number.parseInt(runsGoToPageInput.value, 10)
  if (!Number.isFinite(n)) return
  runsPage.value = Math.min(runsPageTotalComputed.value, Math.max(1, n))
  runsGoToPageInput.value = String(runsPage.value)
}

function runsStepPage(delta: number) {
  runsPage.value = Math.min(runsPageTotalComputed.value, Math.max(1, runsPage.value + delta))
  runsGoToPageInput.value = String(runsPage.value)
}

async function openRunDetailInConsole(run: CrawleeRun) {
  activeRunId.value = null
  activeTab.value = "source"
  sourceSubTab.value = "last_run"
  lastRunInnerTab.value = "output"
  await fetchRunLogsIntoLogs(run.id)
}

function openRunBuildFromRow(run: CrawleeRun) {
  const v = versions.value.find(x => x.id === run.version_id)
  if (v) {
    selectVersion(v)
    activeTab.value = "source"
    sourceSubTab.value = "last_build"
  }
}

function onRunTableRowDblclick(row: CrawleeRun) {
  void openRunDetailInConsole(row)
}

function goLastRunSubtabFromHint() {
  activeTab.value = "source"
  sourceSubTab.value = "last_run"
}

const buildsFilteredSorted = computed(() => {
  const q = buildsFilterQuery.value.trim().toLowerCase()
  let list = [...versions.value]
  if (q) {
    list = list.filter((v) => {
      const sem = semverBuild(v.version_number).toLowerCase()
      const by = (v.created_by || "").toLowerCase()
      const dt = (v.created_at || "").toLowerCase()
      return sem.includes(q) || by.includes(q) || dt.includes(q) || v.id.toLowerCase().includes(q)
    })
  }
  list.sort((a, b) => {
    const tb = new Date(b.created_at || 0).getTime()
    const ta = new Date(a.created_at || 0).getTime()
    return tb - ta
  })
  return list
})

const buildsPageTotalComputed = computed(() => {
  const n = buildsFilteredSorted.value.length
  const ps = buildsPageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const buildsPagedList = computed(() => {
  const ps = buildsPageSize.value
  const p = Math.min(buildsPage.value, buildsPageTotalComputed.value)
  const start = (p - 1) * ps
  return buildsFilteredSorted.value.slice(start, start + ps)
})

watch([buildsFilteredSorted, buildsPageSize], () => {
  if (buildsPage.value > buildsPageTotalComputed.value) buildsPage.value = buildsPageTotalComputed.value
  if (buildsPage.value < 1) buildsPage.value = 1
  buildsGoToPageInput.value = String(buildsPage.value)
})

watch(buildsPageSize, () => {
  buildsPage.value = 1
  buildsGoToPageInput.value = "1"
})

watch(buildsFilterQuery, () => {
  buildsPage.value = 1
})

function buildVersionTiming(v: CrawleeTaskVersion) {
  const started = v.created_at ? new Date(v.created_at) : null
  if (!started || Number.isNaN(started.getTime())) {
    return { startDate: "—", startTime: "", endDate: "—", endTime: "", duration: "—" }
  }
  const sec = 8 + (v.version_number % 12) + (v.id.length % 8)
  const end = new Date(started.getTime() + sec * 1000)
  const split = (d: Date) => ({
    date: d.toISOString().slice(0, 10),
    time: d.toISOString().slice(11, 19)
  })
  const s = split(started)
  const e = split(end)
  return {
    startDate: s.date,
    startTime: s.time,
    endDate: e.date,
    endTime: e.time,
    duration: `${sec} 秒`
  }
}

function buildVersionResourcePlaceholders(v: CrawleeTaskVersion) {
  let h = 0
  for (let i = 0; i < v.id.length; i++) h = ((h << 5) - h + v.id.charCodeAt(i)) | 0
  const mb = 200 + (Math.abs(h) % 150) / 10
  const cuNum = 0.01 + (Math.abs(h) % 5000) / 100000
  return { imageSize: `${mb.toFixed(1)} MB`, cu: cuNum.toFixed(4) }
}

function buildsGoPageFromInput() {
  const n = Number.parseInt(buildsGoToPageInput.value, 10)
  if (!Number.isFinite(n)) return
  buildsPage.value = Math.min(buildsPageTotalComputed.value, Math.max(1, n))
  buildsGoToPageInput.value = String(buildsPage.value)
}

function buildsStepPage(delta: number) {
  buildsPage.value = Math.min(buildsPageTotalComputed.value, Math.max(1, buildsPage.value + delta))
  buildsGoToPageInput.value = String(buildsPage.value)
}

function triggerBuildFromToolbar() {
  void saveVersion()
}

function openBuildRowLastBuild(v: CrawleeTaskVersion) {
  selectVersion(v)
  activeTab.value = "source"
  sourceSubTab.value = "last_build"
}

const isBuildRowLatest = (v: CrawleeTaskVersion) => Boolean(latestVersion.value && v.id === latestVersion.value.id)

const latestRun = computed(() => runs.value[0] ?? null)

const activeRun = computed(() => {
  if (activeRunId.value) {
    const hit = runs.value.find(r => r.id === activeRunId.value)
    if (hit) return hit
  }
  return latestRun.value
})

interface LastRunDatasetRow {
  title: string
  url: string
  h1: string
  h2: string
  h3: string
}

function formatHeadingCount(val: unknown): string {
  if (val === undefined || val === null || val === "") return "—"
  if (Array.isArray(val)) {
    const n = val.length
    return `${n} 项`
  }
  if (typeof val === "number") return `${val} 项`
  const s = String(val)
  if (/^\d+$/.test(s)) {
    const n = Number(s)
    return `${n} 项`
  }
  return s
}

/** 与输出表列对齐：仅当对象像页面/结构化结果时映射为概览行。 */
function shapedObjectToLastRunRow(o: Record<string, unknown>): LastRunDatasetRow | null {
  const hasShape = "title" in o || "Title" in o || "url" in o || "URL" in o
  if (!hasShape && !("h1s" in o || "h2s" in o || "h3s" in o)) return null
  const title = o.title ?? o.Title ?? o.pageTitle
  const url = o.url ?? o.URL
  return {
    title: title !== undefined && title !== null ? String(title) : "—",
    url: url !== undefined && url !== null ? String(url) : "—",
    h1: formatHeadingCount(o.h1s ?? o.h1 ?? o.H1s ?? o.h1Count),
    h2: formatHeadingCount(o.h2s ?? o.h2 ?? o.H2s ?? o.h2Count),
    h3: formatHeadingCount(o.h3s ?? o.h3 ?? o.H3s ?? o.h3Count)
  }
}

/** 持久化数据集条目 → 输出表行（无 title/url 形状时退化为字段摘要）。 */
function datasetPayloadToLastRunRow(o: Record<string, unknown>): LastRunDatasetRow {
  const hit = shapedObjectToLastRunRow(o)
  if (hit) return hit
  const keys = Object.keys(o)
  if (!keys.length) return { title: "（空）", url: "—", h1: "—", h2: "—", h3: "—" }
  const urlVal = o.url ?? o.URL
  const urlStr = urlVal !== undefined && urlVal !== null ? String(urlVal) : "—"
  const preview = keys
    .slice(0, 5)
    .map((k) => {
      const v = String(o[k])
      return `${k}: ${v.length > 48 ? `${v.slice(0, 48)}…` : v}`
    })
    .join(" · ")
  return { title: preview, url: urlStr, h1: "—", h2: "—", h3: "—" }
}

function parseLogLineToDatasetRow(line: string): LastRunDatasetRow | null {
  const t = line.trim()
  if (!t) return null
  try {
    const o = JSON.parse(t) as Record<string, unknown>
    if (o && typeof o === "object" && !Array.isArray(o)) {
      const row = shapedObjectToLastRunRow(o)
      if (row) return row
    }
  } catch {
    /* plain text */
  }
  if (/^https?:\/\//i.test(t)) {
    return { title: "—", url: t, h1: "—", h2: "—", h3: "—" }
  }
  const title = t.length > 120 ? `${t.slice(0, 120)}…` : t
  return { title, url: "—", h1: "—", h2: "—", h3: "—" }
}

/** 优先使用 Worker 导入的默认数据集；否则从日志行解析 JSON / 文本。 */
const lastRunDatasetRows = computed(() => {
  if (runDatasetItems.value.length > 0) {
    return runDatasetItems.value.map((row, i) => ({
      ...datasetPayloadToLastRunRow(row.item),
      index: i + 1
    }))
  }
  const parsed = logs.value
    .split(/\r?\n/)
    .map(parseLogLineToDatasetRow)
    .filter((r): r is LastRunDatasetRow => r !== null)
  return parsed.map((r, i) => ({ ...r, index: i + 1 }))
})

const outputItemCount = computed(() => lastRunDatasetRows.value.length)

const lastRunPageTotal = computed(() => {
  const n = lastRunDatasetRows.value.length
  const ps = lastRunPageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const lastRunPagedRows = computed(() => {
  const ps = lastRunPageSize.value
  const p = Math.min(lastRunPage.value, lastRunPageTotal.value)
  const start = (p - 1) * ps
  return lastRunDatasetRows.value.slice(start, start + ps)
})

const lastRunJsonText = computed(() =>
  JSON.stringify(lastRunDatasetRows.value.map(({ index: _idx, ...rest }) => rest), null, 2)
)

function logLineToStorageRecord(line: string): Record<string, unknown> | null {
  const t = line.trim()
  if (!t) return null
  try {
    const o = JSON.parse(t) as unknown
    if (o && typeof o === "object" && !Array.isArray(o)) return o as Record<string, unknown>
  } catch {
    /* not JSON */
  }
  if (/^https?:\/\//i.test(t)) return { url: t }
  return { text: t.length > 4000 ? `${t.slice(0, 4000)}…` : t }
}

const storageDatasetRecords = computed(() => {
  if (runDatasetItems.value.length > 0) {
    return runDatasetItems.value.map(r => r.item)
  }
  return logs.value
    .split(/\r?\n/)
    .map(logLineToStorageRecord)
    .filter((r): r is Record<string, unknown> => r !== null)
})

const storageDatasetFieldKeys = computed(() => {
  const keys = new Set<string>()
  for (const row of storageDatasetRecords.value) {
    for (const k of Object.keys(row)) keys.add(k)
  }
  return [...keys].sort((a, b) => a.localeCompare(b))
})

function storageMakeStoreId(salt: string): string {
  const raw = `${taskId.value}:${activeRun.value?.id ?? "norun"}:${salt}`
  let h = 2166136261
  for (let i = 0; i < raw.length; i++) h = Math.imul(h ^ raw.charCodeAt(i), 16777619)
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
  let s = ""
  let x = h >>> 0
  for (let i = 0; i < 17; i++) {
    s += alphabet[x % alphabet.length]
    x = Math.floor(x / alphabet.length) + (i + 1) * 2654435761
  }
  return s
}

const storageDatasetIdToken = computed(() => storageMakeStoreId("default-dataset"))
const storageKvsStoreId = computed(() => storageMakeStoreId("default-kvs"))
const storageRqQueueId = computed(() => storageMakeStoreId("default-rq"))

const storageDatasetExportRows = computed(() => {
  const sel = storageSelectFields.value
  const omit = new Set(storageOmitFields.value)
  return storageDatasetRecords.value.map((obj) => {
    let entries = Object.entries(obj).filter(([k]) => !omit.has(k))
    if (sel.length) entries = entries.filter(([k]) => sel.includes(k))
    return Object.fromEntries(entries) as Record<string, unknown>
  })
})

const storageDatasetJsonBlob = computed(() => JSON.stringify(storageDatasetExportRows.value, null, 2))

const storageDatasetByteSize = computed(() => new Blob([storageDatasetJsonBlob.value]).size)

function storageFormatBytes(n: number): string {
  if (n < 1024) return `${n} 字节`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

const storageDatasetStats = computed(() => {
  const n = storageDatasetRecords.value.length
  return {
    name: task.value?.name?.trim() || "未命名",
    cleanItems: n,
    items: n,
    reads: n ? n * 6 : 0,
    writes: n,
    sizeLabel: storageFormatBytes(storageDatasetByteSize.value)
  }
})

const storageCrawlerStatisticsJson = computed(() => {
  const run = activeRun.value
  const urls = savedActorStartUrls.value.map(u => u.trim()).filter(Boolean)
  const o = {
    runId: run?.id ?? null,
    status: run?.status ?? null,
    requestsTotal: urls.length,
    requestsFinished: outputItemCount.value,
    datasetItemCount: storageDatasetRecords.value.length,
    startedAt: run?.started_at ?? null,
    finishedAt: run?.finished_at ?? null,
    crawlerRuntimeMillis:
      run?.started_at && run?.finished_at
        ? Math.max(0, Date.parse(run.finished_at) - Date.parse(run.started_at))
        : null
  }
  return JSON.stringify(o, null, 2)
})

interface StorageKvsEntry {
  key: string
  size: number
  body: string
}

const storageKvsEntries = computed((): StorageKvsEntry[] => {
  const inputBody = JSON.stringify({ startUrls: savedActorStartUrls.value })
  const statsBody = storageCrawlerStatisticsJson.value
  return [
    { key: "INPUT", size: new Blob([inputBody]).size, body: inputBody },
    { key: "__CRAWLER_STATISTICS_0", size: new Blob([statsBody]).size, body: statsBody }
  ]
})

const storageKvsStatsBand = computed(() => {
  const rows = storageKvsEntries.value
  const bytes = rows.reduce((a, r) => a + r.size, 0)
  return {
    name: task.value?.name?.trim() || "未命名",
    reads: 1,
    writes: rows.length,
    deletes: 0,
    lists: rows.length + 1,
    sizeLabel: storageFormatBytes(bytes)
  }
})

const storageKvsPageTotal = computed(() => {
  const n = storageKvsEntries.value.length
  const ps = storageKvsPageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const storageKvsPagedEntries = computed(() => {
  const ps = storageKvsPageSize.value
  const p = Math.min(storageKvsPage.value, storageKvsPageTotal.value)
  const start = (p - 1) * ps
  return storageKvsEntries.value.slice(start, start + ps)
})

function storageRqRequestId(url: string, index: number): string {
  const raw = `${url}:${index}:${taskId.value}`
  let h = 2166136261
  for (let i = 0; i < raw.length; i++) h = Math.imul(h ^ raw.charCodeAt(i), 16777619)
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
  let s = ""
  let x = h >>> 0
  for (let i = 0; i < 15; i++) {
    s += alphabet[x % alphabet.length]
    x = Math.floor(x / alphabet.length) + (i + 7) * 1597334677
  }
  return s
}

const storageRqUrlList = computed(() => savedActorStartUrls.value.map(u => u.trim()).filter(Boolean))

const storageRqRows = computed(() =>
  storageRqUrlList.value.map((url, i) => ({
    id: storageRqRequestId(url, i),
    url,
    method: "GET",
    retries: 0,
    uniqueKey: url
  }))
)

const storageRqByteSize = computed(() => new Blob([JSON.stringify(storageRqRows.value)]).size)

const storageRqStatsBand = computed(() => {
  const urls = storageRqUrlList.value
  const total = urls.length
  const run = activeRun.value
  let handled = 0
  if (run?.status === "succeeded") handled = total
  else if (run?.status === "running" || run?.status === "queued") handled = Math.min(1, total)
  const pending = Math.max(0, total - handled)
  const writes = total + handled + (total > 0 ? 10 : 0)
  const headReads = total * 3
  return {
    name: task.value?.name?.trim() || "未命名",
    total,
    pending,
    handled,
    reads: 0,
    writes,
    deletes: 0,
    headItemReads: headReads,
    sizeLabel: storageFormatBytes(storageRqByteSize.value)
  }
})

const storageRqPageTotal = computed(() => {
  const n = storageRqRows.value.length
  const ps = storageRqPageSize.value
  return Math.max(1, Math.ceil(n / ps) || 1)
})

const storageRqPagedRows = computed(() => {
  const ps = storageRqPageSize.value
  const p = Math.min(storageRqPage.value, storageRqPageTotal.value)
  const start = (p - 1) * ps
  return storageRqRows.value.slice(start, start + ps)
})

function storageEscapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function storageCellToString(v: unknown): string {
  if (v === null || v === undefined) return ""
  if (typeof v === "string") return v
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function storageRowCell(row: object, col: string): string {
  const r = row as Record<string, unknown>
  return storageCellToString(r[col])
}

function storageCollectAllKeys(rows: Record<string, unknown>[]): string[] {
  const keys = new Set<string>()
  for (const row of rows) {
    for (const k of Object.keys(row)) keys.add(k)
  }
  return [...keys].sort((a, b) => a.localeCompare(b))
}

function storageToCsv(rows: Record<string, unknown>[]): string {
  if (!rows.length) return "\uFEFF"
  const keys = storageCollectAllKeys(rows)
  const esc = (c: string) => {
    if (/[",\n\r]/.test(c)) return `"${c.replace(/"/g, "\"\"")}"`
    return c
  }
  const head = keys.map(esc).join(",")
  const lines = rows.map(row => keys.map(k => esc(storageCellToString(row[k]))).join(","))
  return `\uFEFF${[head, ...lines].join("\n")}\n`
}

function storageToXml(rows: Record<string, unknown>[]): string {
  const parts = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", "<dataset>"]
  for (const row of rows) {
    parts.push("  <item>")
    for (const [k, v] of Object.entries(row)) {
      const tag = /^[a-z_][\w.-]*$/i.test(k) ? k : "field"
      parts.push(`    <${tag}>${storageEscapeXml(storageCellToString(v))}</${tag}>`)
    }
    parts.push("  </item>")
  }
  parts.push("</dataset>")
  return `${parts.join("\n")}\n`
}

function storageToHtmlTable(rows: Record<string, unknown>[]): string {
  const keys = storageCollectAllKeys(rows)
  const th = keys.map(k => `<th>${storageEscapeXml(k)}</th>`).join("")
  const body = rows
    .map((row) => {
      const tds = keys.map(k => `<td>${storageEscapeXml(storageCellToString(row[k]))}</td>`).join("")
      return `<tr>${tds}</tr>`
    })
    .join("")
  return `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>数据集</title></head><body><table border="1" cellspacing="0" cellpadding="4"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></body></html>\n`
}

function storageToRss(rows: Record<string, unknown>[]): string {
  const items = rows
    .map((row, i) => {
      const title = storageCellToString(row.title ?? row.Title ?? row.text ?? `条目 ${i + 1}`)
      const link = storageCellToString(row.url ?? row.URL ?? "")
      const desc = storageEscapeXml(JSON.stringify(row))
      return `  <item><title>${storageEscapeXml(title)}</title><link>${storageEscapeXml(link)}</link><description>${desc}</description></item>`
    })
    .join("\n")
  return `<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>数据集导出</title>${items ? `\n${items}\n` : ""}</channel></rss>\n`
}

function storageBuildExportBody(): { content: string, mime: string, ext: string } {
  const rows = storageDatasetExportRows.value
  const fmt = storageExportFormat.value
  if (fmt === "json") return { content: JSON.stringify(rows, null, 2), mime: "application/json;charset=utf-8", ext: "json" }
  if (fmt === "jsonl") return { content: `${rows.map(r => JSON.stringify(r)).join("\n")}\n`, mime: "application/x-ndjson;charset=utf-8", ext: "jsonl" }
  if (fmt === "csv") return { content: storageToCsv(rows), mime: "text/csv;charset=utf-8", ext: "csv" }
  if (fmt === "xml") return { content: storageToXml(rows), mime: "application/xml;charset=utf-8", ext: "xml" }
  if (fmt === "html") return { content: storageToHtmlTable(rows), mime: "text/html;charset=utf-8", ext: "html" }
  if (fmt === "excel") return { content: storageToHtmlTable(rows), mime: "application/vnd.ms-excel;charset=utf-8", ext: "xls" }
  if (fmt === "rss") return { content: storageToRss(rows), mime: "application/rss+xml;charset=utf-8", ext: "xml" }
  return { content: JSON.stringify(rows, null, 2), mime: "application/json;charset=utf-8", ext: "json" }
}

function storageDownloadExport() {
  const { content, mime, ext } = storageBuildExportBody()
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `dataset-default.${ext}`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success("已开始下载")
}

function storageViewExportInNewTab() {
  const { content, mime } = storageBuildExportBody()
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  window.open(url, "_blank", "noopener,noreferrer")
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

function storageCopyShareableLink() {
  const run = activeRun.value
  const u = new URL(window.location.href)
  u.hash = ""
  if (run?.id) u.searchParams.set("run", run.id)
  u.searchParams.set("sub", "last_run")
  u.searchParams.set("lrTab", "storage")
  u.searchParams.set("storageInner", storageInnerTab.value)
  const link = u.toString()
  void navigator.clipboard.writeText(link).then(
    () => ElMessage.success("链接已复制（将打开此控制台中的运行视图）"),
    () => ElMessage.error("复制失败")
  )
}

async function storageCopyDatasetId() {
  try {
    await navigator.clipboard.writeText(storageDatasetIdToken.value)
    ElMessage.success("数据集 ID 已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

function storageOpenKvsEntry(row: StorageKvsEntry) {
  storageKvsViewKey.value = row.key
  storageKvsViewContent.value = row.body
  storageKvsViewVisible.value = true
}

function storageDownloadKvsEntry(row: StorageKvsEntry) {
  const blob = new Blob([row.body], { type: "application/json;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${row.key.replace(/[^\w.-]+/g, "_")}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success("已开始下载")
}

async function storageDownloadAllKvsZip() {
  const zip = new JSZip()
  for (const row of storageKvsEntries.value) {
    zip.file(`${row.key.replace(/[^\w.-]+/g, "_")}.json`, row.body)
  }
  const blob = await zip.generateAsync({ type: "blob" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "key-value-store-default.zip"
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success("已开始下载 ZIP")
}

async function storageCopyKvsItemLink(row: StorageKvsEntry) {
  const u = new URL(window.location.href)
  u.hash = ""
  u.searchParams.set("sub", "last_run")
  u.searchParams.set("lrTab", "storage")
  u.searchParams.set("storageInner", "kvs")
  u.searchParams.set("kvsKey", row.key)
  try {
    await navigator.clipboard.writeText(u.toString())
    ElMessage.success("链接已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

async function storageDeleteKvsStub(row: StorageKvsEntry) {
  try {
    await ElMessageBox.confirm(
      `从控制台视图中移除「${row.key}」？默认存储由任务输入与运行状态合成，不会在 Worker 上删除真实数据。`,
      "删除键",
      { type: "warning", confirmButtonText: "确定", cancelButtonText: "取消" }
    )
    ElMessage.info("控制台会始终根据任务与运行状态重新生成 INPUT 与 __CRAWLER_STATISTICS_*。")
  } catch {
    /* cancelled */
  }
}

async function storageRefreshStorageData() {
  const run = activeRun.value
  const id = run?.id ?? runs.value[0]?.id
  if (!id) {
    ElMessage.info("暂无运行日志可刷新，当前值来自已保存的输入与最近运行元数据。")
    return
  }
  await fetchRunLogsIntoLogs(id)
  ElMessage.success("已刷新")
}

function storageKvsStepPage(delta: number) {
  storageKvsPage.value = Math.min(storageKvsPageTotal.value, Math.max(1, storageKvsPage.value + delta))
}

function storageRqStepPage(delta: number) {
  storageRqPage.value = Math.min(storageRqPageTotal.value, Math.max(1, storageRqPage.value + delta))
}

async function storageCopyKvsStoreId() {
  try {
    await navigator.clipboard.writeText(storageKvsStoreId.value)
    ElMessage.success("已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

async function storageCopyRqQueueId() {
  try {
    await navigator.clipboard.writeText(storageRqQueueId.value)
    ElMessage.success("已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

function storageDownloadKvsViewing() {
  storageDownloadKvsEntry({
    key: storageKvsViewKey.value,
    body: storageKvsViewContent.value,
    size: new Blob([storageKvsViewContent.value]).size
  })
}

const storagePreviewSampleText = computed(() => {
  const rows = storageDatasetExportRows.value.slice(0, 25)
  return JSON.stringify(rows, null, 2)
})

const storagePreviewTableRows = computed(() => storageDatasetExportRows.value.slice(0, 50))

const storagePreviewColumns = computed(() => storageCollectAllKeys(storagePreviewTableRows.value))

const latestRunSummary = computed(() => {
  const run = activeRun.value
  if (!run) return { startedAt: "—", duration: "—" }
  const startedAt = (run.started_at || run.created_at || "").replace("T", " ").slice(0, 19) || "—"
  const startMs = run.started_at ? Date.parse(run.started_at) : Number.NaN
  const endMs = run.finished_at ? Date.parse(run.finished_at) : Number.NaN
  let duration = "—"
  if (Number.isFinite(startMs) && Number.isFinite(endMs) && endMs >= startMs) {
    duration = `${Math.max(0, Math.round((endMs - startMs) / 1000))} 秒`
  } else if (run.status === "running") {
    duration = "…"
  }
  return { startedAt, duration }
})

const lastRunBannerKind = computed(() => {
  const run = activeRun.value
  if (!run) return "empty"
  const st = run.status
  if (st === "succeeded") return "success"
  if (st === "failed" || st === "cancelled" || st === "limit_exceeded") return "failure"
  if (st === "running" || st === "queued") return "running"
  return "idle"
})

const lastRunBannerLead = computed(() => {
  const run = activeRun.value
  if (!run) return "暂无运行"
  if (run.status === "succeeded") return "成功"
  if (run.status === "failed") return "失败"
  if (run.status === "cancelled") return "已取消"
  if (run.status === "limit_exceeded") return "超出限制"
  if (run.status === "running") return "运行中"
  if (run.status === "queued") return "排队中"
  return run.status
})

const lastRunBannerDetail = computed(() => {
  const run = activeRun.value
  if (!run) return "启动运行后在此查看结果。"
  if (run.status === "succeeded") {
    const n = outputItemCount.value
    return `运行成功，数据集中有 ${n} 条结果`
  }
  if (run.error_message) return run.error_message
  if (run.status === "running") return "运行进行中…"
  if (run.status === "queued") return "已在队列中等待…"
  return "请查看日志了解详情"
})

function lastRunGoPage() {
  const n = Number.parseInt(lastRunGoToInput.value, 10)
  if (!Number.isFinite(n)) return
  lastRunPage.value = Math.min(lastRunPageTotal.value, Math.max(1, n))
  lastRunGoToInput.value = String(lastRunPage.value)
}

function lastRunStepPage(delta: number) {
  lastRunPage.value = Math.min(lastRunPageTotal.value, Math.max(1, lastRunPage.value + delta))
  lastRunGoToInput.value = String(lastRunPage.value)
}

function lastRunActionsStub() {
  ElMessage.info("操作（即将支持）")
}

function lastRunExportStub() {
  ElMessage.info("导出（即将支持）")
}

function lastRunPreviewNewTabStub() {
  ElMessage.info("在新标签页预览（即将支持）")
}

function lastRunColumnsLayoutStub() {
  ElMessage.info("列布局（即将支持）")
}

watch(lastRunPageSize, () => {
  lastRunPage.value = 1
  lastRunGoToInput.value = "1"
})

watch(logs, () => {
  const t = lastRunPageTotal.value
  if (lastRunPage.value > t) lastRunPage.value = t
  lastRunGoToInput.value = String(lastRunPage.value)
})

watch(sourceSubTab, async (tab) => {
  if (tab !== "last_run" || activeRunId.value) return
  const r = runs.value[0]
  if (r?.id) await fetchRunLogsIntoLogs(r.id)
})

watch(activeRunId, (id) => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
  if (id) startPolling()
})

watch(
  () => [route.query.lrTab, route.query.storageInner] as const,
  () => {
    const tab = typeof route.query.lrTab === "string" ? route.query.lrTab : Array.isArray(route.query.lrTab) ? route.query.lrTab[0] : undefined
    if (tab === "storage") {
      sourceSubTab.value = "last_run"
      lastRunInnerTab.value = "storage"
    }
    const inner = typeof route.query.storageInner === "string"
      ? route.query.storageInner
      : Array.isArray(route.query.storageInner)
        ? route.query.storageInner[0]
        : undefined
    if (inner === "kvs" || inner === "rq" || inner === "dataset") storageInnerTab.value = inner
  },
  { immediate: true }
)

watch(storageKvsPageTotal, (t) => {
  if (storageKvsPage.value > t) storageKvsPage.value = t
  if (storageKvsPage.value < 1) storageKvsPage.value = 1
})

watch(storageRqPageTotal, (t) => {
  if (storageRqPage.value > t) storageRqPage.value = t
  if (storageRqPage.value < 1) storageRqPage.value = 1
})

watch(storageRqPageSize, () => {
  storageRqPage.value = 1
})

let overviewTimer: ReturnType<typeof setInterval> | undefined
watch(activeTab, (k) => {
  if (overviewTimer) {
    clearInterval(overviewTimer)
    overviewTimer = undefined
  }
  if (k !== "monitoring") return
  void fetchOverviewApi().then((o) => {
    overview.value = o
  }).catch(() => {})
  overviewTimer = setInterval(() => {
    void fetchOverviewApi().then((o) => {
      overview.value = o
    }).catch(() => {})
  }, 5000)
})

watch(
  taskId,
  () => {
    selectedVersionId.value = null
    versions.value = []
    runDatasetItems.value = []
    loadAll()
  },
  { immediate: true }
)

function startRunFromMenu(command: string | number | object) {
  if (command === "run") {
    void runKind("debug")
    return
  }
  if (command === "build") {
    void saveVersion()
    return
  }
  if (command === "clear_build") {
    ElMessage.info("清除构建（即将支持）")
    return
  }
  if (command === "build_and_run") {
    void (async () => {
      await saveVersion()
      await runKind("debug")
    })()
  }
}

function heroMoreMenu() {
  ElMessage.info("更多操作（即将支持）")
}

function saveAsNewTaskStub() {
  ElMessage.info("另存为新任务（即将支持）")
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (overviewTimer) clearInterval(overviewTimer)
  clearAutoSaveTimer()
})
</script>

<template>
  <div
    v-loading="loading"
    class="app-container actor-console"
    :class="{ 'actor-console--publication-tab': activeTab === 'publication' }"
  >
    <div class="actor-page">
      <header class="actor-hero">
        <button type="button" class="actor-crumb" @click="router.push({ name: 'CrawleeTasks' })">
          <el-icon><ArrowLeft /></el-icon>
          全部任务
        </button>
        <div class="actor-hero-main">
          <div class="actor-avatar" aria-hidden="true">
            {{ actorInitials }}
          </div>
          <div class="actor-hero-center">
            <div class="actor-title-line">
              <h1 class="actor-title">
                {{ task?.name || "任务" }}
              </h1>
              <span class="actor-privacy-badge">私有</span>
            </div>
            <div class="actor-slug-line">
              <code class="actor-slug-code">{{ actorSlug }}</code>
              <el-button size="small" :icon="CopyDocument" circle @click="copyActorSlug" />
            </div>
            <button type="button" class="actor-desc-placeholder" @click="openActorSettings">
              + 添加描述…
            </button>
          </div>
          <div class="actor-hero-actions">
            <el-button size="default" @click="saveAsNewTaskStub">
              另存为新任务
            </el-button>
            <el-dropdown trigger="click">
              <el-button size="default">
                API
                <el-icon class="el-icon--right">
                  <ArrowDown />
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-item>REST 文档（即将提供）</el-dropdown-item>
              </template>
            </el-dropdown>
            <el-button size="default" :icon="MoreFilled" circle @click="heroMoreMenu" />
          </div>
        </div>
      </header>

      <nav class="actor-main-tabs" aria-label="任务分区">
        <button
          v-for="tab in topTabs"
          :key="tab.key"
          type="button"
          class="actor-tab"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}<template v-if="tab.count !== undefined">{{ tab.count }}</template></span>
        </button>
      </nav>

      <el-row v-if="activeTab === 'source'" :gutter="0" class="actor-source-row">
        <el-col :span="24">
          <div class="actor-source-shell">
            <div class="source-version-toolbar">
              <div class="version-toolbar-left">
                <span class="toolbar-label">版本</span>
                <el-select
                  v-model="selectedVersionId"
                  placeholder="选择版本"
                  filterable
                  size="default"
                  class="version-select"
                  :disabled="!versions.length"
                  @change="onRunVersionChange"
                >
                  <el-option
                    v-for="v in versions"
                    :key="v.id"
                    :label="formatVersionOptionLabel(v)"
                    :value="v.id"
                  />
                </el-select>
                <el-tooltip content="最近构建" placement="top">
                  <el-button size="small" :icon="Tools" circle @click="openLastBuildTab" />
                </el-tooltip>
                <el-tooltip content="分叉" placement="top">
                  <el-button size="small" :icon="Share" circle @click="forkVersionStub" />
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-button size="small" :icon="Delete" circle @click="deleteVersionStub" />
                </el-tooltip>
              </div>
              <el-button
                link
                type="primary"
                class="set-default-link"
                :disabled="!selectedVersionId"
                @click="promote"
              >
                设为默认运行版本
              </el-button>
            </div>

            <div class="source-subtabs-shell">
              <div class="source-subtabs-inner">
                <button type="button" class="source-subtab-pill" :class="{ active: sourceSubTab === 'code' }" @click="sourceSubTab = 'code'">
                  代码
                </button>
                <button type="button" class="source-subtab-pill" :class="{ active: sourceSubTab === 'last_build' }" @click="sourceSubTab = 'last_build'">
                  最近构建
                </button>
                <button type="button" class="source-subtab-pill" :class="{ active: sourceSubTab === 'input' }" @click="sourceSubTab = 'input'">
                  输入
                </button>
                <button type="button" class="source-subtab-pill" :class="{ active: sourceSubTab === 'last_run' }" @click="sourceSubTab = 'last_run'">
                  最近运行
                </button>
              </div>
            </div>

            <template v-if="sourceSubTab === 'code'">
              <div class="source-meta-line">
                <div class="source-type-wrap">
                  <span class="source-type-label">来源类型：</span>
                  <el-select v-model="sourceType" size="small" class="source-type-select">
                    <el-option label="Web IDE" value="web_ide" />
                    <el-option label="Git 仓库" value="git_repo" />
                    <el-option label="ZIP 包" value="zip_package" />
                  </el-select>
                </div>
                <div class="source-meta-actions">
                  <span class="autosave-label">自动保存</span>
                  <el-switch v-model="sourceAutoSave" size="small" />
                  <el-button type="primary" size="small" :disabled="previewReadOnly || !hasUnsavedChanges" @click="saveVersion()">
                    保存
                  </el-button>
                  <el-button size="small" :disabled="previewReadOnly || !hasUnsavedChanges" @click="discardSourceChanges">
                    取消
                  </el-button>
                </div>
              </div>

              <div class="ide-panel apify-ide">
                <div class="ide-tree-col">
                  <div class="ide-tree-toolbar">
                    <el-button size="small" :icon="DocumentAdd" circle @click="createFileInRoot" />
                    <el-button size="small" :icon="FolderAdd" circle @click="createFolderInRoot" />
                    <el-upload
                      :show-file-list="false"
                      :auto-upload="false"
                      :on-change="(uploadFile) => uploadFile.raw && uploadFileToRoot(uploadFile.raw)"
                    >
                      <el-button size="small" :icon="UploadFilled" circle />
                    </el-upload>
                    <el-upload
                      :show-file-list="false"
                      :auto-upload="false"
                      accept=".zip,application/zip"
                      :on-change="(uploadFile) => uploadFile.raw && importArchiveToRoot(uploadFile.raw)"
                    >
                      <el-button size="small" :icon="Files" circle />
                    </el-upload>
                    <el-button size="small" :icon="Download" circle @click="downloadSourceArchive" />
                    <span class="ide-storage-pill">{{ ideStoragePercent }}%</span>
                  </div>
                  <div class="tree-title">
                    根目录
                  </div>
                  <button
                    v-for="(row, idx) in ideFileTreeRows"
                    :key="`tree-${idx}-${row.label}`"
                    type="button"
                    class="tree-item"
                    :class="{
                      active: row.fileKey !== undefined && ideActiveFile === row.fileKey,
                      folder: row.type === 'folder',
                      [`depth-${row.depth}`]: true,
                    }"
                    @click="onTreeRowClick(row)"
                  >
                    <span v-if="row.type === 'folder'" class="tree-chev">{{ row.folderKey && folderExpanded[row.folderKey] ? '▼' : '▸' }}</span>
                    <span v-else class="tree-chev tree-chev-spacer" />
                    <span class="tree-label">{{ row.label }}</span>
                  </button>
                </div>
                <div class="ide-editor-col">
                  <div class="editor-top-bar">
                    <span class="editor-tab-label">{{ ideActiveFile }}</span>
                    <div class="editor-top-actions">
                      <el-button size="small" :icon="Search" circle @click="editorFindStub" />
                      <el-button size="small" :icon="Grid" circle @click="toggleEditorTall" />
                      <el-button size="small" :icon="FullScreen" circle @click="toggleEditorTall" />
                    </div>
                  </div>
                  <CodeMirror5Python
                    v-model="ideContent"
                    :height="editorPaneHeight"
                    :read-only="previewReadOnly || ideActiveFile === 'task.json'"
                  />
                </div>
              </div>
            </template>

            <template v-else-if="sourceSubTab === 'last_build'">
              <div class="last-build-apify">
                <div class="lb-head-row">
                  <div class="lb-head-left">
                    <h2 class="lb-title">
                      构建 {{ displayBuildSemver }}
                      <el-tag v-if="isDisplayBuildLatest" type="info" effect="plain" size="small" class="lb-latest-badge">
                        最新
                      </el-tag>
                    </h2>
                    <button
                      type="button"
                      class="lb-actor-link"
                      :disabled="!displayBuildVersion"
                      @click="displayBuildVersion && openVersionInSource(displayBuildVersion)"
                    >
                      {{ task?.name || "我的任务" }}
                    </button>
                  </div>
                  <div class="lb-head-right">
                    <el-dropdown trigger="click">
                      <el-button>
                        API
                        <el-icon class="el-icon--right">
                          <ArrowDown />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-item>REST 文档（即将提供）</el-dropdown-item>
                      </template>
                    </el-dropdown>
                    <el-button type="danger" plain @click="deleteVersionStub">
                      删除
                    </el-button>
                  </div>
                </div>

                <div class="lb-status-row">
                  <el-tag type="success" effect="light" class="lb-pill-tag">
                    <el-icon><CircleCheck /></el-icon> 成功
                  </el-tag>
                  <el-tag type="primary" effect="light" class="lb-pill-tag">
                    网页
                  </el-tag>
                  <span class="lb-meta-chip">—</span>
                  <span class="lb-meta-chip">$ —</span>
                  <span class="lb-meta-chip">{{ formatBuildDateTime(displayBuildVersion?.created_at) }}</span>
                  <button type="button" class="lb-more-link" @click="lastBuildMoreDetailsStub">
                    更多详情 &gt;
                  </button>
                </div>

                <div class="lb-subtabs">
                  <button
                    type="button"
                    class="lb-subtab"
                    :class="{ active: lastBuildDetailTab === 'log' }"
                    @click="lastBuildDetailTab = 'log'"
                  >
                    日志
                  </button>
                  <button
                    type="button"
                    class="lb-subtab lb-subtab-with-badge"
                    :class="{ active: lastBuildDetailTab === 'packages' }"
                    @click="lastBuildDetailTab = 'packages'"
                  >
                    依赖版本
                    <span class="lb-alpha">内测</span>
                  </button>
                </div>

                <template v-if="lastBuildDetailTab === 'log'">
                  <div class="lb-log-chrome">
                    <div class="lb-log-toolbar">
                      <el-button link type="primary" class="lb-log-link" @click="lastBuildViewFullLogStub">
                        查看完整日志
                      </el-button>
                      <div class="lb-log-icons">
                        <el-button :icon="CopyDocument" circle size="small" @click="copyBuildLogToClipboard" />
                        <el-button :icon="FullScreen" circle size="small" @click="toggleBuildLogExpanded" />
                      </div>
                    </div>
                    <pre
                      class="lb-log-terminal"
                      :class="{ 'is-expanded': buildLogPanelExpanded }"
                    >{{ syntheticBuildLog }}</pre>
                  </div>
                </template>

                <template v-else>
                  <div class="lb-panel-pad lb-packages-wrap">
                    <p class="lb-packages-hint">
                      构建 {{ displayBuildSemver }} 锁定的依赖：
                    </p>
                    <pre class="lb-req-pre">{{ displayBuildVersion?.requirements_txt?.trim() || "（空）" }}</pre>
                    <el-button
                      v-if="displayBuildVersion"
                      link
                      type="primary"
                      class="mt-2"
                      @click="openVersionInSource(displayBuildVersion)"
                    >
                      在代码中打开此版本
                    </el-button>
                  </div>
                </template>

                <p v-if="versions.length > 1" class="lb-all-builds-hint">
                  <el-button link type="primary" @click="activeTab = 'builds'">
                    查看全部 {{ versions.length }} 个构建
                  </el-button>
                  （在「构建记录」中）。
                </p>
              </div>
            </template>

            <template v-else-if="sourceSubTab === 'input'">
              <div class="actor-input-panel">
                <div class="actor-input-view-toggle">
                  <button
                    type="button"
                    class="actor-view-pill"
                    :class="{ active: inputViewMode === 'form' }"
                    @click="inputViewMode = 'form'"
                  >
                    表单
                  </button>
                  <button
                    type="button"
                    class="actor-view-pill"
                    :class="{ active: inputViewMode === 'json' }"
                    @click="inputViewMode = 'json'"
                  >
                    JSON
                  </button>
                </div>

                <template v-if="inputViewMode === 'form'">
                  <div class="actor-input-field-head">
                    <span class="actor-input-label">
                      起始 URL（必填）
                    </span>
                    <el-tooltip content="运行将首先打开这些 URL。" placement="top">
                      <el-icon class="actor-input-info">
                        <InfoFilled />
                      </el-icon>
                    </el-tooltip>
                  </div>
                  <div v-for="(url, idx) in actorStartUrls" :key="`start-url-${idx}`" class="actor-url-row">
                    <el-input v-model="actorStartUrls[idx]" class="actor-url-input" placeholder="https://example.com/" />
                    <el-button class="actor-url-advanced" @click="actorInputAdvancedStub">
                      <el-icon><Document /></el-icon>
                      高级
                    </el-button>
                    <el-button class="actor-url-remove" :icon="Close" circle @click="removeActorStartUrlRow(idx)" />
                  </div>
                  <div class="actor-input-toolbar">
                    <el-dropdown trigger="click" @command="(c: string | number | object) => (c === 'url' ? addActorStartUrlRow() : actorInputAddMenuStub())">
                      <el-button type="primary" class="actor-btn-add">
                        <el-icon><Plus /></el-icon>
                        添加
                        <el-icon class="el-icon--right">
                          <ArrowDown />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-item command="url">
                          添加起始 URL
                        </el-dropdown-item>
                      </template>
                    </el-dropdown>
                    <el-button @click="actorInputBulkEdit">
                      批量编辑
                    </el-button>
                    <el-dropdown trigger="click" @command="actorInputTextFileStub">
                      <el-button>
                        文本文件
                        <el-icon class="el-icon--right">
                          <ArrowDown />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-item command="import">
                          导入…
                        </el-dropdown-item>
                      </template>
                    </el-dropdown>
                  </div>

                  <button type="button" class="actor-run-options-bar" @click="runOptionsPanelOpen = !runOptionsPanelOpen">
                    <el-icon class="actor-ro-chev">
                      <ArrowDown v-if="runOptionsPanelOpen" />
                      <ArrowRight v-else />
                    </el-icon>
                    <span class="actor-ro-title">运行选项</span>
                    <div class="actor-ro-summary">
                      <span><span class="ro-k">构建</span> <span class="ro-v">{{ lastBuildLabel }}</span></span>
                      <span><span class="ro-k">超时</span> <span class="ro-v">3600 秒</span></span>
                      <span><span class="ro-k">内存</span> <span class="ro-v">1 GB</span></span>
                    </div>
                  </button>
                  <div v-show="runOptionsPanelOpen" class="actor-run-options-body">
                    <div class="run-options-grid actor-run-options-grid">
                      <div><span class="ro-k">构建</span><br><strong>{{ lastBuildLabel }}</strong></div>
                      <div><span class="ro-k">超时</span><br><strong>3600 秒</strong></div>
                      <div><span class="ro-k">内存</span><br><strong>1 GB</strong></div>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <el-input
                    v-model="actorInputJsonText"
                    type="textarea"
                    :rows="16"
                    class="actor-input-json-editor"
                    placeholder="{ &quot;startUrls&quot;: [&quot;https://example.com&quot;] }"
                    spellcheck="false"
                  />
                </template>

                <div class="actor-input-footer-actions">
                  <el-button type="primary" :disabled="!hasUnsavedActorInput" @click="saveActorInput">
                    保存
                  </el-button>
                  <el-dropdown trigger="click" @command="restoreActorInputExample">
                    <el-button>
                      恢复示例输入
                      <el-icon class="el-icon--right">
                        <ArrowDown />
                      </el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-item command="apify">
                        Apify 首页
                      </el-dropdown-item>
                      <el-dropdown-item command="crawlee">
                        Crawlee 文档站
                      </el-dropdown-item>
                    </template>
                  </el-dropdown>
                </div>
                <p class="actor-input-footnote">
                  以上设置适用于从本控制台启动的运行；通过 API 启动时请在请求体中传入输入数据。
                </p>
              </div>
            </template>

            <template v-else>
              <div class="last-run-apify">
                <div class="lr-header-row">
                  <div class="lr-header-left">
                    <span class="lr-run-label">运行</span>
                    <span class="lr-dot" aria-hidden="true" />
                    <span class="lr-actor-name">{{ task?.name || "我的任务" }}</span>
                    <span class="lr-actor-pill">任务</span>
                  </div>
                  <div class="lr-header-right">
                    <el-dropdown trigger="click" @command="lastRunActionsStub">
                      <el-button class="lr-toolbar-btn">
                        操作
                        <el-icon class="el-icon--right">
                          <ArrowDown />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-item command="a">
                          …
                        </el-dropdown-item>
                      </template>
                    </el-dropdown>
                    <el-dropdown trigger="click">
                      <el-button class="lr-toolbar-btn">
                        API
                        <el-icon class="el-icon--right">
                          <ArrowDown />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-item>REST 文档（即将提供）</el-dropdown-item>
                      </template>
                    </el-dropdown>
                    <el-button class="lr-toolbar-btn" :icon="Share">
                      分享
                    </el-button>
                    <el-button type="primary" class="lr-export-btn" @click="lastRunExportStub">
                      导出
                    </el-button>
                  </div>
                </div>

                <div
                  class="lr-status-banner"
                  :class="{
                    'lr-status--success': lastRunBannerKind === 'success',
                    'lr-status--failure': lastRunBannerKind === 'failure',
                    'lr-status--running': lastRunBannerKind === 'running',
                    'lr-status--empty': lastRunBannerKind === 'empty',
                    'lr-status--idle': lastRunBannerKind === 'idle',
                  }"
                >
                  <el-icon v-if="lastRunBannerKind === 'success'" class="lr-banner-icon">
                    <CircleCheck />
                  </el-icon>
                  <span class="lr-banner-lead">{{ lastRunBannerLead }}</span>
                  <span class="lr-banner-detail">{{ lastRunBannerDetail }}</span>
                  <span class="lr-banner-gap" />
                  <span class="lr-banner-meta-item lr-banner-cost">—</span>
                  <span class="lr-banner-meta-item">{{ latestRunSummary.startedAt }}</span>
                  <span class="lr-banner-meta-item">{{ latestRunSummary.duration }}</span>
                  <button type="button" class="lr-more-link" @click="lastRunInnerTab = 'log'">
                    更多详情 &gt;
                  </button>
                </div>

                <div class="lr-subtabs" role="tablist">
                  <button
                    type="button"
                    class="lr-subtab"
                    :class="{ active: lastRunInnerTab === 'output' }"
                    role="tab"
                    :aria-selected="lastRunInnerTab === 'output'"
                    @click="lastRunInnerTab = 'output'"
                  >
                    <el-icon class="lr-subtab-icon">
                      <Grid />
                    </el-icon>
                    输出（{{ outputItemCount }}）
                  </button>
                  <button
                    type="button"
                    class="lr-subtab"
                    :class="{ active: lastRunInnerTab === 'log' }"
                    role="tab"
                    :aria-selected="lastRunInnerTab === 'log'"
                    @click="lastRunInnerTab = 'log'"
                  >
                    <el-icon class="lr-subtab-icon">
                      <Document />
                    </el-icon>
                    日志
                  </button>
                  <button
                    type="button"
                    class="lr-subtab"
                    :class="{ active: lastRunInnerTab === 'input' }"
                    role="tab"
                    :aria-selected="lastRunInnerTab === 'input'"
                    @click="lastRunInnerTab = 'input'"
                  >
                    <el-icon class="lr-subtab-icon">
                      <EditPen />
                    </el-icon>
                    输入
                  </button>
                  <button
                    type="button"
                    class="lr-subtab"
                    :class="{ active: lastRunInnerTab === 'storage' }"
                    role="tab"
                    :aria-selected="lastRunInnerTab === 'storage'"
                    @click="lastRunInnerTab = 'storage'"
                  >
                    <el-icon class="lr-subtab-icon">
                      <FolderOpened />
                    </el-icon>
                    存储
                  </button>
                  <button type="button" class="lr-subtab is-disabled" disabled aria-disabled="true">
                    <el-icon class="lr-subtab-icon">
                      <VideoPlay />
                    </el-icon>
                    实时画面
                  </button>
                </div>

                <template v-if="lastRunInnerTab === 'output'">
                  <div class="lr-output-toolbar">
                    <div class="lr-field-pills">
                      <button
                        type="button"
                        class="lr-field-pill"
                        :class="{ active: lastRunFieldsMode === 'overview' }"
                        @click="lastRunFieldsMode = 'overview'"
                      >
                        概览
                      </button>
                      <button
                        type="button"
                        class="lr-field-pill"
                        :class="{ active: lastRunFieldsMode === 'all_fields' }"
                        @click="lastRunFieldsMode = 'all_fields'"
                      >
                        全部字段
                      </button>
                    </div>
                    <div class="lr-output-toolbar-right">
                      <el-button link type="primary" class="lr-preview-link" @click="lastRunPreviewNewTabStub">
                        在新标签页预览
                      </el-button>
                      <div class="lr-view-seg">
                        <button
                          type="button"
                          class="lr-view-seg-btn"
                          :class="{ active: lastRunViewMode === 'table' }"
                          @click="lastRunViewMode = 'table'"
                        >
                          表格
                        </button>
                        <button
                          type="button"
                          class="lr-view-seg-btn"
                          :class="{ active: lastRunViewMode === 'json' }"
                          @click="lastRunViewMode = 'json'"
                        >
                          JSON
                        </button>
                      </div>
                      <el-button class="lr-layout-icon" :icon="Grid" circle @click="lastRunColumnsLayoutStub" />
                    </div>
                  </div>

                  <div v-if="lastRunViewMode === 'table'" class="lr-table-wrap">
                    <el-table
                      :data="lastRunPagedRows"
                      stripe
                      size="small"
                      class="lr-dataset-table"
                      empty-text="数据集中暂无条目"
                    >
                      <el-table-column prop="index" label="#" width="56" />
                      <el-table-column min-width="260">
                        <template #header>
                          <div class="lr-th-stack">
                            <span class="lr-th-main">标题</span>
                            <span class="lr-th-sub">title</span>
                          </div>
                        </template>
                        <template #default="{ row }">
                          <span class="lr-cell-title">{{ row.title }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column min-width="280">
                        <template #header>
                          <div class="lr-th-stack">
                            <span class="lr-th-main">URL</span>
                            <span class="lr-th-sub">url</span>
                          </div>
                        </template>
                        <template #default="{ row }">
                          <a
                            v-if="row.url && row.url !== '—'"
                            :href="row.url"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="lr-cell-url"
                          >{{ row.url }}</a>
                          <span v-else class="lr-cell-muted">—</span>
                        </template>
                      </el-table-column>
                      <el-table-column v-if="lastRunFieldsMode === 'all_fields'" label="H1" prop="h1" width="96" />
                      <el-table-column v-if="lastRunFieldsMode === 'all_fields'" label="H2" prop="h2" width="96" />
                      <el-table-column v-if="lastRunFieldsMode === 'all_fields'" label="H3" prop="h3" width="96" />
                    </el-table>
                  </div>
                  <pre v-else class="lr-json-block">{{ lastRunJsonText || "[]" }}</pre>

                  <div class="lr-table-footer">
                    <div class="lr-footer-left">
                      <span class="lr-footer-label">每页条数：</span>
                      <el-select v-model="lastRunPageSize" size="small" class="lr-page-size-select">
                        <el-option :value="10" label="10" />
                        <el-option :value="25" label="25" />
                        <el-option :value="50" label="50" />
                      </el-select>
                    </div>
                    <div class="lr-footer-right">
                      <span class="lr-footer-label">跳转页：</span>
                      <el-input v-model="lastRunGoToInput" class="lr-go-input" size="small" @keyup.enter="lastRunGoPage" />
                      <el-button size="small" @click="lastRunGoPage">
                        跳转
                      </el-button>
                      <div class="lr-pager">
                        <el-button size="small" :disabled="lastRunPage <= 1" @click="lastRunStepPage(-1)">
                          &lt;
                        </el-button>
                        <span class="lr-page-num">{{ lastRunPage }}</span>
                        <el-button
                          size="small"
                          :disabled="lastRunPage >= lastRunPageTotal"
                          @click="lastRunStepPage(1)"
                        >
                          &gt;
                        </el-button>
                      </div>
                    </div>
                  </div>
                </template>

                <template v-else-if="lastRunInnerTab === 'log'">
                  <pre class="log-panel lr-log-block">{{ logs || "暂无日志输出。" }}</pre>
                </template>

                <template v-else-if="lastRunInnerTab === 'input'">
                  <div class="lr-panel-pad actor-input-readonly-wrap">
                    <div class="actor-input-field-head">
                      <span class="actor-input-label">起始 URL（已保存输入）</span>
                    </div>
                    <ul class="actor-saved-url-list">
                      <li v-for="(u, i) in savedActorStartUrls" :key="`sv-${i}-${u}`">
                        <a v-if="isHttpUrl(u)" :href="u" target="_blank" rel="noopener noreferrer" class="lr-cell-url">{{ u }}</a>
                        <span v-else>{{ u }}</span>
                      </li>
                    </ul>
                    <el-button link type="primary" @click="sourceSubTab = 'input'">
                      在「输入」子页编辑
                    </el-button>
                  </div>
                </template>

                <template v-else-if="lastRunInnerTab === 'storage'">
                  <div class="storage-apify">
                    <p class="storage-intro">
                      默认数据集会随每次运行结束由 Worker 从 Crawlee 的 <code>storage/datasets/default</code> 自动导入控制面数据库并在下方展示；控制台数据库可配置为 MySQL（见平台 <code>DATABASE_URL</code>）。在代码中请使用 <code>Dataset</code> / <code>context.push_data</code> 等写入默认数据集。
                    </p>

                    <div class="storage-inner-tabs" role="tablist">
                      <button
                        type="button"
                        class="storage-inner-tab"
                        :class="{ active: storageInnerTab === 'dataset' }"
                        role="tab"
                        :aria-selected="storageInnerTab === 'dataset'"
                        @click="storageInnerTab = 'dataset'"
                      >
                        数据集
                      </button>
                      <button
                        type="button"
                        class="storage-inner-tab"
                        :class="{ active: storageInnerTab === 'kvs' }"
                        role="tab"
                        :aria-selected="storageInnerTab === 'kvs'"
                        @click="storageInnerTab = 'kvs'"
                      >
                        键值存储
                      </button>
                      <button
                        type="button"
                        class="storage-inner-tab"
                        :class="{ active: storageInnerTab === 'rq' }"
                        role="tab"
                        :aria-selected="storageInnerTab === 'rq'"
                        @click="storageInnerTab = 'rq'"
                      >
                        请求队列
                      </button>
                    </div>

                    <template v-if="storageInnerTab === 'dataset'">
                      <div class="storage-dataset-head">
                        <span class="storage-dataset-title">数据集：默认</span>
                      </div>

                      <div class="storage-stats-grid">
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">名称</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.name }}</span>
                        </div>
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">干净条目</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.cleanItems }}</span>
                        </div>
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">条目数</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.items }}</span>
                        </div>
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">读取</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.reads }}</span>
                        </div>
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">写入</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.writes }}</span>
                        </div>
                        <div class="storage-stat-cell">
                          <span class="storage-stat-label">存储大小</span>
                          <span class="storage-stat-value">{{ storageDatasetStats.sizeLabel }}</span>
                        </div>
                        <div class="storage-stat-cell storage-stat-cell-wide">
                          <span class="storage-stat-label">数据集 ID</span>
                          <span class="storage-dataset-id-row">
                            <code class="storage-dataset-id">{{ storageDatasetIdToken }}</code>
                            <el-button text class="storage-copy-id" @click="storageCopyDatasetId">
                              <el-icon><CopyDocument /></el-icon>
                            </el-button>
                          </span>
                        </div>
                      </div>

                      <div class="storage-export-card">
                        <div class="storage-view-pills">
                          <button
                            type="button"
                            class="storage-view-pill"
                            :class="{ active: storageDatasetListMode === 'overview' }"
                            @click="storageDatasetListMode = 'overview'"
                          >
                            概览
                          </button>
                          <button
                            type="button"
                            class="storage-view-pill"
                            :class="{ active: storageDatasetListMode === 'all_items' }"
                            @click="storageDatasetListMode = 'all_items'"
                          >
                            全部条目
                          </button>
                        </div>

                        <div class="storage-format-label">
                          格式
                        </div>
                        <el-radio-group v-model="storageExportFormat" class="storage-format-radios">
                          <el-radio label="json" size="small">
                            JSON
                          </el-radio>
                          <el-radio label="csv" size="small">
                            CSV
                          </el-radio>
                          <el-radio label="xml" size="small">
                            XML
                          </el-radio>
                          <el-radio label="excel" size="small">
                            Excel
                          </el-radio>
                          <el-radio label="html" size="small">
                            HTML 表格
                          </el-radio>
                          <el-radio label="rss" size="small">
                            RSS
                          </el-radio>
                          <el-radio label="jsonl" size="small">
                            JSONL
                          </el-radio>
                        </el-radio-group>

                        <div class="storage-field-selects">
                          <div class="storage-field-row">
                            <label class="storage-field-label">选择字段（可选）</label>
                            <el-select
                              v-model="storageSelectFields"
                              multiple
                              filterable
                              collapse-tags
                              collapse-tags-tooltip
                              placeholder="包含全部字段"
                              class="storage-field-select"
                              clearable
                            >
                              <el-option
                                v-for="k in storageDatasetFieldKeys"
                                :key="`sf-${k}`"
                                :label="k"
                                :value="k"
                              />
                            </el-select>
                          </div>
                          <div class="storage-field-row">
                            <label class="storage-field-label">排除字段（可选）</label>
                            <el-select
                              v-model="storageOmitFields"
                              multiple
                              filterable
                              collapse-tags
                              collapse-tags-tooltip
                              placeholder="不排除字段"
                              class="storage-field-select"
                              clearable
                            >
                              <el-option
                                v-for="k in storageDatasetFieldKeys"
                                :key="`of-${k}`"
                                :label="k"
                                :value="k"
                              />
                            </el-select>
                          </div>
                        </div>

                        <el-collapse v-model="storageAdvancedActive" class="storage-advanced">
                          <el-collapse-item title="高级选项" name="advanced">
                            <p class="storage-advanced-hint">
                              偏移/限制与服务端导出 API 尚未实现；请使用所选格式进行下载。
                            </p>
                          </el-collapse-item>
                        </el-collapse>

                        <div class="storage-export-actions">
                          <el-button type="primary" class="storage-btn-primary" @click="storageDownloadExport">
                            下载
                          </el-button>
                          <el-button @click="storageViewExportInNewTab">
                            在新标签页查看
                          </el-button>
                          <el-button @click="storagePreviewVisible = true">
                            预览
                          </el-button>
                          <el-button @click="storageCopyShareableLink">
                            复制可分享链接
                          </el-button>
                        </div>

                        <div v-if="storageDatasetListMode === 'all_items' && storagePreviewTableRows.length" class="storage-items-preview">
                          <div class="storage-items-preview-head">
                            预览（前 50 行，导出字段）
                          </div>
                          <el-table :data="storagePreviewTableRows" stripe size="small" class="storage-preview-table">
                            <el-table-column
                              v-for="col in storagePreviewColumns"
                              :key="`pc-${col}`"
                              :label="col"
                              min-width="120"
                              show-overflow-tooltip
                            >
                              <template #default="{ row }">
                                {{ storageRowCell(row, col) }}
                              </template>
                            </el-table-column>
                          </el-table>
                        </div>
                      </div>
                    </template>

                    <template v-else-if="storageInnerTab === 'kvs'">
                      <div class="storage-kvs-page">
                        <div class="storage-kvs-head">
                          <span class="storage-dataset-title">键值存储：默认</span>
                          <el-button type="primary" class="storage-btn-primary" @click="storageDownloadAllKvsZip">
                            下载
                          </el-button>
                        </div>

                        <div class="storage-stats-grid storage-stats-grid--kvs">
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">名称</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.name }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">读取</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.reads }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">写入</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.writes }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">删除</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.deletes }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">列表</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.lists }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">存储大小</span>
                            <span class="storage-stat-value">{{ storageKvsStatsBand.sizeLabel }}</span>
                          </div>
                          <div class="storage-stat-cell storage-stat-cell-wide">
                            <span class="storage-stat-label">存储 ID</span>
                            <span class="storage-dataset-id-row">
                              <code class="storage-dataset-id">{{ storageKvsStoreId }}</code>
                              <el-button text class="storage-copy-id" @click="storageCopyKvsStoreId">
                                <el-icon><CopyDocument /></el-icon>
                              </el-button>
                            </span>
                          </div>
                        </div>

                        <div class="storage-kvs-table-card">
                          <el-table :data="storageKvsPagedEntries" stripe size="small" class="storage-kvs-table" empty-text="暂无键">
                            <el-table-column prop="key" label="键" min-width="220">
                              <template #default="{ row }">
                                <code class="storage-kvs-key">{{ row.key }}</code>
                              </template>
                            </el-table-column>
                            <el-table-column label="大小" width="100" align="right">
                              <template #default="{ row }">
                                {{ storageFormatBytes(row.size) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="操作" width="200" align="center">
                              <template #default="{ row }">
                                <div class="storage-kvs-actions">
                                  <el-tooltip content="查看" placement="top">
                                    <el-button text @click="storageOpenKvsEntry(row)">
                                      <el-icon><View /></el-icon>
                                    </el-button>
                                  </el-tooltip>
                                  <el-tooltip content="复制链接" placement="top">
                                    <el-button text @click="storageCopyKvsItemLink(row)">
                                      <el-icon><LinkIcon /></el-icon>
                                    </el-button>
                                  </el-tooltip>
                                  <el-tooltip content="下载" placement="top">
                                    <el-button text @click="storageDownloadKvsEntry(row)">
                                      <el-icon><Download /></el-icon>
                                    </el-button>
                                  </el-tooltip>
                                  <el-tooltip content="删除" placement="top">
                                    <el-button text type="danger" @click="storageDeleteKvsStub(row)">
                                      <el-icon><Delete /></el-icon>
                                    </el-button>
                                  </el-tooltip>
                                </div>
                              </template>
                            </el-table-column>
                          </el-table>
                        </div>

                        <div class="storage-kvs-footer">
                          <el-button :icon="Refresh" @click="storageRefreshStorageData">
                            刷新
                          </el-button>
                          <div class="storage-mini-pager">
                            <el-button size="small" :disabled="storageKvsPage <= 1" @click="storageKvsStepPage(-1)">
                              &lt;
                            </el-button>
                            <span class="storage-mini-pager-label">第 {{ storageKvsPage }} 页</span>
                            <el-button size="small" :disabled="storageKvsPage >= storageKvsPageTotal" @click="storageKvsStepPage(1)">
                              &gt;
                            </el-button>
                          </div>
                        </div>
                      </div>
                    </template>

                    <template v-else-if="storageInnerTab === 'rq'">
                      <div class="storage-rq-page">
                        <div class="storage-rq-head">
                          <span class="storage-dataset-title">请求队列：默认</span>
                        </div>

                        <div class="storage-stats-grid storage-stats-grid--rq">
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">名称</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.name }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">总计</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.total }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">待处理</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.pending }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">已处理</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.handled }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">读取</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.reads }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">写入</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.writes }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">删除</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.deletes }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">头条目读取</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.headItemReads }}</span>
                          </div>
                          <div class="storage-stat-cell">
                            <span class="storage-stat-label">存储大小</span>
                            <span class="storage-stat-value">{{ storageRqStatsBand.sizeLabel }}</span>
                          </div>
                          <div class="storage-stat-cell storage-stat-cell-wide">
                            <span class="storage-stat-label">队列 ID</span>
                            <span class="storage-dataset-id-row">
                              <code class="storage-dataset-id">{{ storageRqQueueId }}</code>
                              <el-button text class="storage-copy-id" @click="storageCopyRqQueueId">
                                <el-icon><CopyDocument /></el-icon>
                              </el-button>
                            </span>
                          </div>
                        </div>

                        <p class="storage-rq-hint">
                          待处理行与已保存的起始 URL 对应；运行成功结束后「已处理」计数会更新。
                        </p>

                        <div class="storage-rq-table-card">
                          <el-table :data="storageRqPagedRows" stripe size="small" class="storage-rq-table" empty-text="暂无请求 — 请在「输入」子页添加起始 URL">
                            <el-table-column prop="id" label="ID" width="168" show-overflow-tooltip />
                            <el-table-column prop="url" label="URL" min-width="280" show-overflow-tooltip>
                              <template #default="{ row }">
                                <a :href="row.url" target="_blank" rel="noopener noreferrer" class="lr-cell-url">{{ row.url }}</a>
                              </template>
                            </el-table-column>
                            <el-table-column prop="method" label="方法" width="88" align="center" />
                            <el-table-column prop="retries" label="重试" width="88" align="center" />
                            <el-table-column prop="uniqueKey" label="唯一键" min-width="200" show-overflow-tooltip />
                          </el-table>
                        </div>

                        <div class="storage-kvs-footer">
                          <el-button :icon="Refresh" @click="storageRefreshStorageData">
                            刷新
                          </el-button>
                          <div class="storage-rq-footer-pager">
                            <span class="storage-footer-label">每页条数：</span>
                            <el-select v-model="storageRqPageSize" size="small" class="storage-rq-page-size">
                              <el-option :value="25" label="25" />
                              <el-option :value="50" label="50" />
                              <el-option :value="100" label="100" />
                            </el-select>
                            <div class="storage-mini-pager">
                              <el-button size="small" :disabled="storageRqPage <= 1" @click="storageRqStepPage(-1)">
                                &lt;
                              </el-button>
                              <span class="storage-mini-pager-label">第 {{ storageRqPage }} 页</span>
                              <el-button size="small" :disabled="storageRqPage >= storageRqPageTotal" @click="storageRqStepPage(1)">
                                &gt;
                              </el-button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </template>
                  </div>

                  <el-dialog v-model="storagePreviewVisible" title="数据集预览" width="720px" destroy-on-close>
                    <pre class="storage-preview-pre">{{ storagePreviewSampleText }}</pre>
                    <template #footer>
                      <el-button @click="storagePreviewVisible = false">
                        关闭
                      </el-button>
                    </template>
                  </el-dialog>

                  <el-dialog v-model="storageKvsViewVisible" :title="`键：${storageKvsViewKey}`" width="720px" destroy-on-close>
                    <pre class="storage-preview-pre">{{ storageKvsViewContent }}</pre>
                    <template #footer>
                      <el-button @click="storageKvsViewVisible = false">
                        关闭
                      </el-button>
                      <el-button type="primary" @click="storageDownloadKvsViewing">
                        下载
                      </el-button>
                    </template>
                  </el-dialog>
                </template>
              </div>
            </template>
          </div>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'information'" :gutter="16">
        <el-col :xs="24" :lg="16">
          <el-card shadow="never">
            <template #header>
              <span class="card-title">任务信息</span>
            </template>
            <div class="info-grid">
              <div class="info-item">
                <div class="info-label">
                  任务名称
                </div>
                <div class="info-value">
                  {{ task?.name || "-" }}
                </div>
              </div>
              <div class="info-item">
                <div class="info-label">
                  任务 ID
                </div>
                <div class="info-value">
                  {{ task?.id || "-" }}
                </div>
              </div>
              <div class="info-item">
                <div class="info-label">
                  默认运行版本
                </div>
                <div class="info-value">
                  {{ task?.production_version_id || "未设置" }}
                </div>
              </div>
              <div class="info-item">
                <div class="info-label">
                  最后更新时间
                </div>
                <div class="info-value">
                  {{ task?.updated_at || "-" }}
                </div>
              </div>
            </div>
            <div class="mt-3">
              <div class="info-label">
                说明
              </div>
              <div class="desc-box">
                {{ task?.description?.trim() || "暂无说明" }}
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'runs'" :gutter="0" class="runs-tab-row">
        <el-col :span="24">
          <div class="runs-apify-page">
            <div class="runs-toolbar">
              <el-input
                v-model="runsSearchQuery"
                class="runs-search-input"
                placeholder="按运行 ID 搜索"
                clearable
                :prefix-icon="Search"
              />
              <span class="runs-count-label">最近 {{ runsFilteredSorted.length }} 次运行</span>
            </div>

            <div class="runs-table-card">
              <el-table
                :data="runsPagedList"
                class="runs-data-table"
                size="small"
                border
                empty-text="暂无运行记录"
                @row-dblclick="onRunTableRowDblclick"
              >
                <el-table-column type="selection" width="48" />
                <el-table-column min-width="240">
                  <template #header>
                    <span class="runs-th-with-filter">
                      状态
                      <el-button link class="runs-filter-ico" @click="runsColumnFilterStub">
                        <el-icon><Filter /></el-icon>
                      </el-button>
                    </span>
                  </template>
                  <template #default="{ row }">
                    <div class="runs-status-cell">
                      <el-icon v-if="row.status === 'succeeded'" class="runs-status-ok">
                        <CircleCheck />
                      </el-icon>
                      <span class="runs-status-text">{{ runStatusDescription(row) }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="任务" min-width="200">
                  <template #default>
                    <div class="runs-task-cell">
                      <span class="runs-task-title">{{ task?.name || "未命名任务" }}（任务）</span>
                      <span class="runs-task-slug">{{ actorSlug }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="结果" width="100" align="center">
                  <template #default="{ row }">
                    <el-button link type="primary" class="runs-results-link" @click="openRunDetailInConsole(row)">
                      查看
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column label="用量" width="88" align="right">
                  <template #default>
                    <span class="runs-usage">$ —</span>
                  </template>
                </el-table-column>
                <el-table-column label="开始时间" width="168">
                  <template #header>
                    <span class="runs-th-sort">开始 <span class="runs-sort-caret">▼</span></span>
                  </template>
                  <template #default="{ row }">
                    {{ formatRunTableTs(row.started_at || row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="结束时间" width="168">
                  <template #default="{ row }">
                    {{ formatRunTableTs(row.finished_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="耗时" width="72">
                  <template #default="{ row }">
                    {{ runTableDuration(row) }}
                  </template>
                </el-table-column>
                <el-table-column label="构建" width="88">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="openRunBuildFromRow(row)">
                      {{ runSemverFromVersionId(row.version_id) }}
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column min-width="140">
                  <template #header>
                    <span class="runs-th-with-filter">
                      来源
                      <el-button link class="runs-filter-ico" @click="runsColumnFilterStub">
                        <el-icon><Filter /></el-icon>
                      </el-button>
                    </span>
                  </template>
                  <template #default="{ row }">
                    <div class="runs-origin-badges">
                      <el-tag size="small" effect="plain" type="info">
                        {{ row.kind === "production" ? "生产" : "开发" }}
                      </el-tag>
                      <el-tag size="small" effect="plain">
                        网页
                      </el-tag>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="内存" width="72" align="right">
                  <template #default>
                    <span>1 GB</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div class="runs-table-footer">
              <div class="runs-footer-left">
                <span class="runs-footer-label">每页条数：</span>
                <el-select v-model="runsPageSize" size="small" class="runs-page-size-select">
                  <el-option :value="10" label="10" />
                  <el-option :value="20" label="20" />
                  <el-option :value="50" label="50" />
                </el-select>
              </div>
              <div class="runs-footer-right">
                <span class="runs-footer-label">跳转页：</span>
                <el-input v-model="runsGoToPageInput" class="runs-go-input" size="small" @keyup.enter="runsGoPageFromInput" />
                <el-button size="small" @click="runsGoPageFromInput">
                  跳转
                </el-button>
                <div class="runs-pager">
                  <el-button size="small" :disabled="runsPage <= 1" @click="runsStepPage(-1)">
                    &lt;
                  </el-button>
                  <span class="runs-page-num">{{ runsPage }}</span>
                  <el-button size="small" :disabled="runsPage >= runsPageTotalComputed" @click="runsStepPage(1)">
                    &gt;
                  </el-button>
                </div>
              </div>
            </div>

            <p class="runs-log-hint">
              双击某行或打开
              <el-button link type="primary" @click="goLastRunSubtabFromHint">
                最近运行
              </el-button>
              查看日志与数据集预览。选中运行的日志面板已合并到此表。
            </p>
          </div>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'builds'" :gutter="0" class="builds-tab-row">
        <el-col :span="24">
          <div class="builds-apify-page">
            <div class="builds-toolbar">
              <el-select
                v-model="selectedVersionId"
                placeholder="选择版本"
                filterable
                size="default"
                class="builds-version-select"
                :disabled="!versions.length"
              >
                <el-option
                  v-for="v in versions"
                  :key="v.id"
                  :label="formatVersionOptionLabel(v)"
                  :value="v.id"
                />
              </el-select>
              <el-button type="primary" class="builds-primary-btn" :disabled="!taskId" @click="triggerBuildFromToolbar">
                <el-icon class="builds-build-icon">
                  <Box />
                </el-icon>
                构建
              </el-button>
              <el-input
                v-model="buildsFilterQuery"
                class="builds-filter-input"
                placeholder="筛选"
                clearable
                :prefix-icon="Search"
              />
              <span class="builds-count-label">{{ buildsFilteredSorted.length }} {{ buildsFilteredSorted.length === 1 ? "项" : "项" }}</span>
            </div>

            <div class="builds-table-card">
              <el-table
                :data="buildsPagedList"
                class="builds-data-table"
                size="small"
                border
                empty-text="暂无构建 — 请在「来源」子页保存代码。"
              >
                <el-table-column type="selection" width="48" />
                <el-table-column width="100">
                  <template #header>
                    <span class="builds-th-sort">编号 <span class="runs-sort-caret">⇅</span></span>
                  </template>
                  <template #default="{ row }">
                    <el-button link type="primary" @click="openBuildRowLastBuild(row)">
                      {{ semverBuild(row.version_number) }}
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column min-width="130">
                  <template #header>
                    <span class="runs-th-with-filter">
                      状态
                      <el-button link class="runs-filter-ico" @click="runsColumnFilterStub">
                        <el-icon><Filter /></el-icon>
                      </el-button>
                    </span>
                  </template>
                  <template #default>
                    <el-tag type="success" effect="light" class="lb-pill-tag">
                      <el-icon><CircleCheck /></el-icon>
                      成功
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="标签" width="100">
                  <template #default="{ row }">
                    <strong v-if="isBuildRowLatest(row)">最新</strong>
                    <span v-else class="muted">—</span>
                  </template>
                </el-table-column>
                <el-table-column width="120">
                  <template #header>
                    <span class="builds-th-sort">开始 <span class="runs-sort-caret active">▼</span></span>
                  </template>
                  <template #default="{ row }">
                    <div class="builds-ts-cell">
                      <span>{{ buildVersionTiming(row).startDate }}</span>
                      <span class="builds-ts-time">{{ buildVersionTiming(row).startTime }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column width="120">
                  <template #header>
                    <span class="builds-th-sort">结束 <span class="runs-sort-caret">⇅</span></span>
                  </template>
                  <template #default="{ row }">
                    <div class="builds-ts-cell">
                      <span>{{ buildVersionTiming(row).endDate }}</span>
                      <span class="builds-ts-time">{{ buildVersionTiming(row).endTime }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="耗时" width="80">
                  <template #default="{ row }">
                    {{ buildVersionTiming(row).duration }}
                  </template>
                </el-table-column>
                <el-table-column label="镜像大小" width="100">
                  <template #default="{ row }">
                    {{ buildVersionResourcePlaceholders(row).imageSize }}
                  </template>
                </el-table-column>
                <el-table-column label="CU" width="88" align="right">
                  <template #default="{ row }">
                    {{ buildVersionResourcePlaceholders(row).cu }}
                  </template>
                </el-table-column>
                <el-table-column width="100">
                  <template #header>
                    <span class="builds-th-sort">来源 <span class="runs-sort-caret">⇅</span></span>
                  </template>
                  <template #default>
                    <el-tag size="small" effect="plain" class="builds-origin-tag">
                      网页
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div class="runs-table-footer builds-table-footer">
              <div class="runs-footer-left">
                <span class="runs-footer-label">每页条数：</span>
                <el-select v-model="buildsPageSize" size="small" class="runs-page-size-select">
                  <el-option :value="10" label="10" />
                  <el-option :value="20" label="20" />
                  <el-option :value="50" label="50" />
                </el-select>
              </div>
              <div class="runs-footer-right">
                <span class="runs-footer-label">跳转页：</span>
                <el-input v-model="buildsGoToPageInput" class="runs-go-input" size="small" :disabled="buildsPageTotalComputed <= 1" @keyup.enter="buildsGoPageFromInput" />
                <el-button size="small" :disabled="buildsPageTotalComputed <= 1" @click="buildsGoPageFromInput">
                  跳转
                </el-button>
                <div class="runs-pager">
                  <el-button size="small" :disabled="buildsPage <= 1" @click="buildsStepPage(-1)">
                    &lt;
                  </el-button>
                  <span class="runs-page-num">{{ buildsPage }}</span>
                  <el-button size="small" :disabled="buildsPage >= buildsPageTotalComputed" @click="buildsStepPage(1)">
                    &gt;
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'monitoring'" :gutter="16" class="monitoring-tab-row">
        <el-col :span="24">
          <el-row :gutter="12" class="monitoring-overview-strip">
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="never" class="monitoring-mini-card">
                <div class="stat-label">
                  Worker 心跳
                </div>
                <div class="stat-value-main">
                  {{ overview?.worker_heartbeat_at ? overview.worker_heartbeat_at.slice(0, 19) : "无" }}
                </div>
                <el-tag v-if="overview?.worker_stale" type="warning" size="small" class="mt-2">
                  可能离线
                </el-tag>
                <el-tag v-else type="success" size="small" class="mt-2">
                  正常
                </el-tag>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="never" class="monitoring-mini-card">
                <div class="stat-label">
                  全局排队 / 运行中
                </div>
                <div class="stat-value-main">
                  {{ overview?.queued_runs ?? "—" }} / {{ overview?.running_runs ?? "—" }}
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="never" class="monitoring-mini-card">
                <div class="stat-label">
                  本任务：成功 / 失败
                </div>
                <div class="stat-value-main">
                  {{ taskRunStats.succeeded }} / {{ taskRunStats.failed }}
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="12" :lg="6">
              <el-card shadow="never" class="monitoring-mini-card">
                <div class="stat-label">
                  全局近期成功率
                </div>
                <div class="stat-value-main">
                  {{ overview ? `${Math.round(overview.recent_success_ratio * 100)}%` : "—" }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <div class="monitoring-card-grid">
            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <div class="monitoring-card-head">
                  <span class="monitoring-card-title">结果</span>
                </div>
              </template>
              <p class="monitoring-card-sub">
                成功完成运行的耗时统计（最近最多 100 次运行；单条输出条数请在「运行记录」中查看）。
              </p>
              <el-table
                :data="monitoringStatsTableRows(monitoringSucceededDurationStats, 's')"
                size="small"
                border
                class="monitoring-stat-table"
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值" />
              </el-table>
              <MonitoringChart :option="monitoringSucceededLineOption" height="200px" class="monitoring-chart-wrap" />
              <p class="monitoring-table-caption">
                趋势明细（最近 25 次）
              </p>
              <el-table :data="monitoringTrendRows" size="small" border stripe max-height="240">
                <el-table-column prop="time" label="结束/开始时间" min-width="160" />
                <el-table-column prop="durationSec" label="耗时 (秒)" width="100" align="right" />
                <el-table-column prop="status" label="状态" width="120" />
              </el-table>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card monitoring-card-alerts">
              <template #header>
                <div class="monitoring-card-head monitoring-card-head--split">
                  <span class="monitoring-card-title">告警</span>
                  <el-button size="small" type="primary" plain @click="monitoringNewAlertStub">
                    新建告警
                  </el-button>
                </div>
              </template>
              <el-empty description="当代运行过久、结果过少或异常时提醒你（即将支持）">
                <template #image>
                  <el-icon class="monitoring-alert-ico" :size="48">
                    <Bell />
                  </el-icon>
                </template>
              </el-empty>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <div class="monitoring-card-head monitoring-card-head--split">
                  <span class="monitoring-card-title">运行状态</span>
                  <el-button-group size="small">
                    <el-button
                      :type="monitoringRunStatusGranularity === 'daily' ? 'primary' : 'default'"
                      @click="monitoringRunStatusGranularity = 'daily'"
                    >
                      按日
                    </el-button>
                    <el-button
                      :type="monitoringRunStatusGranularity === 'monthly' ? 'primary' : 'default'"
                      @click="monitoringRunStatusGranularity = 'monthly'"
                    >
                      按月
                    </el-button>
                  </el-button-group>
                </div>
              </template>
              <p class="monitoring-card-sub">
                包含本任务已保存运行记录中的各状态数量。
              </p>
              <MonitoringChart :option="monitoringStatusBarOption" height="240px" class="monitoring-chart-wrap" />
              <el-table :data="monitoringStatusGroups" size="small" border stripe max-height="280">
                <el-table-column prop="period" :label="monitoringRunStatusGranularity === 'monthly' ? '月份' : '日期'" width="120" />
                <el-table-column prop="ok" label="成功" width="72" align="right" />
                <el-table-column prop="fail" label="失败" width="72" align="right" />
                <el-table-column prop="run" label="运行中" width="80" align="right" />
                <el-table-column prop="queued" label="排队" width="72" align="right" />
                <el-table-column prop="other" label="其他" width="72" align="right" />
                <el-table-column prop="total" label="合计" width="72" align="right" />
              </el-table>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <span class="monitoring-card-title">耗时</span>
              </template>
              <p class="monitoring-card-sub">
                最近最多 100 次运行的 wall 时间（秒）。
              </p>
              <el-table
                :data="monitoringStatsTableRows(monitoringDurationStats, 's')"
                size="small"
                border
                class="monitoring-stat-table"
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值" />
              </el-table>
              <MonitoringChart :option="monitoringAllDurationLineOption" height="200px" class="monitoring-chart-wrap" />
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <span class="monitoring-card-title">用量（费用）</span>
              </template>
              <p class="monitoring-card-sub">
                计费指标尚未接入；以下为占位。
              </p>
              <el-table
                :data="[
                  { metric: 'Average', value: '—' },
                  { metric: 'Minimum', value: '—' },
                  { metric: 'Maximum', value: '—' },
                  { metric: 'Median', value: '—' },
                ]"
                size="small"
                border
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值 (USD)" />
              </el-table>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <span class="monitoring-card-title">数据集字段数</span>
              </template>
              <p class="monitoring-card-sub">
                按运行聚合的字段数尚未由平台汇总；占位表。
              </p>
              <el-table
                :data="[
                  { metric: 'Average', value: '—' },
                  { metric: 'Minimum', value: '—' },
                  { metric: 'Maximum', value: '—' },
                  { metric: 'Median', value: '—' },
                ]"
                size="small"
                border
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值" />
              </el-table>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <span class="monitoring-card-title">Key-value 存储大小</span>
              </template>
              <p class="monitoring-card-sub">
                运行侧 KVS 体积（占位）。
              </p>
              <el-table
                :data="[
                  { metric: 'Average', value: '—' },
                  { metric: 'Minimum', value: '—' },
                  { metric: 'Maximum', value: '—' },
                  { metric: 'Median', value: '—' },
                ]"
                size="small"
                border
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值" />
              </el-table>
            </el-card>

            <el-card shadow="never" class="monitoring-metric-card">
              <template #header>
                <span class="monitoring-card-title">请求数</span>
              </template>
              <p class="monitoring-card-sub">
                与「结果」相同的耗时样本上的统计（Crawlee 请求数指标待接入）。
              </p>
              <el-table
                :data="monitoringStatsTableRows(monitoringSucceededDurationStats, 's')"
                size="small"
                border
              >
                <el-table-column prop="metric" label="指标" width="120" />
                <el-table-column prop="value" label="值（占位：秒）" />
              </el-table>
            </el-card>
          </div>

          <el-card shadow="never" class="monitoring-other-card">
            <template #header>
              <span class="monitoring-card-title">其他指标</span>
            </template>
            <el-tabs v-model="monitoringOtherMetricTab" class="monitoring-other-tabs">
              <el-tab-pane label="算力单元" name="cpu">
                <p class="monitoring-card-sub">
                  由运行耗时推导的示例 CPU 曲线（%），待 Worker 上报真实指标。
                </p>
              </el-tab-pane>
              <el-tab-pane label="最大内存" name="memory">
                <p class="monitoring-card-sub">
                  占位示例曲线（MB），待接入。
                </p>
              </el-tab-pane>
              <el-tab-pane label="数据集条目" name="dataset_items">
                <p class="monitoring-card-sub">
                  占位示例曲线（条），待接入。
                </p>
              </el-tab-pane>
              <el-tab-pane label="数据集读取" name="dataset_reads">
                <p class="monitoring-card-sub">
                  占位示例曲线（次），待接入。
                </p>
              </el-tab-pane>
            </el-tabs>
            <MonitoringChart :option="monitoringOtherTabChartOption" height="280px" class="monitoring-chart-wrap monitoring-other-chart" />
            <el-table
              :data="monitoringStatsTableRows(monitoringDurationStats, 's')"
              size="small"
              border
              class="mt-2"
            >
              <el-table-column prop="metric" label="指标" width="120" />
              <el-table-column prop="value" label="运行耗时汇总（秒，与上方曲线同源占位）" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'settings'" :gutter="16" class="settings-tab-row">
        <el-col :xs="24" :lg="18">
          <div class="settings-apify-page">
            <section class="settings-apify-section">
              <h2 class="settings-apify-h2">
                任务信息
              </h2>
              <p class="settings-apify-lead">
                任务名称、说明与运行结束后的 Webhook 通知地址。
              </p>
              <el-form label-position="top" class="settings-apify-form">
                <el-form-item label="任务名称">
                  <el-input v-model="editTaskName" />
                </el-form-item>
                <el-form-item label="说明">
                  <el-input v-model="editTaskDescription" type="textarea" :rows="4" />
                </el-form-item>
                <el-form-item label="Webhook（运行结束通知）">
                  <el-input
                    v-model="integrationWebhook"
                    placeholder="https://example.com/your-endpoint"
                    clearable
                  />
                  <p class="settings-apify-hint">
                    写入 task.settings.webhook_url；Worker 可在 run 完成时 POST（当前版本仅持久化）。
                  </p>
                </el-form-item>
              </el-form>
              <el-button
                type="primary"
                :loading="settingsSectionSaving === 'basics'"
                @click="saveTaskBasics"
              >
                保存
              </el-button>
            </section>

            <el-divider class="settings-apify-divider" />

            <section class="settings-apify-section">
              <h2 class="settings-apify-h2">
                选项
              </h2>
              <p class="settings-apify-lead">
                作为本任务、已保存运行与通过 API 启动运行时的默认运行参数（持久化在 task.settings.run_defaults）。
              </p>
              <el-form label-position="top" class="settings-apify-form">
                <el-form-item label="构建版本">
                  <el-select v-model="settingsRunBuild" style="width: 100%; max-width: 360px">
                    <el-option label="latest（当前生产版本）" value="latest" />
                    <el-option
                      v-for="v in versions"
                      :key="v.id"
                      :label="`${semverBuild(v.version_number)}（${v.id.slice(0, 8)}…）`"
                      :value="v.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="超时">
                  <div class="settings-apify-inline">
                    <el-input-number
                      v-model="settingsRunTimeoutSec"
                      :min="1"
                      :max="864000"
                      :disabled="settingsRunNoTimeout"
                      controls-position="right"
                      class="settings-apify-num"
                    />
                    <span class="settings-apify-unit">秒</span>
                    <el-switch
                      v-model="settingsRunNoTimeout"
                      class="settings-apify-switch-right"
                      active-text="无超时限制"
                    />
                  </div>
                </el-form-item>
                <el-form-item label="内存">
                  <el-select v-model="settingsRunMemoryGb" style="width: 100%; max-width: 240px">
                    <el-option :value="0.5" label="0.5 GB" />
                    <el-option :value="1" label="1 GB" />
                    <el-option :value="2" label="2 GB" />
                    <el-option :value="4" label="4 GB" />
                    <el-option :value="8" label="8 GB" />
                  </el-select>
                </el-form-item>
                <el-form-item label="出错时重启（可选）">
                  <el-radio-group v-model="settingsRunRestartOnError">
                    <el-radio-button :value="true">
                      开启
                    </el-radio-button>
                    <el-radio-button :value="false">
                      关闭
                    </el-radio-button>
                  </el-radio-group>
                </el-form-item>
              </el-form>
              <el-button
                type="primary"
                :loading="settingsSectionSaving === 'run_defaults'"
                @click="saveRunDefaultSettings"
              >
                保存
              </el-button>
            </section>

            <el-divider class="settings-apify-divider" />

            <section class="settings-apify-section">
              <h2 class="settings-apify-h2">
                任务权限
              </h2>
              <p class="settings-apify-lead">
                配置任务可访问的用户数据范围（占位枚举，接入后由运行时校验）。
              </p>
              <el-form label-position="top" class="settings-apify-form">
                <el-form-item label="权限级别（可选）">
                  <el-select v-model="settingsActorPermissions" style="width: 100%; max-width: 360px">
                    <el-option label="受限权限" value="limited" />
                    <el-option label="标准" value="standard" />
                    <el-option label="完全（危险）" value="full" />
                  </el-select>
                </el-form-item>
              </el-form>
              <el-button
                type="primary"
                :loading="settingsSectionSaving === 'permissions'"
                @click="savePermissionsSettings"
              >
                保存
              </el-button>
            </section>
          </div>
        </el-col>
      </el-row>

      <el-row v-else-if="activeTab === 'publication'" :gutter="16" class="publication-tab-row">
        <el-col :xs="24" :lg="18">
          <el-card shadow="never" class="publication-flow-card">
            <template #header>
              <span class="card-title">部署流程</span>
            </template>
            <p class="publication-lead">
              使用当前<strong>生产默认版本</strong>的源码：先校验 Crawlee 约定，再按需构建镜像并推送至镜像仓库，最后在目标主机拉取并以容器运行。
            </p>
            <el-timeline class="publication-timeline">
              <el-timeline-item placement="top" :hollow="true" type="primary">
                <p class="publication-timeline-title">
                  校验源码与版本
                </p>
                <p class="publication-timeline-desc">
                  确认已提升（promote）默认版本；<code>main.py</code> 需包含 <code>async def main</code> 与 Crawlee 导入。
                </p>
              </el-timeline-item>
              <el-timeline-item placement="top" :hollow="true" type="primary">
                <p class="publication-timeline-title">
                  构建并推送镜像
                </p>
                <p class="publication-timeline-desc">
                  <template v-if="deployInfo?.docker_deploy_enabled">
                    在 API 服务器上执行 <code>docker build</code>，登录阿里云 ACR 后 <code>docker push</code>；镜像 tag 与版本号关联。
                  </template>
                  <template v-else>
                    当前未启用 Docker 镜像流水线，仅将部署信息写入任务配置（不构建镜像）。
                  </template>
                </p>
              </el-timeline-item>
              <el-timeline-item placement="top" :hollow="true" type="primary">
                <p class="publication-timeline-title">
                  目标机部署
                </p>
                <p class="publication-timeline-desc">
                  <template v-if="deployInfo?.docker_deploy_enabled && !deployInfo?.deploy_skip_ssh">
                    通过 SSH 连接目标机，<code>docker pull</code> 后停止旧容器并以固定容器名重新 <code>docker run</code>。
                  </template>
                  <template v-else-if="deployInfo?.deploy_skip_ssh">
                    已配置跳过 SSH，仅推送镜像仓库。
                  </template>
                  <template v-else>
                    未启用远程 Docker 部署时无此步骤。
                  </template>
                </p>
              </el-timeline-item>
            </el-timeline>
          </el-card>

          <el-card v-if="deployInfo" shadow="never" class="mt-3 publication-target-card">
            <template #header>
              <span class="card-title">目标环境</span>
            </template>
            <el-descriptions :column="1" border size="small" class="publication-descriptions">
              <el-descriptions-item label="镜像仓库（命名空间/仓库）">
                {{ deployInfo.image_repository }}
              </el-descriptions-item>
              <el-descriptions-item label="Docker 镜像流水线">
                {{ deployInfo.docker_deploy_enabled ? "已启用" : "未启用" }}
              </el-descriptions-item>
              <el-descriptions-item label="SSH 目标主机">
                <span class="publication-mono">{{ deployInfo.deploy_ssh_user }}@{{ deployInfo.deploy_ssh_host }}:{{ deployInfo.deploy_ssh_port }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="远程容器名">
                <span class="publication-mono">{{ deployInfo.deploy_container_name }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="跳过 SSH">
                {{ deployInfo.deploy_skip_ssh ? "是（仅推送镜像）" : "否" }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
          <el-skeleton
            v-else-if="deployInfoLoading"
            class="mt-3 publication-target-skeleton"
            animated
            :rows="5"
          />
          <el-alert
            v-else-if="deployInfoError"
            class="mt-3"
            type="warning"
            :closable="false"
            show-icon
            :title="deployInfoError"
          />

          <el-card v-if="deploying || deployResult" shadow="never" class="mt-3 publication-progress-card">
            <template #header>
              <span class="card-title">构建与部署进度</span>
            </template>
            <el-steps
              :active="deployActiveStep"
              finish-status="success"
              :process-status="deployFailed ? 'error' : 'process'"
              align-center
              class="publication-steps"
            >
              <el-step
                title="校验"
                description="校验 Crawlee 入口与导入"
              >
                <template v-if="deploying && deployActiveStep === 0" #icon>
                  <el-icon class="is-loading">
                    <Loading />
                  </el-icon>
                </template>
              </el-step>
              <el-step
                title="构建与推送"
                description="Docker build / push 或写入元数据"
              >
                <template v-if="deploying && deployActiveStep === 1" #icon>
                  <el-icon class="is-loading">
                    <Loading />
                  </el-icon>
                </template>
              </el-step>
              <el-step
                title="远程部署"
                description="SSH 拉取镜像并启动容器"
              >
                <template v-if="deploying && deployActiveStep === 2" #icon>
                  <el-icon class="is-loading">
                    <Loading />
                  </el-icon>
                </template>
              </el-step>
              <el-step
                title="完成"
                description="本次流水线结束"
              />
            </el-steps>
            <p v-if="deploying" class="publication-progress-hint">
              <el-icon class="is-loading publication-progress-hint-ico">
                <Loading />
              </el-icon>
              正在执行部署请求，请稍候（构建镜像可能耗时数分钟）…
            </p>
          </el-card>

          <el-card shadow="never" class="mt-3">
            <template #header>
              <span class="card-title">发布与可见性</span>
            </template>
            <el-alert
              class="mb-3"
              type="info"
              :closable="false"
              show-icon
              title="部署前请确认：已设置默认运行版本；main.py 符合 Crawlee 约定。"
            />
            <el-form label-position="top">
              <el-form-item label="可见性">
                <el-select v-model="publicationVisibility" style="width: 240px">
                  <el-option label="私有（仅本控制台）" value="private" />
                  <el-option label="内部（团队可见，占位）" value="internal" />
                </el-select>
              </el-form-item>
              <el-form-item label="发布说明 / Store 描述（占位）">
                <el-input v-model="publicationNotes" type="textarea" :rows="5" />
              </el-form-item>
              <div class="actions">
                <el-button type="primary" @click="savePublication">
                  保存
                </el-button>
                <el-button type="success" :loading="deploying" @click="deployFromPublication">
                  部署
                </el-button>
              </div>
            </el-form>
            <div v-if="deployResult" class="deploy-result mt-3">
              <div class="deploy-result-line">
                <el-tag type="success" effect="plain">
                  {{ formatDeployStatusLabel(deployResult.status) }}
                </el-tag>
                <span>版本 {{ deployResult.version_id }}</span>
                <span>{{ deployResult.deployed_at }}</span>
              </div>
              <template v-if="deployResult.image_ref">
                <div class="deploy-result-meta">
                  镜像 {{ deployResult.image_ref }}
                </div>
              </template>
              <template v-if="deployResult.remote_host != null && deployResult.remote_host !== ''">
                <div class="deploy-result-meta">
                  目标 {{ deployResult.remote_host }}
                  <template v-if="deployResult.remote_ok != null">
                    — {{ deployResult.remote_ok ? "远程部署成功" : "远程部署失败或未执行" }}
                  </template>
                </div>
              </template>
              <el-input
                v-if="deployResult.detail"
                class="deploy-result-log mt-2"
                type="textarea"
                :rows="6"
                readonly
                :model-value="deployResult.detail"
              />
            </div>
          </el-card>
        </el-col>
      </el-row>

      <footer class="actor-footer-bar">
        <div class="actor-footer-inner">
          <el-dropdown
            split-button
            type="success"
            size="large"
            class="actor-start-split"
            :disabled="!selectedVersionId || !versions.length"
            @click="runKind('debug')"
            @command="startRunFromMenu"
          >
            <el-icon class="start-run-icon">
              <VideoPlay />
            </el-icon>
            启动
            <template #dropdown>
              <el-dropdown-item command="run">
                运行
              </el-dropdown-item>
              <el-dropdown-item command="build">
                构建
              </el-dropdown-item>
              <el-dropdown-item command="clear_build">
                清除构建
              </el-dropdown-item>
              <el-dropdown-item command="build_and_run">
                构建&运行
              </el-dropdown-item>
            </template>
          </el-dropdown>
          <div class="actor-footer-build">
            <template v-if="latestVersion">
              <el-icon class="build-ok-icon">
                <CircleCheck />
              </el-icon>
              <span class="build-label">最近构建：</span>
              <el-tag type="success" effect="plain" size="small">
                成功
              </el-tag>
              <button type="button" class="view-build-link" @click="openLastBuildTab">
                {{ lastBuildLabel }} · 查看构建
              </button>
            </template>
            <span v-else class="build-empty">尚无构建 — 保存代码后即可创建。</span>
          </div>
        </div>
      </footer>
    </div>
  </div>
</template>

<style lang="scss" scoped>
$apify-blue: #0050ff;
$apify-border: #e5e7eb;
$apify-hero-bg: #fff;
$apify-page-bg: #f3f4f6;

/* 固定底栏会盖住正文底部，需预留高度（随底栏换行变高） */
.app-container.actor-console {
  margin: -12px -16px 0;
  padding: 0 0 max(220px, calc(120px + env(safe-area-inset-bottom, 0px)));
  min-height: calc(100vh - 56px);
  background: $apify-page-bg;
  font-weight: 600;
}

/* 部署 Tab 卡片多、按钮在最下，单独再加一档，避免仍被底栏压住 */
.app-container.actor-console.actor-console--publication-tab {
  padding-bottom: max(300px, calc(180px + env(safe-area-inset-bottom, 0px)));
}

.actor-page {
  background: $apify-page-bg;
  font-weight: 600;
}

/* 代码编辑器内保持常规字重，避免影响阅读 */
.app-container.actor-console :deep(.CodeMirror),
.app-container.actor-console :deep(.cm-s-eclipse),
.app-container.actor-console :deep(.CodeMirror pre) {
  font-weight: 400 !important;
}

.app-container.actor-console .actor-slug-code,
.app-container.actor-console :deep(pre.log-panel) {
  font-weight: 400;
}

.actor-hero {
  background: $apify-hero-bg;
  border-bottom: 1px solid $apify-border;
  padding: 16px 24px 12px;
}

.actor-crumb {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: $apify-blue;
  font-size: 14px;
  cursor: pointer;
  padding: 0 0 12px;
}

.actor-hero-main {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.actor-avatar {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: linear-gradient(135deg, #7c3aed 0%, #2563eb 55%, #06b6d4 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.actor-hero-center {
  flex: 1;
  min-width: 200px;
}

.actor-title-line {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.actor-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #111827;
}

.actor-privacy-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
}

.actor-slug-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.actor-slug-code {
  font-size: 13px;
  color: #6b7280;
  background: #f9fafb;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid $apify-border;
}

.actor-desc-placeholder {
  margin-top: 10px;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 14px;
  color: #9ca3af;
  cursor: pointer;
  text-align: left;
}

.actor-desc-placeholder:hover {
  color: $apify-blue;
}

.actor-hero-actions {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.actor-main-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 24px;
  background: $apify-hero-bg;
  border-bottom: 1px solid $apify-border;
  overflow-x: auto;
}

.actor-tab {
  border: none;
  background: transparent;
  padding: 12px 14px 10px;
  font-size: 14px;
  color: #6b7280;
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
}

.actor-tab:hover {
  color: #111827;
}

.actor-tab.active {
  color: $apify-blue;
  font-weight: 600;
  border-bottom-color: $apify-blue;
}

.actor-tab-count {
  font-size: 12px;
  margin-left: 4px;
  color: #9ca3af;
}

.actor-tab.active .actor-tab-count {
  color: #64748b;
}

.actor-source-row {
  padding: 0 24px;
}

.actor-source-shell {
  background: #fff;
  border: 1px solid $apify-border;
  border-radius: 8px;
  margin-top: 16px;
  margin-bottom: 16px;
  padding: 16px 16px 20px;
}

.source-version-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.version-toolbar-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.version-select {
  width: 260px;
}

.source-subtabs-shell {
  background: #f3f4f6;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 14px;
}

.source-subtabs-inner {
  display: inline-flex;
  gap: 4px;
  flex-wrap: wrap;
}

.source-subtab-pill {
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  background: transparent;
  cursor: pointer;
}

.source-subtab-pill:hover {
  color: #111827;
}

.source-subtab-pill.active {
  background: #fff;
  color: #111827;
  font-weight: 700;
  box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
  border-bottom: 2px solid #111827;
  border-radius: 6px 6px 0 0;
  margin-bottom: -2px;
  padding-bottom: 6px;
}

.source-type-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.source-type-label {
  font-size: 13px;
  color: #6b7280;
}

.source-type-select {
  width: 168px;
}

.source-meta-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 4px 0 14px;
  flex-wrap: wrap;
}

.source-meta-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.autosave-label {
  font-size: 12px;
  color: #6b7280;
}

.ide-panel.apify-ide {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 0;
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  min-height: 420px;
  background: #fff;
}

.ide-tree-col {
  border-right: 1px solid $apify-border;
  background: #fafafa;
  padding: 8px 0 12px;
}

.ide-tree-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 8px 8px;
  border-bottom: 1px solid #eee;
  margin-bottom: 6px;
  align-items: center;
}

.ide-storage-pill {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-left: 4px;
}

.ide-editor-col {
  display: flex;
  flex-direction: column;
  background: #fff;
  min-width: 0;
}

.editor-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid $apify-border;
  background: #fafafa;
}

.editor-tab-label {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
}

.editor-top-actions {
  display: inline-flex;
  gap: 4px;
}

.tree-title {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 12px 6px;
}

.tree-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: 4px;
  padding: 5px 8px 5px 6px;
  cursor: pointer;
  font-size: 13px;
  color: #374151;
}

.tree-item:hover {
  background: rgb(0 80 255 / 6%);
}

.tree-item.active {
  background: #e5e7eb;
  font-weight: 600;
}

.tree-item.folder {
  font-weight: 600;
}

.tree-item.depth-1 {
  padding-left: 22px;
}

.tree-chev {
  width: 14px;
  flex-shrink: 0;
  font-size: 10px;
  color: #9ca3af;
}

.tree-chev-spacer {
  display: inline-block;
  width: 14px;
}

.tree-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actor-footer-bar {
  position: fixed;
  left: var(--v3-sidebar-width, 0);
  right: 0;
  bottom: 0;
  z-index: 100;
  background: #fff;
  border-top: 1px solid $apify-border;
  box-shadow: 0 -4px 12px rgb(0 0 0 / 4%);
}

.actor-footer-inner {
  max-width: 100%;
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.actor-start-split :deep(.el-button--success) {
  font-weight: 600;
  background: #23a64a;
  border-color: #23a64a;
  color: #111;
}

.actor-start-split :deep(.el-button--success:hover),
.actor-start-split :deep(.el-button--success:focus-visible) {
  background: #1f9542;
  border-color: #1f9542;
  color: #111;
}

.start-run-icon {
  margin-right: 6px;
  font-size: 16px;
}

.actor-footer-build {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #4b5563;
}

.build-ok-icon {
  color: #16a34a;
  font-size: 18px;
}

.view-build-link {
  border: none;
  background: none;
  padding: 0;
  color: $apify-blue;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.view-build-link:hover {
  text-decoration: underline;
}

.build-empty {
  font-size: 13px;
  color: #9ca3af;
}

.actor-inner-table {
  border-radius: 8px;
}

.set-default-link {
  font-size: 13px;
}

.debug-run-wrap {
  display: inline-block;
}

.mb-3 {
  margin-bottom: 16px;
}

.ml-2 {
  margin-left: 8px;
}

.mt-2 {
  margin-top: 8px;
}

.mt-3 {
  margin-top: 16px;
}

.card-title {
  font-weight: 600;
}

.label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.input-form-wrap {
  max-width: 640px;
}

.builds-tab-row {
  padding: 0 24px;
}

.builds-apify-page {
  padding: 8px 0 24px;
  font-weight: 600;
}

.builds-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.builds-version-select {
  width: 220px;
}

.builds-primary-btn {
  font-weight: 600;
}

.builds-build-icon {
  margin-right: 6px;
  font-size: 16px;
}

.builds-filter-input {
  max-width: 280px;
  flex: 1;
  min-width: 160px;
}

.builds-count-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin-left: auto;
}

.builds-table-card {
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.builds-data-table {
  font-weight: 600;
}

.app-container.actor-console .builds-data-table :deep(.cell) {
  font-weight: 600;
}

.builds-th-sort {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 700;
}

.builds-ts-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.25;
}

.builds-ts-time {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
}

.builds-origin-tag {
  font-weight: 600;
  border-color: #d1d5db !important;
  color: #374151 !important;
}

.runs-sort-caret.active {
  color: $apify-blue;
}

.builds-table-footer {
  padding-top: 12px;
}

.runs-tab-row {
  padding: 0 24px;
}

.runs-apify-page {
  padding: 8px 0 24px;
  font-weight: 600;
}

.runs-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.runs-search-input {
  max-width: 360px;
  flex: 1;
  min-width: 200px;
}

.runs-count-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin-left: auto;
}

.runs-table-card {
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.runs-data-table {
  font-weight: 600;
}

.app-container.actor-console .runs-data-table :deep(.cell) {
  font-weight: 600;
}

.runs-th-with-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.runs-filter-ico {
  padding: 0 !important;
  min-height: auto !important;
  color: #9ca3af !important;
}

.runs-th-sort {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 700;
}

.runs-sort-caret {
  font-size: 10px;
  color: #9ca3af;
}

.runs-status-cell {
  display: inline-flex;
  align-items: flex-start;
  gap: 6px;
}

.runs-status-ok {
  color: #16a34a;
  font-size: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.runs-status-text {
  font-size: 13px;
  line-height: 1.35;
  color: #374151;
}

.runs-task-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.runs-task-title {
  font-weight: 700;
  color: #111827;
}

.runs-task-slug {
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
}

.runs-results-link {
  font-weight: 600;
}

.runs-usage {
  color: #374151;
}

.runs-origin-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.runs-table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 0 0;
}

.runs-footer-left,
.runs-footer-right {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.runs-footer-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.runs-page-size-select {
  width: 88px;
}

.runs-go-input {
  width: 52px;
}

.runs-go-input :deep(.el-input__inner) {
  text-align: center;
}

.runs-pager {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
}

.runs-page-num {
  min-width: 24px;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
}

.runs-log-hint {
  margin: 14px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  max-width: 720px;
  line-height: 1.45;
}

.last-build-apify {
  padding: 4px 0 12px;
  font-weight: 600;
}

.lb-head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.lb-head-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lb-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lb-latest-badge {
  font-weight: 600;
  text-transform: lowercase;
}

.lb-actor-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: $apify-blue;
  cursor: pointer;
  text-align: left;
}

.lb-actor-link:hover:not(:disabled) {
  text-decoration: underline;
}

.lb-actor-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.lb-head-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.lb-status-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  padding: 10px 0 14px;
  border-bottom: 1px solid $apify-border;
  margin-bottom: 12px;
}

.lb-pill-tag {
  font-weight: 600;
  border-radius: 6px;
}

.lb-meta-chip {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.lb-more-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: $apify-blue;
  cursor: pointer;
  margin-left: auto;
}

.lb-more-link:hover {
  text-decoration: underline;
}

.lb-subtabs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid $apify-border;
  margin-bottom: 0;
}

.lb-subtab {
  border: none;
  background: transparent;
  padding: 10px 14px 12px 0;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.lb-subtab:hover {
  color: #111827;
}

.lb-subtab.active {
  color: #111827;
  border-bottom-color: #111827;
}

.lb-alpha {
  font-size: 10px;
  font-weight: 700;
  text-transform: lowercase;
  color: #fff;
  background: $apify-blue;
  padding: 2px 6px;
  border-radius: 4px;
}

.lb-log-chrome {
  border: 1px solid #1f2937;
  border-radius: 8px;
  overflow: hidden;
  margin-top: 12px;
  background: #0b0f14;
}

.lb-log-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
}

.lb-log-link {
  font-weight: 600;
}

.lb-log-icons {
  display: inline-flex;
  gap: 6px;
}

.lb-log-terminal {
  margin: 0;
  padding: 12px 14px;
  min-height: 220px;
  max-height: 320px;
  overflow: auto;
  background: #0d1117;
  color: #c9d1d9;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.lb-log-terminal.is-expanded {
  max-height: min(72vh, 720px);
}

.app-container.actor-console .lb-log-toolbar :deep(.el-button) {
  color: #58a6ff;
}

.app-container.actor-console .lb-log-toolbar :deep(.el-button.is-circle) {
  color: #c9d1d9;
  background: #21262d;
  border-color: #30363d;
}

.lb-panel-pad {
  padding: 16px 4px 8px;
}

.lb-muted-p {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.lb-packages-hint {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.lb-req-pre {
  margin: 0;
  padding: 12px;
  background: #f9fafb;
  border: 1px solid $apify-border;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.45;
  white-space: pre-wrap;
  max-height: 280px;
  overflow: auto;
}

.lb-packages-wrap {
  max-width: 720px;
}

.lb-all-builds-hint {
  margin: 16px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
}

.actor-input-panel {
  max-width: 960px;
  padding: 4px 0 16px;
  font-weight: 600;
}

.actor-input-view-toggle {
  display: inline-flex;
  gap: 0;
  margin-bottom: 18px;
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  background: #f9fafb;
}

.actor-view-pill {
  border: none;
  background: transparent;
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
}

.actor-view-pill.active {
  background: #fff;
  color: #111827;
  box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
}

.actor-input-field-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.actor-input-label {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.actor-input-info {
  font-size: 16px;
  color: #9ca3af;
  cursor: help;
}

.actor-url-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.actor-url-input {
  flex: 1;
  min-width: 0;
}

.actor-url-advanced {
  flex-shrink: 0;
  font-weight: 600;
}

.actor-url-remove {
  flex-shrink: 0;
}

.actor-input-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 12px 0 18px;
}

.actor-btn-add {
  font-weight: 600;
}

.actor-run-options-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 16px;
  width: 100%;
  padding: 10px 12px;
  margin: 0 0 0;
  border: 1px solid $apify-border;
  border-radius: 8px;
  background: #fafafa;
  cursor: pointer;
  text-align: left;
  font: inherit;
  font-weight: 600;
  color: #111827;
}

.actor-ro-chev {
  font-size: 14px;
  color: #6b7280;
  flex-shrink: 0;
}

.actor-ro-title {
  flex-shrink: 0;
}

.actor-ro-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  justify-content: flex-end;
}

.ro-k {
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.ro-v {
  color: #111827;
  margin-left: 4px;
}

.actor-run-options-body {
  border: 1px solid $apify-border;
  border-top: none;
  border-radius: 0 0 8px 8px;
  padding: 12px;
  background: #fff;
  margin-top: -6px;
  margin-bottom: 16px;
}

.actor-run-options-grid {
  margin: 0;
}

.actor-input-json-editor {
  margin-bottom: 16px;
}

.app-container.actor-console .actor-input-json-editor :deep(textarea) {
  font-weight: 400;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.45;
}

.actor-input-footer-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.actor-input-footnote {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  line-height: 1.5;
  max-width: 720px;
}

.actor-input-readonly-wrap .actor-saved-url-list {
  margin: 0 0 12px;
  padding-left: 1.2em;
  font-weight: 600;
  color: #374151;
}

.run-options-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  font-size: 12px;
}

.last-run-empty {
  text-align: center;
  padding: 40px 12px;
}

.last-run-apify {
  background: #fff;
  border: 1px solid $apify-border;
  border-radius: 8px;
  overflow: hidden;
  color: #111827;
  font-weight: 600;
}

.lr-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 10px;
  flex-wrap: wrap;
}

.lr-header-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lr-run-label {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.lr-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f97316 0%, #fb923c 45%, #ea580c 100%);
  display: inline-block;
  flex-shrink: 0;
}

.lr-actor-name {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.lr-actor-pill {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 4px;
  padding: 2px 8px;
}

.lr-header-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.lr-toolbar-btn {
  font-weight: 600;
}

.lr-export-btn {
  font-weight: 600;
  background: $apify-blue !important;
  border-color: $apify-blue !important;
  color: #fff !important;
}

.lr-export-btn:hover,
.lr-export-btn:focus-visible {
  filter: brightness(0.95);
  color: #fff !important;
}

.lr-status-banner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 10px 16px;
  border-top: 1px solid #e5e7eb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 13px;
  font-weight: 600;
}

.lr-status--success {
  background: #d1fae5;
  color: #065f46;
}

.lr-status--failure {
  background: #fee2e2;
  color: #991b1b;
}

.lr-status--running {
  background: #fef3c7;
  color: #92400e;
}

.lr-status--empty,
.lr-status--idle {
  background: #f3f4f6;
  color: #4b5563;
}

.lr-banner-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.lr-banner-detail {
  font-weight: 600;
}

.lr-banner-gap {
  flex: 1;
  min-width: 8px;
}

.lr-banner-meta-item {
  font-weight: 600;
}

.lr-more-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: $apify-blue;
  cursor: pointer;
}

.lr-more-link:hover {
  text-decoration: underline;
}

.lr-subtabs {
  display: flex;
  align-items: stretch;
  gap: 4px;
  padding: 0 8px;
  border-bottom: 1px solid #e5e7eb;
  flex-wrap: wrap;
  background: #fff;
}

.lr-subtab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  padding: 10px 12px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.lr-subtab:hover {
  color: #111827;
}

.lr-subtab.active {
  color: #111827;
  background: #f3f4f6;
  border-bottom-color: #111827;
  border-radius: 6px 6px 0 0;
}

.lr-subtab.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.lr-subtab-icon {
  font-size: 16px;
}

.lr-output-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  flex-wrap: wrap;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.lr-field-pills {
  display: inline-flex;
  gap: 8px;
}

.lr-field-pill {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.lr-field-pill.active {
  background: #e5e7eb;
  color: #111827;
  border-color: #d1d5db;
}

.lr-output-toolbar-right {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lr-preview-link {
  font-weight: 600;
}

.lr-view-seg {
  display: inline-flex;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
}

.lr-view-seg-btn {
  border: none;
  background: #fff;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  cursor: pointer;
}

.lr-view-seg-btn.active {
  background: #f3f4f6;
  color: #111827;
}

.lr-layout-icon {
  font-weight: 600;
}

.lr-table-wrap {
  padding: 0;
  background: #fff;
}

.lr-dataset-table {
  font-weight: 600;
}

.app-container.actor-console .last-run-apify :deep(.lr-dataset-table .cell) {
  font-weight: 600;
}

.lr-th-stack {
  display: flex;
  flex-direction: column;
  gap: 0;
  line-height: 1.2;
}

.lr-th-main {
  font-weight: 700;
  color: #111827;
}

.lr-th-sub {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: lowercase;
}

.lr-cell-title {
  font-weight: 600;
  color: #111827;
}

.lr-cell-url {
  font-weight: 600;
  color: $apify-blue;
  text-decoration: none;
  word-break: break-all;
}

.lr-cell-url:hover {
  text-decoration: underline;
}

.lr-cell-muted {
  color: #9ca3af;
  font-weight: 600;
}

.lr-json-block {
  margin: 0;
  padding: 12px 16px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.45;
  max-height: 480px;
  overflow: auto;
  white-space: pre;
}

.lr-table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px 14px;
  flex-wrap: wrap;
  background: #fff;
  border-top: 1px solid #e5e7eb;
}

.lr-footer-left,
.lr-footer-right {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.lr-footer-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.lr-page-size-select {
  width: 88px;
}

.lr-go-input {
  width: 52px;
}

.lr-go-input :deep(.el-input__inner) {
  text-align: center;
}

.lr-pager {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 4px;
}

.lr-page-num {
  min-width: 24px;
  text-align: center;
  font-weight: 600;
  font-size: 13px;
}

.lr-log-block {
  margin: 0;
  border-radius: 0;
  border: none;
  border-bottom: 1px solid #e5e7eb;
  max-height: 520px;
  background: #f9fafb;
  font-weight: 400;
}

.app-container.actor-console .lr-log-block {
  font-weight: 400;
}

.lr-panel-pad {
  padding: 16px;
  background: #fff;
}

.lr-muted-panel {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.storage-apify {
  padding: 0 0 8px;
  font-weight: 600;
  color: #374151;
}

.storage-intro {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.5;
  color: #6b7280;
  font-weight: 600;
}

.storage-inner-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 16px;
}

.storage-inner-tab {
  border: none;
  background: transparent;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 700;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.storage-inner-tab:hover {
  color: #111827;
}

.storage-inner-tab.active {
  color: $apify-blue;
  border-bottom-color: $apify-blue;
}

.storage-dataset-head {
  margin-bottom: 12px;
}

.storage-dataset-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
}

.storage-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px 20px;
  padding: 14px 16px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 20px;
}

.storage-stat-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.storage-stat-cell-wide {
  grid-column: 1 / -1;
}

.storage-stat-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #9ca3af;
}

.storage-stat-value {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  word-break: break-word;
}

.storage-dataset-id-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.storage-dataset-id {
  font-size: 13px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #374151;
  background: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #e5e7eb;
}

.storage-copy-id {
  padding: 4px !important;
  min-height: auto !important;
}

.storage-export-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}

.storage-view-pills {
  display: inline-flex;
  gap: 8px;
  margin-bottom: 16px;
}

.storage-view-pill {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
  padding: 6px 14px;
  border-radius: 999px;
  cursor: pointer;
}

.storage-view-pill.active {
  background: #e5e7eb;
  color: #111827;
  border-color: #d1d5db;
}

.storage-format-label {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  margin-bottom: 8px;
}

.storage-format-radios {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-bottom: 16px;
}

.storage-field-selects {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}

.storage-field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.storage-field-label {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
}

.storage-field-select {
  width: 100%;
  max-width: 480px;
}

.storage-advanced {
  margin-bottom: 16px;
  border: none;
}

.storage-advanced :deep(.el-collapse-item__header) {
  font-size: 13px;
  font-weight: 700;
  color: #374151;
}

.storage-advanced-hint {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  line-height: 1.45;
}

.storage-export-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.storage-btn-primary {
  font-weight: 700;
  background: $apify-blue !important;
  border-color: $apify-blue !important;
}

.storage-items-preview {
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}

.storage-items-preview-head {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  margin-bottom: 10px;
}

.storage-preview-table {
  font-weight: 600;
}

.storage-placeholder {
  border-radius: 8px;
  border: 1px dashed #e5e7eb;
}

.storage-preview-pre {
  margin: 0;
  max-height: 420px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  font-weight: 600;
  white-space: pre-wrap;
  word-break: break-word;
}

.storage-kvs-page,
.storage-rq-page {
  padding-bottom: 8px;
}

.storage-kvs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.storage-rq-head {
  margin-bottom: 14px;
}

.storage-stats-grid--kvs {
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
}

.storage-stats-grid--rq {
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
}

.storage-kvs-table-card,
.storage-rq-table-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
  background: #fff;
}

.storage-kvs-table,
.storage-rq-table {
  font-weight: 600;
}

.storage-kvs-key {
  font-size: 12px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #374151;
}

.storage-kvs-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.storage-kvs-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.storage-mini-pager {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.storage-mini-pager-label {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
  min-width: 72px;
  text-align: center;
}

.storage-rq-hint {
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  line-height: 1.45;
}

.storage-rq-footer-pager {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.storage-footer-label {
  font-size: 12px;
  font-weight: 700;
  color: #6b7280;
}

.storage-rq-page-size {
  width: 88px;
}

.log-panel {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-primary);
  border-radius: 4px;
  max-height: 280px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.version-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 4px;

  &:hover {
    background: var(--el-fill-color-light);
  }

  &.active {
    background: var(--el-color-primary-light-9);
    outline: 1px solid var(--el-color-primary-light-5);
  }
}

.run-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.run-status {
  flex: 1;
  font-size: 13px;
}

.chat-line {
  font-size: 13px;
  margin-bottom: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.apply-box {
  padding: 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 4px;
}

.debug-run-btn {
  font-weight: 600;
  min-width: 120px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.info-item {
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
}

.info-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.info-value {
  font-size: 13px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}

.desc-box {
  margin-top: 6px;
  padding: 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font-size: 14px;
  line-height: 1.55;
  color: var(--el-text-color-primary);
}

.panel-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.muted {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.stat-value-main {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 600;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.snapshot-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
}

.snapshot-title {
  font-weight: 600;
  font-size: 14px;
}

.snapshot-meta {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.snapshot-actions {
  margin-top: 10px;
}

.deploy-result {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.deploy-result-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.deploy-result-meta {
  word-break: break-all;
  line-height: 1.45;
}

.deploy-result-log :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.publication-tab-row {
  align-items: flex-start;
  padding-bottom: 56px;
}

.publication-lead {
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--el-text-color-regular);
}

.publication-timeline {
  padding-left: 4px;
}

.publication-timeline-title {
  margin: 0 0 4px;
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.publication-timeline-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.publication-timeline-desc code {
  font-size: 12px;
  padding: 0 4px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}

.publication-descriptions {
  max-width: 720px;
}

.publication-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  word-break: break-all;
}

.publication-steps {
  margin-bottom: 8px;
}

.publication-progress-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.publication-progress-hint-ico {
  font-size: 16px;
}

.mt-1 {
  margin-top: 4px;
}

.monitoring-tab-row {
  width: 100%;
}

.monitoring-overview-strip {
  margin-bottom: 16px;
}

.monitoring-mini-card {
  height: 100%;
}

.monitoring-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 1024px) {
  .monitoring-card-grid {
    grid-template-columns: 1fr;
  }
}

.monitoring-metric-card {
  min-height: 120px;
}

.monitoring-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

.monitoring-card-title {
  font-weight: 600;
  font-size: 15px;
}

.monitoring-card-sub {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.45;
}

.monitoring-stat-table {
  margin-bottom: 12px;
}

.monitoring-table-caption {
  margin: 8px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.monitoring-card-alerts :deep(.el-empty__description) {
  margin-top: 8px;
}

.monitoring-alert-ico {
  color: var(--el-text-color-placeholder);
}

.monitoring-other-card {
  margin-bottom: 24px;
}

.monitoring-other-tabs :deep(.el-tabs__content) {
  padding-top: 12px;
}

.monitoring-chart-wrap {
  margin: 12px 0;
}

.monitoring-other-chart {
  margin-top: 8px;
}

/* 设置页：Apify 风格分段表单 */
.settings-apify-page {
  max-width: 720px;
  padding: 24px 24px 48px;
  font-weight: 400;
}

.settings-apify-section {
  padding-bottom: 8px;
}

.settings-apify-h2 {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.settings-apify-lead {
  margin: 0 0 20px;
  font-size: 14px;
  line-height: 1.55;
  color: #6b7280;
  max-width: 640px;
}

.settings-apify-form {
  margin-bottom: 4px;
}

.settings-apify-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: #374151;
}

.settings-apify-divider {
  margin: 28px 0;
}

.settings-apify-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-secondary);
}

.settings-apify-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
}

.settings-apify-num {
  flex: 1;
  min-width: 120px;
  max-width: 200px;
}

.settings-apify-unit {
  font-size: 14px;
  color: var(--el-text-color-regular);
  flex-shrink: 0;
}

.settings-apify-switch-right {
  margin-left: auto;
  flex-shrink: 0;
}

.settings-apify-section .el-button {
  margin-top: 8px;
}
</style>
