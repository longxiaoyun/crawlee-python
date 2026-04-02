import { TSESTree } from '@typescript-eslint/types'
import { TSESLint } from '@typescript-eslint/utils'
/**
 * Computes the dependency names of an import-like AST node.
 *
 * @param props - The parameters object.
 * @param props.sourceCode - ESLint source code object for text extraction.
 * @param props.node - The AST node representing an import-like declaration.
 * @returns The names of the dependencies.
 */
export declare function computeDependencyNames({
  sourceCode,
  node,
}: {
  node:
    | TSESTree.TSImportEqualsDeclaration
    | TSESTree.VariableDeclaration
    | TSESTree.ImportDeclaration
  sourceCode: TSESLint.SourceCode
}): string[]
