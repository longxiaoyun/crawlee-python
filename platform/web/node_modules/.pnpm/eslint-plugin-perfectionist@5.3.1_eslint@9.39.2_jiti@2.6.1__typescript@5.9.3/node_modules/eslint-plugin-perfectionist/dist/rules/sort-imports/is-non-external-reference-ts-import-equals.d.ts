import { TSESTree } from '@typescript-eslint/types'
/**
 * Determines whether the given AST node is a non-external-reference TS import
 * equals declaration.
 *
 * @param node - The AST node representing an import-like declaration.
 * @returns True if the node is a non-external-reference TS import equals
 *   declaration; otherwise, false.
 */
export declare function isNonExternalReferenceTsImportEquals(
  node:
    | TSESTree.TSImportEqualsDeclaration
    | TSESTree.VariableDeclaration
    | TSESTree.ImportDeclaration,
): node is TSESTree.TSImportEqualsDeclaration
