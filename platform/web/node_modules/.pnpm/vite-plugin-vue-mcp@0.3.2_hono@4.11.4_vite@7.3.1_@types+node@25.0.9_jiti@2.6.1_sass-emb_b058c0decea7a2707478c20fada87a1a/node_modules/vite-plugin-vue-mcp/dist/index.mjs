import { existsSync } from 'node:fs';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import c from 'ansis';
import { join } from 'pathe';
import { searchForWorkspaceRoot, normalizePath } from 'vite';
import { createRPCServer } from 'vite-dev-rpc';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import DEBUG from 'debug';
import { createHooks } from 'hookable';

const debug = DEBUG("vite:mcp:server");
async function setupRoutes(base, server, vite) {
  const transports = /* @__PURE__ */ new Map();
  vite.middlewares.use(`${base}/sse`, async (req, res) => {
    const transport = new SSEServerTransport(`${base}/messages`, res);
    transports.set(transport.sessionId, transport);
    debug("SSE Connected %s", transport.sessionId);
    res.on("close", () => {
      transports.delete(transport.sessionId);
    });
    await server.connect(transport);
  });
  vite.middlewares.use(`${base}/messages`, async (req, res) => {
    if (req.method !== "POST") {
      res.statusCode = 405;
      res.end("Method Not Allowed");
      return;
    }
    const query = new URLSearchParams(req.url?.split("?").pop() || "");
    const clientId = query.get("sessionId");
    if (!clientId || typeof clientId !== "string") {
      res.statusCode = 400;
      res.end("Bad Request");
      return;
    }
    const transport = transports.get(clientId);
    if (!transport) {
      res.statusCode = 404;
      res.end("Not Found");
      return;
    }
    debug("Message from %s", clientId);
    await transport.handlePostMessage(req, res);
  });
}

function createVueMcpContext() {
  return {
    hooks: createHooks(),
    rpc: null,
    rpcServer: null
  };
}

function createServerRpc(ctx) {
  return {
    // component tree
    getInspectorTree: (_) => ({}),
    onInspectorTreeUpdated: (event, data) => {
      ctx.hooks.callHook(event, data);
    },
    // component state
    getInspectorState: (_) => ({}),
    onInspectorStateUpdated: (event, data) => {
      ctx.hooks.callHook(event, data);
    },
    // router info
    getRouterInfo: (_) => ({}),
    onRouterInfoUpdated: (event, data) => {
      ctx.hooks.callHook(event, data);
    },
    // pinia tree
    getPiniaTree: (_) => ({}),
    onPiniaTreeUpdated: (event, data) => {
      ctx.hooks.callHook(event, data);
    },
    // pinia state
    getPiniaState: (_) => ({}),
    onPiniaInfoUpdated: (event, data) => {
      ctx.hooks.callHook(event, data);
    }
  };
}

function getVueMcpPath() {
  const pluginPath = normalizePath(path.dirname(fileURLToPath(import.meta.url)));
  return pluginPath.replace(/\/dist$/, "//src");
}
const vueMcpResourceSymbol = "?__vue-mcp-resource";
function VueMcp(options = {}) {
  const {
    mcpPath = "/__mcp",
    updateCursorMcpJson = true,
    printUrl = true,
    mcpServer = (vite, ctx2) => import('./chunks/server.mjs').then((m) => m.createMcpServerDefault(options, vite, ctx2))
  } = options;
  const cursorMcpOptions = typeof updateCursorMcpJson == "boolean" ? { enabled: updateCursorMcpJson } : updateCursorMcpJson;
  let config;
  const vueMcpPath = getVueMcpPath();
  const vueMcpOptionsImportee = "virtual:vue-mcp-options";
  const resolvedVueMcpOptions = `\0${vueMcpOptionsImportee}`;
  const ctx = createVueMcpContext();
  return {
    name: "vite-plugin-mcp",
    enforce: "pre",
    apply: "serve",
    async configureServer(vite) {
      const rpc = createServerRpc(ctx);
      const rpcServer = createRPCServer(
        "vite-plugin-vue-mcp",
        vite.ws,
        rpc,
        {
          timeout: -1
        }
      );
      ctx.rpcServer = rpcServer;
      ctx.rpc = rpc;
      let mcp = await mcpServer(vite, ctx);
      mcp = await options.mcpServerSetup?.(mcp, vite) || mcp;
      await setupRoutes(mcpPath, mcp, vite);
      const port = vite.config.server.port || 5173;
      const root = searchForWorkspaceRoot(vite.config.root);
      const sseUrl = `http://${options.host || "localhost"}:${port}${mcpPath}/sse`;
      if (cursorMcpOptions.enabled) {
        if (existsSync(join(root, ".cursor"))) {
          const mcp2 = existsSync(join(root, ".cursor/mcp.json")) ? JSON.parse(await fs.readFile(join(root, ".cursor/mcp.json"), "utf-8") || "{}") : {};
          mcp2.mcpServers ||= {};
          mcp2.mcpServers[cursorMcpOptions.serverName || "vue-mcp"] = { url: sseUrl };
          await fs.writeFile(join(root, ".cursor/mcp.json"), `${JSON.stringify(mcp2, null, 2)}
`);
        }
      }
      if (printUrl) {
        setTimeout(() => {
          console.log(`${c.yellow.bold`  ➜  MCP:     `}Server is running at ${sseUrl}`);
        }, 300);
      }
    },
    async resolveId(importee) {
      if (importee === vueMcpOptionsImportee) {
        return resolvedVueMcpOptions;
      } else if (importee.startsWith("virtual:vue-mcp-path:")) {
        const resolved = importee.replace("virtual:vue-mcp-path:", `${vueMcpPath}/`);
        return `${resolved}${vueMcpResourceSymbol}`;
      }
    },
    configResolved(resolvedConfig) {
      config = resolvedConfig;
    },
    transform(code, id, _options) {
      if (_options?.ssr)
        return;
      const appendTo = options.appendTo;
      const [filename] = id.split("?", 2);
      if (appendTo && (typeof appendTo === "string" && filename.endsWith(appendTo) || appendTo instanceof RegExp && appendTo.test(filename))) {
        code = `import 'virtual:vue-mcp-path:overlay.js';
${code}`;
      }
      return code;
    },
    transformIndexHtml(html) {
      if (options.appendTo)
        return;
      return {
        html,
        tags: [
          {
            tag: "script",
            injectTo: "head-prepend",
            attrs: {
              type: "module",
              src: `${config.base || "/"}@id/virtual:vue-mcp-path:overlay.js`
            }
          }
        ]
      };
    }
  };
}

export { VueMcp };
