import { TSESLint } from '@typescript-eslint/utils'
import { TSESTree } from '@typescript-eslint/types'
export declare function computeSpecifierName({
  sourceCode,
  node,
}: {
  node:
    | TSESTree.TSImportEqualsDeclaration
    | TSESTree.VariableDeclaration
    | TSESTree.ImportDeclaration
  sourceCode: TSESLint.SourceCode
}): string | null
