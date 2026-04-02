<script lang="ts" setup>
import CodeMirror from "codemirror"
import "codemirror/lib/codemirror.css"
import "codemirror/mode/python/python.js"
import "codemirror/theme/eclipse.css"

const props = withDefaults(
  defineProps<{
    modelValue: string
    readOnly?: boolean
    height?: string
  }>(),
  { readOnly: false, height: "380px" }
)

const emit = defineEmits<{
  "update:modelValue": [value: string]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
let editor: CodeMirror.EditorFromTextArea | null = null
const syncingFromEditor = ref(false)

function mountEditor() {
  const ta = textareaRef.value
  if (!ta || editor) return

  editor = CodeMirror.fromTextArea(ta, {
    mode: "python",
    theme: "eclipse",
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    readOnly: props.readOnly,
    lineWrapping: true
  })
  editor.setValue(props.modelValue)
  editor.setSize("100%", props.height)
  editor.on("change", (cm) => {
    syncingFromEditor.value = true
    emit("update:modelValue", cm.getValue())
    nextTick(() => {
      syncingFromEditor.value = false
    })
  })
}

watch(
  () => props.modelValue,
  (val) => {
    if (!editor || syncingFromEditor.value) return
    const cur = editor.getValue()
    if (cur !== val) editor.setValue(val)
  }
)

watch(
  () => props.readOnly,
  (ro) => {
    editor?.setOption("readOnly", ro)
  }
)

watch(
  () => props.height,
  (h) => {
    editor?.setSize("100%", h)
  }
)

onMounted(() => {
  mountEditor()
})

onUnmounted(() => {
  if (editor) {
    editor.toTextArea()
    editor = null
  }
})
</script>

<template>
  <div class="cm5-wrap">
    <textarea
      ref="textareaRef"
      class="cm5-textarea"
      :readonly="props.readOnly"
    />
  </div>
</template>

<style lang="scss" scoped>
.cm5-wrap {
  width: 100%;
}

.cm5-textarea {
  width: 100%;
  min-height: 120px;
}

/* 高度由 editor.setSize 控制，避免与 CodeMirror 内部布局冲突 */
:deep(.CodeMirror) {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  font-size: 13px;
}
</style>
