import { ComparatorByOptionsComputer } from '../../utils/compare/default-comparator-by-options-computer.js'
import { SortModulesSortingNode, SortModulesOptions } from './types.js'
export declare function buildComparatorByOptionsComputer({
  ignoreEslintDisabledNodes,
  sortingNodes,
}: {
  sortingNodes: SortModulesSortingNode[]
  ignoreEslintDisabledNodes: boolean
}): ComparatorByOptionsComputer<
  Required<SortModulesOptions[number]>,
  SortModulesSortingNode
>
