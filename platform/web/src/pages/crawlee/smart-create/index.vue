<script lang="ts" setup>
import {
  createWizardSessionApi,
  fetchWizardMessagesApi,
  fetchWizardSessionMetaApi,
  fetchWizardSessionsApi,
  finalizeWizardApi,
  postWizardMessageApi
} from "@@/apis/crawlee"
import { ArrowLeft, Clock, Position } from "@element-plus/icons-vue"
import { useRouter } from "vue-router"

const router = useRouter()

const WIZARD_SESSION_KEY = "crawlee_wizard_session_id"

const smartEnabled = import.meta.env.VITE_ENABLE_SMART_TASK_CREATE !== "false"

type WizardSessionRow = {
  session_id: string
  status: string
  created_at: string
  updated_at: string
  preview: string
  message_count: number
}

const loading = ref(false)
const sending = ref(false)
const sessionId = ref<string | null>(null)
/** 后端 `active` | `finalized`；未拉取元数据时为 null */
const sessionStatus = ref<string | null>(null)
const input = ref("")
const messages = ref<{ role: string, content: string }[]>([])
const lastDraft = ref<Record<string, unknown> | null>(null)
const previewTab = ref<"code" | "req" | "settings">("code")
const scrollRef = ref<HTMLElement | null>(null)

const historyDrawerVisible = ref(false)
const historyLoading = ref(false)
const historySessions = ref<WizardSessionRow[]>([])

const sessionReadonly = computed(
  () => sessionStatus.value !== null && sessionStatus.value !== "active"
)

/** 与后端 wizard_service.extract_wizard_json 一致：取助手消息中最后一个 ```json``` 块解析为草稿 */
function deriveLastDraftFromMessages(msgs: { role: string, content: string }[]): Record<string, unknown> | null {
  const fence = /```(?:json)?\s*([\s\S]*?)```/gi
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i]!.role !== "assistant") continue
    const text = msgs[i]!.content
    let lastBlock: string | null = null
    let m: RegExpExecArray | null
    fence.lastIndex = 0
    while ((m = fence.exec(text)) !== null) lastBlock = m[1] ?? null
    if (!lastBlock?.trim()) continue
    try {
      const parsed = JSON.parse(lastBlock.trim()) as Record<string, unknown>
      if (parsed && typeof parsed.source_code === "string") return parsed
    } catch {
      /* try older assistant message */
    }
  }
  return null
}

async function refreshSessionMeta(sid: string) {
  try {
    const meta = await fetchWizardSessionMetaApi(sid)
    sessionStatus.value = meta.status
  } catch {
    sessionStatus.value = null
  }
}

/** 助手消息里若含 JSON 代码块，列表中隐藏该段（预览区已展示结构化内容） */
function chatLineDisplay(role: string, content: string) {
  if (role !== "assistant") return content
  const stripped = content.replace(/```(?:json)?\s*[\s\S]*?```/gi, "").trim()
  return stripped.length > 0 ? stripped : content
}

function formatSessionTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    })
  } catch {
    return iso
  }
}

async function bootstrapSession() {
  if (!smartEnabled) return
  loading.value = true
  try {
    const stored = localStorage.getItem(WIZARD_SESSION_KEY)
    if (stored) {
      try {
        const hist = await fetchWizardMessagesApi(stored)
        sessionId.value = stored
        messages.value = hist
        lastDraft.value = deriveLastDraftFromMessages(hist)
        await refreshSessionMeta(stored)
        return
      } catch {
        localStorage.removeItem(WIZARD_SESSION_KEY)
      }
    }
    const { session_id } = await createWizardSessionApi()
    sessionId.value = session_id
    localStorage.setItem(WIZARD_SESSION_KEY, session_id)
    messages.value = []
    lastDraft.value = null
    sessionStatus.value = "active"
  } catch {
    sessionId.value = null
    sessionStatus.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void bootstrapSession()
})

async function openHistoryDrawer() {
  historyDrawerVisible.value = true
  historyLoading.value = true
  try {
    historySessions.value = await fetchWizardSessionsApi(80)
  } finally {
    historyLoading.value = false
  }
}

async function applySession(sid: string) {
  loading.value = true
  try {
    const [hist, meta] = await Promise.all([
      fetchWizardMessagesApi(sid),
      fetchWizardSessionMetaApi(sid)
    ])
    sessionId.value = sid
    messages.value = hist
    lastDraft.value = deriveLastDraftFromMessages(hist)
    sessionStatus.value = meta.status
    localStorage.setItem(WIZARD_SESSION_KEY, sid)
    input.value = ""
    previewTab.value = "code"
    historyDrawerVisible.value = false
  } finally {
    loading.value = false
  }
}

const previewSource = computed(() => (typeof lastDraft.value?.source_code === "string" ? lastDraft.value.source_code : ""))
const previewReq = computed(() => (typeof lastDraft.value?.requirements_txt === "string" ? lastDraft.value.requirements_txt : ""))
const previewSettings = computed(() => {
  const s = lastDraft.value?.settings
  if (s && typeof s === "object") return JSON.stringify(s, null, 2)
  return "{}"
})

function scrollChatToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(messages, () => scrollChatToBottom(), { deep: true })
watch(lastDraft, () => scrollChatToBottom())

function onChatKeydown(evt: Event | KeyboardEvent) {
  const e = evt as KeyboardEvent
  if (e.key !== "Enter") return
  if (e.shiftKey) return
  e.preventDefault()
  void send()
}

async function send() {
  const text = input.value.trim()
  if (!text || !sessionId.value || sending.value || sessionReadonly.value) return
  sending.value = true
  messages.value = [...messages.value, { role: "user", content: text }]
  input.value = ""
  try {
    const { reply, draft } = await postWizardMessageApi(sessionId.value, text)
    messages.value = [...messages.value, { role: "assistant", content: reply }]
    if (draft && typeof draft === "object") lastDraft.value = draft as Record<string, unknown>
  } finally {
    sending.value = false
  }
}

const finalizing = ref(false)

async function confirmCreate() {
  if (sessionReadonly.value) {
    ElMessage.warning("此会话已结束，无法再次提交")
    return
  }
  const d = lastDraft.value
  if (!d || !sessionId.value) {
    ElMessage.warning("请多轮对话直到模型在回复中生成可解析的 JSON 代码块（含 main.py）。")
    return
  }
  const name = typeof d.name === "string" ? d.name : "ai-task"
  const description = typeof d.description === "string" ? d.description : ""
  const source_code = typeof d.source_code === "string" ? d.source_code : ""
  const requirements_txt = typeof d.requirements_txt === "string" ? d.requirements_txt : "crawlee[beautifulsoup]\nbeautifulsoup4\naiomysql\n"
  const settings = typeof d.settings === "object" && d.settings !== null ? (d.settings as Record<string, unknown>) : {}
  if (!source_code.trim()) {
    ElMessage.warning("草稿缺少 source_code")
    return
  }
  finalizing.value = true
  try {
    const { task_id } = await finalizeWizardApi(sessionId.value, {
      name,
      description,
      source_code,
      requirements_txt,
      settings
    })
    localStorage.removeItem(WIZARD_SESSION_KEY)
    ElMessage.success("任务已创建")
    // 与手动创建后进入任务详情一致：默认打开「来源 → 代码」
    router.replace({
      name: "CrawleeTaskDetail",
      params: { taskId: task_id },
      query: { tab: "source", sub: "code" }
    })
  } finally {
    finalizing.value = false
  }
}

function goBack() {
  router.push({ name: "CrawleeTasks" })
}

async function newSession() {
  localStorage.removeItem(WIZARD_SESSION_KEY)
  sessionId.value = null
  messages.value = []
  lastDraft.value = null
  sessionStatus.value = null
  input.value = ""
  await bootstrapSession()
}
</script>

<template>
  <div v-loading="loading" class="smart-create-page">
    <header class="sc-head">
      <el-button :icon="ArrowLeft" text @click="goBack">
        返回任务列表
      </el-button>
      <h1 class="sc-title">
        智能创建任务
      </h1>
      <div class="sc-head-actions">
        <el-button
          v-if="smartEnabled"
          size="small"
          :icon="Clock"
          @click="openHistoryDrawer"
        >
          历史会话
        </el-button>
        <el-button v-if="sessionId" size="small" @click="newSession">
          新会话
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="!smartEnabled"
      type="warning"
      :closable="false"
      title="已关闭智能创建（VITE_ENABLE_SMART_TASK_CREATE=false）"
      class="sc-alert"
    />

    <template v-else-if="!sessionId && !loading">
      <el-alert type="error" :closable="false" title="无法创建向导会话（后端可能关闭了智能创建或网络错误）" class="sc-alert" />
    </template>

    <div v-else class="sc-body">
      <el-alert
        v-if="sessionReadonly"
        type="info"
        :closable="false"
        show-icon
        class="sc-readonly-alert"
        title="此会话已提交任务或已结束，仅可查看历史消息与代码预览，无法继续发送或提交。"
      />
      <div ref="scrollRef" class="ai-conversation" role="log" aria-live="polite">
        <div
          v-for="(m, i) in messages"
          :key="`m-${i}`"
          class="ai-message"
          :class="m.role === 'user' ? 'ai-message--user' : 'ai-message--assistant'"
        >
          <span class="ai-message-role">{{ m.role === "user" ? "你" : "助手" }}</span>
          <pre class="ai-message-body">{{ chatLineDisplay(m.role, m.content) }}</pre>
        </div>

        <div v-if="lastDraft" class="draft-in-chat">
          <div class="draft-in-chat-title">
            代码预览
          </div>
          <p class="draft-in-chat-hint">
            确认无误后点击下方「提交任务」，将进入与手动创建相同的任务详情页（来源 → 代码，可继续编辑 AI 生成的代码）。
          </p>
          <el-tabs v-model="previewTab" class="draft-tabs">
            <el-tab-pane label="main.py" name="code">
              <pre class="draft-pre">{{ previewSource || "（暂无）" }}</pre>
            </el-tab-pane>
            <el-tab-pane label="requirements.txt" name="req">
              <pre class="draft-pre">{{ previewReq || "（暂无）" }}</pre>
            </el-tab-pane>
            <el-tab-pane label="settings" name="settings">
              <pre class="draft-pre">{{ previewSettings }}</pre>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <footer class="sc-footer">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          placeholder="描述目标网站、要抓取的字段、是否需要写入 MySQL 等…（Enter 发送，Shift+Enter 换行）"
          :disabled="sending || !sessionId || sessionReadonly"
          class="sc-input"
          @keydown="onChatKeydown"
        />
        <div class="sc-footer-actions">
          <el-button
            type="primary"
            :icon="Position"
            :loading="sending"
            :disabled="!sessionId || sessionReadonly"
            @click="send"
          >
            发送
          </el-button>
          <el-button
            type="success"
            :loading="finalizing"
            :disabled="!lastDraft || !sessionId || sessionReadonly"
            @click="confirmCreate"
          >
            提交任务
          </el-button>
        </div>
      </footer>
    </div>

    <el-drawer
      v-model="historyDrawerVisible"
      title="会话历史"
      direction="rtl"
      size="min(420px, 92vw)"
      append-to-body
      destroy-on-close
    >
      <div v-loading="historyLoading" class="history-drawer-body">
        <el-empty v-if="!historyLoading && historySessions.length === 0" description="暂无历史会话" />
        <el-scrollbar v-else max-height="calc(100vh - 120px)">
          <button
            v-for="row in historySessions"
            :key="row.session_id"
            type="button"
            class="history-row"
            :class="{ 'history-row--current': row.session_id === sessionId }"
            @click="applySession(row.session_id)"
          >
            <div class="history-row-top">
              <span class="history-preview">{{ row.preview || "（空会话）" }}</span>
              <el-tag v-if="row.status === 'finalized'" size="small" type="success">
                已提交
              </el-tag>
              <el-tag v-else size="small" type="primary">
                进行中
              </el-tag>
            </div>
            <div class="history-row-meta">
              {{ row.message_count }} 条消息 · {{ formatSessionTime(row.updated_at) }}
            </div>
          </button>
        </el-scrollbar>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.smart-create-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  flex: 1;
  min-height: 0;
  padding: 8px 16px 0;
  box-sizing: border-box;
}

.sc-alert {
  flex-shrink: 0;
  margin-bottom: 8px;
}

.sc-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.sc-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  flex: 1;
}

.sc-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.sc-readonly-alert {
  flex-shrink: 0;
  margin-bottom: 8px;
}

.sc-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  margin-top: 8px;
}

.ai-conversation {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.ai-message {
  margin-bottom: 14px;

  &:last-of-type {
    margin-bottom: 8px;
  }
}

.ai-message--user .ai-message-body {
  background: #dbeafe;
}

.ai-message--assistant .ai-message-body {
  background: #fff;
  border: 1px solid var(--el-border-color-extra-light);
}

.ai-message-role {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.ai-message-body {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.5;
}

.draft-in-chat {
  margin-top: 12px;
  padding: 12px;
  background: var(--el-bg-color);
  border: 1px dashed var(--el-color-primary-light-5);
  border-radius: 8px;
}

.draft-in-chat-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-color-primary);
  margin-bottom: 6px;
}

.draft-in-chat-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.draft-tabs :deep(.el-tabs__content) {
  padding-top: 8px;
}

.draft-pre {
  margin: 0;
  max-height: min(42vh, 400px);
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  padding: 12px;
  background: var(--el-fill-color-dark);
  border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.sc-footer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 0 16px;
  margin-top: 8px;
}

.sc-input :deep(.el-textarea__inner) {
  font-family: inherit;
}

.sc-footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.history-drawer-body {
  min-height: 120px;
}

.history-row {
  display: block;
  width: 100%;
  margin: 0 0 10px;
  padding: 10px 12px;
  text-align: left;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;

  &:hover {
    border-color: var(--el-color-primary-light-5);
    background: var(--el-fill-color-light);
  }
}

.history-row--current {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.history-row-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}

.history-preview {
  flex: 1;
  font-size: 13px;
  line-height: 1.4;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

.history-row-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
