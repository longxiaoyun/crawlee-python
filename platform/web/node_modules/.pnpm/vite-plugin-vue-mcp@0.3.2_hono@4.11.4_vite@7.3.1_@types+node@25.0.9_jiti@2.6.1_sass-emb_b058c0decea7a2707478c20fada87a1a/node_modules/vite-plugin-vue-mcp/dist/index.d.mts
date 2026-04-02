import { ViteDevServer, Plugin } from 'vite';
import { Awaitable } from '@antfu/utils';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { Implementation } from '@modelcontextprotocol/sdk/types.js';

interface VueMcpOptions {
    /**
     * The host to listen on, default is `localhost`
     */
    host?: string;
    /**
     * Print the MCP server URL in the console
     *
     * @default true
     */
    printUrl?: boolean;
    /**
     * The MCP server info. Ingored when `mcpServer` is provided
     */
    mcpServerInfo?: Implementation;
    /**
     * Custom MCP server, when this is provided, the built-in MCP tools will be ignored
     */
    mcpServer?: (viteServer: ViteDevServer) => Awaitable<McpServer>;
    /**
     * Setup the MCP server, this is called when the MCP server is created
     * You may also return a new MCP server to replace the default one
     */
    mcpServerSetup?: (server: McpServer, viteServer: ViteDevServer) => Awaitable<void | McpServer>;
    /**
     * The path to the MCP server, default is `/__mcp`
     */
    mcpPath?: string;
    /**
     * Update the address of the MCP server in the cursor config file `.cursor/mcp.json`,
     * if `.cursor` folder exists.
     *
     * @default true
     */
    updateCursorMcpJson?: boolean | {
        enabled: boolean;
        /**
         * The name of the MCP server, default is `vue-mcp`
         */
        serverName?: string;
    };
    /**
     * append an import to the module id ending with `appendTo` instead of adding a script into body
     * useful for projects that do not use html file as an entry
     *
     * WARNING: only set this if you know exactly what it does.
     * @default ''
     */
    appendTo?: string | RegExp;
}

declare function VueMcp(options?: VueMcpOptions): Plugin;

export { VueMcp };
