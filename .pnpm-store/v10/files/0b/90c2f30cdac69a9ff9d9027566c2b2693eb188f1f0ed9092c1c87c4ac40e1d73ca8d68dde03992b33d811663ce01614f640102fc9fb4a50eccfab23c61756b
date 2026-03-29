import { AST_NODE_TYPES } from '@typescript-eslint/utils'
import { TSESTree } from '@typescript-eslint/types'
import { NodeOfType } from '../types/node-of-type.js'
/**
 * Finds all parent nodes matching one of the specified AST node types.
 *
 * @param options - Options for the search.
 * @param options.allowedTypes - Array of AST node types to match.
 * @param options.node - Starting node to search from.
 * @returns List of matching parent nodes.
 */
export declare function computeParentNodesWithTypes<
  NodeType extends AST_NODE_TYPES,
>({
  allowedTypes,
  node,
}: {
  allowedTypes: NodeType[]
  node: TSESTree.Node
}): NodeOfType<NodeType>[]
