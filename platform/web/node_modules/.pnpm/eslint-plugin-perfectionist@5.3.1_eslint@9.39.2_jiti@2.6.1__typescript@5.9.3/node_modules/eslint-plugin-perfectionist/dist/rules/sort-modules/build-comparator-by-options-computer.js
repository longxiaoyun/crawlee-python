import { defaultComparatorByOptionsComputer } from '../../utils/compare/default-comparator-by-options-computer.js'
import { sortNodesByDependencies } from '../../utils/sort-nodes-by-dependencies.js'
import { computeOrderedValue } from '../../utils/compare/compute-ordered-value.js'
import { UnreachableCaseError } from '../../utils/unreachable-case-error.js'
import { computeDependencies } from './compute-dependencies.js'
function buildComparatorByOptionsComputer({
  ignoreEslintDisabledNodes,
  sortingNodes,
}) {
  return options => {
    switch (options.type) {
      /* v8 ignore next -- @preserve Untested for now as not a relevant sort for this rule. */
      case 'subgroup-order':
      case 'alphabetical':
      case 'line-length':
      case 'unsorted':
      case 'natural':
      case 'custom':
        return defaultComparatorByOptionsComputer({
          ...options,
          type: options.type,
        })
      case 'usage':
        return buildUsageComparator({
          ignoreEslintDisabledNodes,
          sortingNodes,
          options,
        })
      /* v8 ignore next 2 -- @preserve Exhaustive guard. */
      default:
        throw new UnreachableCaseError(options.type)
    }
  }
}
function buildUsageComparator({
  ignoreEslintDisabledNodes,
  sortingNodes,
  options,
}) {
  let orderByNode = buildOrderByNodeMap()
  return (a, b) => {
    let nodeA = a.node
    let nodeB = b.node
    let orderA = orderByNode.get(nodeA)
    let orderB = orderByNode.get(nodeB)
    return computeOrderedValue(orderA - orderB, options.order)
  }
  function buildOrderByNodeMap() {
    let sortingNodesWithUpdatedDependencies = sortingNodes.map(
      ({ isEslintDisabled, dependencyNames, node }) => ({
        dependencies: computeDependencies(node, { type: 'soft' }),
        isEslintDisabled,
        dependencyNames,
        node,
      }),
    )
    let sortedSortingNodes = sortNodesByDependencies(
      sortingNodesWithUpdatedDependencies,
      { ignoreEslintDisabledNodes },
    )
    let orderByNodeMap = /* @__PURE__ */ new Map()
    for (let [i, { node }] of sortedSortingNodes.entries()) {
      orderByNodeMap.set(node, i)
    }
    return orderByNodeMap
  }
}
export { buildComparatorByOptionsComputer }
