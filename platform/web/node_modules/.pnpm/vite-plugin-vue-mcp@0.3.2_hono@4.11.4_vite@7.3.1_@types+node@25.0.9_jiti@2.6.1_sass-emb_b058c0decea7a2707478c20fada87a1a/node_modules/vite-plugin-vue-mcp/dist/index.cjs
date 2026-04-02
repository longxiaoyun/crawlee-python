'use strict';

const node_fs = require('node:fs');
const fs = require('node:fs/promises');
const path = require('node:path');
const node_url = require('node:url');
const c = require('ansis');
const pathe = require('pathe');
const vite = require('vite');
const viteDevRpc = require('vite-dev-rpc');
const sse_js = require('@modelcontextprotocol/sdk/server/sse.js');
const DEBUG = require('debug');
const hookable = require('hookable');

var _documentCurrentScript = typeof document !== 'undefined' ? document.currentScript : null;
function _interopDefaultCompat (e) { return e && typeof e === 'object' && 'default' in e ? e.default : e; }

const fs__default = /*#__PURE__*/_interopDefaultCompat(fs);
const path__default = /*#__PURE__*/_interopDefaultCompat(path);
const c__default = /*#__PURE__*/_interopDefaultCompat(c);
const DEBUG__default = /*#__PURE__*/_interopDefaultCompat(DEBUG);

const debug = DEBUG__default("vite:mcp:server");
async function setupRoutes(base, server, vite) {
  const transports = /* @__PURE__ */ new Map();
  vite.middlewares.use(`${base}/sse`, async (req, res) => {
    const transport = new sse_js.SSEServerTransport(`${base}/messages`, res);
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
    hooks: hookable.createHooks(),
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
  const pluginPath = vite.normalizePath(path__default.dirname(node_url.fileURLToPath((typeof document === 'undefined' ? require('u' + 'rl').pathToFileURL(__filename).href : (_documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === 'SCRIPT' && _documentCurrentScript.src || new URL('index.cjs', document.baseURI).href)))));
  return pluginPath.replace(/\/dist$/, "//src");
}
const vueMcpResourceSymbol = "?__vue-mcp-resource";
function VueMcp(options = {}) {
  const {
    mcpPath = "/__mcp",
    updateCursorMcpJson = true,
    printUrl = true,
    mcpServer = (vite, ctx2) => import('./chunks/server.cjs').then((m) => m.createMcpServerDefault(options, vite, ctx2))
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
    async configureServer(vite$1) {
      const rpc = createServerRpc(ctx);
      const rpcServer = viteDevRpc.createRPCServer(
        "vite-plugin-vue-mcp",
        vite$1.ws,
        rpc,
        {
          timeout: -1
        }
      );
      ctx.rpcServer = rpcServer;
      ctx.rpc = rpc;
      let mcp = await mcpServer(vite$1, ctx);
      mcp = await options.mcpServerSetup?.(mcp, vite$1) || mcp;
      await setupRoutes(mcpPath, mcp, vite$1);
      const port = vite$1.config.server.port || 5173;
      const root = vite.searchForWorkspaceRoot(vite$1.config.root);
      const sseUrl = `http://${options.host || "localhost"}:${port}${mcpPath}/sse`;
      if (cursorMcpOptions.enabled) {
        if (node_fs.existsSync(pathe.join(root, ".cursor"))) {
          const mcp2 = node_fs.existsSync(pathe.join(root, ".cursor/mcp.json")) ? JSON.parse(await fs__default.readFile(pathe.join(root, ".cursor/mcp.json"), "utf-8") || "{}") : {};
          mcp2.mcpServers ||= {};
          mcp2.mcpServers[cursorMcpOptions.serverName || "vue-mcp"] = { url: sseUrl };
          await fs__default.writeFile(pathe.join(root, ".cursor/mcp.json"), `${JSON.stringify(mcp2, null, 2)}
`);
        }
      }
      if (printUrl) {
        setTimeout(() => {
          console.log(`${c__default.yellow.bold`  ➜  MCP:     `}Server is running at ${sseUrl}`);
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

exports.VueMcp = VueMcp;
