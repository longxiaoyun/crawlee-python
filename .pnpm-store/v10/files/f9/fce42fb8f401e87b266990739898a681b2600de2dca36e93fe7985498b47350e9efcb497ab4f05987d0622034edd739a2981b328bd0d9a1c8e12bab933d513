import { AST_NODE_TYPES } from '@typescript-eslint/utils'
import { isSortable } from '../../utils/is-sortable.js'
function getOverloadSignatureGroups(members) {
  let methods = members
    .filter(
      member =>
        member.type === AST_NODE_TYPES.MethodDefinition ||
        member.type === AST_NODE_TYPES.TSAbstractMethodDefinition,
    )
    .filter(member => member.kind === 'method')
  let staticOverloadSignaturesByName = /* @__PURE__ */ new Map()
  let overloadSignaturesByName = /* @__PURE__ */ new Map()
  for (let method of methods) {
    if (method.key.type !== AST_NODE_TYPES.Identifier) {
      continue
    }
    let { name } = method.key
    let mapToUse = method.static
      ? staticOverloadSignaturesByName
      : overloadSignaturesByName
    let signatureOverloadsGroup = mapToUse.get(name)
    if (!signatureOverloadsGroup) {
      signatureOverloadsGroup = []
      mapToUse.set(name, signatureOverloadsGroup)
    }
    signatureOverloadsGroup.push(method)
  }
  return [
    ...overloadSignaturesByName.values(),
    ...staticOverloadSignaturesByName.values(),
  ].filter(isSortable)
}
export { getOverloadSignatureGroups }
