import { TSESLint } from '@typescript-eslint/utils'
import { TSESTree } from '@typescript-eslint/types'
/**
 * Determines whether the given AST node is a side-effect import.
 *
 * @param props - The parameters object.
 * @param props.sourceCode - ESLint source code object for text extraction.
 * @param props.node - The AST node representing an import-like declaration.
 * @returns True if the node is a side-effect import; otherwise, false.
 */
export declare function isSideEffectImport({
  sourceCode,
  node,
}: {
  node:
    | TSESTree.TSImportEqualsDeclaration
    | TSESTree.VariableDeclaration
    | TSESTree.ImportDeclaration
  sourceCode: TSESLint.SourceCode
}): boolean
