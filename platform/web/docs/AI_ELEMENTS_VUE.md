# AI Elements Vue 与控制台

[AI Elements Vue](https://github.com/vuepont/ai-elements-vue) 基于 **shadcn-vue**，需要：

- **Node.js 18+**
- 已执行 `npx shadcn-vue@latest init`
- **Tailwind CSS**（**CSS Variables** 主题模式）
- 项目中已集成 **AI SDK**（若使用其流式示例）

当前 `platform/web` 以 **Element Plus + UnoCSS** 为主，智能创建页使用与官方组件**语义等价**的布局（会话区 / 消息气泡 / 输入区），便于后续在不改业务逻辑的前提下，用 CLI 安装官方组件替换：

```bash
npx ai-elements-vue@latest add conversation message prompt-input
# 或
npx shadcn-vue@latest add https://registry.ai-elements-vue.com/all.json
```

安装后可将 `src/pages/crawlee/smart-create/index.vue` 中的 `.ai-conversation` / `.ai-message` / `.ai-prompt-input` 区块替换为官方组件。

前端开关：**`VITE_ENABLE_SMART_TASK_CREATE`**（默认启用，设为 `false` 关闭「智能创建」按钮与页面能力）。
