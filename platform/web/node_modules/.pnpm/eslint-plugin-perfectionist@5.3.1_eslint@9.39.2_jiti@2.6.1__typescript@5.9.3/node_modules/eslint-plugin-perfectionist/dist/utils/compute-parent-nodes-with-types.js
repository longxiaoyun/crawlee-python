function computeParentNodesWithTypes({ allowedTypes, node }) {
  let allowedTypesSet = new Set(allowedTypes)
  let returnValue = []
  let { parent } = node
  while (parent) {
    if (allowedTypesSet.has(parent.type)) {
      returnValue.push(parent)
    }
    ;({ parent } = parent)
  }
  return returnValue
}
export { computeParentNodesWithTypes }
