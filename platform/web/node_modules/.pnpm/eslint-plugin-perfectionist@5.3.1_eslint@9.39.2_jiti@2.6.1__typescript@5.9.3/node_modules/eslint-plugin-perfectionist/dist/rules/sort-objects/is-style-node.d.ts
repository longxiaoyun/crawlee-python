import { TSESTree } from '@typescript-eslint/types'
/**
 * Checks if a node represents a style definition in JSX or styled-components.
 *
 * @param node - The AST node to check.
 * @returns True if the node is a style definition, false otherwise.
 */
export declare function isStyleNode(node: TSESTree.Node): boolean
