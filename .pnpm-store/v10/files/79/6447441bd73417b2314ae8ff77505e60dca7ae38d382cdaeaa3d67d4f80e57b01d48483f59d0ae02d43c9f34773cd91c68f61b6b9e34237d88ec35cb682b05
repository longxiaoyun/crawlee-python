import { TSESTree } from '@typescript-eslint/types'
import { TSESLint } from '@typescript-eslint/utils'
/**
 * Computes the name of an import-like AST node.
 *
 * @param props - The parameters object.
 * @param props.sourceCode - ESLint source code object for text extraction.
 * @param props.node - The AST node representing an import-like declaration.
 * @returns The name of the import.
 */
export declare function computeNodeName({
  sourceCode,
  node,
}: {
  node:
    | TSESTree.TSImportEqualsDeclaration
    | TSESTree.VariableDeclaration
    | TSESTree.ImportDeclaration
  sourceCode: TSESLint.SourceCode
}): string
