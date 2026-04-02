import { AST_NODE_TYPES } from '@typescript-eslint/utils'
function isStyleNode(node) {
  switch (node.type) {
    case AST_NODE_TYPES.JSXExpressionContainer:
      return (
        node.parent.type === AST_NODE_TYPES.JSXAttribute &&
        node.parent.name.name === 'style'
      )
    case AST_NODE_TYPES.CallExpression:
      return (
        isCssCallExpression(node.callee) ||
        (node.callee.type === AST_NODE_TYPES.MemberExpression &&
          isStyledCallExpression(node.callee.object)) ||
        (node.callee.type === AST_NODE_TYPES.CallExpression &&
          isStyledCallExpression(node.callee.callee))
      )
    default:
      return false
  }
}
function isStyledCallExpression(identifier) {
  return (
    identifier.type === AST_NODE_TYPES.Identifier &&
    identifier.name === 'styled'
  )
}
function isCssCallExpression(identifier) {
  return (
    identifier.type === AST_NODE_TYPES.Identifier && identifier.name === 'css'
  )
}
export { isStyleNode }
