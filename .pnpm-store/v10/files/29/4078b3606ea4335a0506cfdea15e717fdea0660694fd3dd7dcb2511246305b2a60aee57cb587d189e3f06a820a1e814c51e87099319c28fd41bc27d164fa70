import { AST_NODE_TYPES } from '@typescript-eslint/utils'
import {
  ORDER_ERROR_ID,
  GROUP_ORDER_ERROR_ID,
  EXTRA_SPACING_ERROR_ID,
  MISSED_SPACING_ERROR_ID,
  DEPENDENCY_ORDER_ERROR_ID,
  additionalCustomGroupMatchOptionsJsonSchema,
  allSelectors,
  allModifiers,
} from './sort-objects/types.js'
import {
  ORDER_ERROR,
  GROUP_ORDER_ERROR,
  EXTRA_SPACING_ERROR,
  MISSED_SPACING_ERROR,
  DEPENDENCY_ORDER_ERROR,
} from '../utils/report-errors.js'
import {
  partitionByNewLineJsonSchema,
  partitionByCommentJsonSchema,
} from '../utils/json-schemas/common-partition-json-schemas.js'
import {
  buildUseConfigurationIfJsonSchema,
  buildCommonJsonSchemas,
} from '../utils/json-schemas/common-json-schemas.js'
import { computePropertyOrVariableDeclaratorName } from './sort-objects/compute-property-or-variable-declarator-name.js'
import { validateNewlinesAndPartitionConfiguration } from '../utils/validate-newlines-and-partition-configuration.js'
import { buildDefaultOptionsByGroupIndexComputer } from '../utils/build-default-options-by-group-index-computer.js'
import { defaultComparatorByOptionsComputer } from '../utils/compare/default-comparator-by-options-computer.js'
import { buildCommonGroupsJsonSchemas } from '../utils/json-schemas/common-groups-json-schemas.js'
import { validateCustomSortConfiguration } from '../utils/validate-custom-sort-configuration.js'
import { computeMatchedContextOptions } from './sort-objects/compute-matched-context-options.js'
import { scopedRegexJsonSchema } from '../utils/json-schemas/scoped-regex-json-schema.js'
import { validateGroupsConfiguration } from '../utils/validate-groups-configuration.js'
import { generatePredefinedGroups } from '../utils/generate-predefined-groups.js'
import { sortNodesByDependencies } from '../utils/sort-nodes-by-dependencies.js'
import { getEslintDisabledLines } from '../utils/get-eslint-disabled-lines.js'
import { isNodeEslintDisabled } from '../utils/is-node-eslint-disabled.js'
import { doesCustomGroupMatch } from '../utils/does-custom-group-match.js'
import { UnreachableCaseError } from '../utils/unreachable-case-error.js'
import { isNodeOnSingleLine } from '../utils/is-node-on-single-line.js'
import { sortNodesByGroups } from '../utils/sort-nodes-by-groups.js'
import { createEslintRule } from '../utils/create-eslint-rule.js'
import { reportAllErrors } from '../utils/report-all-errors.js'
import { shouldPartition } from '../utils/should-partition.js'
import { isStyleNode } from './sort-objects/is-style-node.js'
import { computeGroup } from '../utils/compute-group.js'
import { rangeToDiff } from '../utils/range-to-diff.js'
import { getSettings } from '../utils/get-settings.js'
import { isSortable } from '../utils/is-sortable.js'
import { complete } from '../utils/complete.js'
let cachedGroupsByModifiersAndSelectors = /* @__PURE__ */ new Map()
let defaultOptions = {
  fallbackSort: { type: 'unsorted' },
  newlinesInside: 'newlinesBetween',
  partitionByNewLine: false,
  partitionByComment: false,
  newlinesBetween: 'ignore',
  specialCharacters: 'keep',
  styledComponents: true,
  useConfigurationIf: {},
  type: 'alphabetical',
  ignoreCase: true,
  customGroups: [],
  locales: 'en-US',
  alphabet: '',
  order: 'asc',
  groups: [],
}
const sortObjects = createEslintRule({
  create: context => {
    let settings = getSettings(context.settings)
    let { sourceCode, id } = context
    function sortObject(nodeObject) {
      if (!isSortable(nodeObject.properties)) {
        return
      }
      let isDestructuredObject =
        nodeObject.type === AST_NODE_TYPES.ObjectPattern
      let matchedContextOptions = computeMatchedContextOptions({
        isDestructuredObject,
        nodeObject,
        sourceCode,
        context,
      })
      let options = complete(matchedContextOptions, settings, defaultOptions)
      validateCustomSortConfiguration(options)
      validateGroupsConfiguration({
        selectors: allSelectors,
        modifiers: allModifiers,
        options,
      })
      validateNewlinesAndPartitionConfiguration(options)
      let objectRoot =
        nodeObject.type === AST_NODE_TYPES.ObjectPattern
          ? null
          : getRootObject(nodeObject)
      if (
        objectRoot &&
        !options.styledComponents &&
        (isStyleNode(objectRoot.parent) ||
          (objectRoot.parent.type === AST_NODE_TYPES.ArrowFunctionExpression &&
            isStyleNode(objectRoot.parent.parent)))
      ) {
        return
      }
      let eslintDisabledLines = getEslintDisabledLines({
        ruleName: id,
        sourceCode,
      })
      function extractDependencies(init) {
        let dependencies = []
        function checkNode(nodeValue) {
          if (
            nodeValue.type === AST_NODE_TYPES.ArrowFunctionExpression ||
            nodeValue.type === AST_NODE_TYPES.FunctionExpression
          ) {
            return
          }
          if (nodeValue.type === AST_NODE_TYPES.Identifier) {
            dependencies.push(nodeValue.name)
          }
          if (nodeValue.type === AST_NODE_TYPES.Property) {
            traverseNode(nodeValue.key)
            traverseNode(nodeValue.value)
          }
          if (nodeValue.type === AST_NODE_TYPES.ConditionalExpression) {
            traverseNode(nodeValue.test)
            traverseNode(nodeValue.consequent)
            traverseNode(nodeValue.alternate)
          }
          if (
            'expression' in nodeValue &&
            typeof nodeValue.expression !== 'boolean'
          ) {
            traverseNode(nodeValue.expression)
          }
          if ('object' in nodeValue) {
            traverseNode(nodeValue.object)
          }
          if ('callee' in nodeValue) {
            traverseNode(nodeValue.callee)
          }
          if ('left' in nodeValue) {
            traverseNode(nodeValue.left)
          }
          if ('right' in nodeValue) {
            traverseNode(nodeValue.right)
          }
          if ('elements' in nodeValue) {
            let elements = nodeValue.elements.filter(
              currentNode => currentNode !== null,
            )
            for (let element of elements) {
              traverseNode(element)
            }
          }
          if ('argument' in nodeValue && nodeValue.argument) {
            traverseNode(nodeValue.argument)
          }
          if ('arguments' in nodeValue) {
            for (let argument of nodeValue.arguments) {
              traverseNode(argument)
            }
          }
          if ('properties' in nodeValue) {
            for (let property of nodeValue.properties) {
              traverseNode(property)
            }
          }
          if ('expressions' in nodeValue) {
            for (let nodeExpression of nodeValue.expressions) {
              traverseNode(nodeExpression)
            }
          }
        }
        function traverseNode(nodeValue) {
          checkNode(nodeValue)
        }
        traverseNode(init)
        return dependencies
      }
      function formatProperties(props) {
        return props.reduce(
          (accumulator, property) => {
            if (
              property.type === AST_NODE_TYPES.SpreadElement ||
              property.type === AST_NODE_TYPES.RestElement
            ) {
              accumulator.push([])
              return accumulator
            }
            let lastSortingNode = accumulator.at(-1)?.at(-1)
            let dependencies = []
            let selectors = []
            let modifiers = []
            if (property.value.type === AST_NODE_TYPES.AssignmentPattern) {
              dependencies = extractDependencies(property.value.right)
            }
            if (
              property.value.type === AST_NODE_TYPES.ArrowFunctionExpression ||
              property.value.type === AST_NODE_TYPES.FunctionExpression
            ) {
              selectors.push('method')
            } else {
              selectors.push('property')
            }
            selectors.push('member')
            if (!isNodeOnSingleLine(property)) {
              modifiers.push('multiline')
            }
            let name = computePropertyOrVariableDeclaratorName({
              node: property,
              sourceCode,
            })
            let dependencyNames = [name]
            if (isDestructuredObject) {
              dependencyNames = [
                ...new Set(extractNamesFromPattern(property.value)),
              ]
            }
            let predefinedGroups = generatePredefinedGroups({
              cache: cachedGroupsByModifiersAndSelectors,
              selectors,
              modifiers,
            })
            let group = computeGroup({
              customGroupMatcher: customGroup =>
                doesCustomGroupMatch({
                  elementValue: getNodeValue({
                    sourceCode,
                    property,
                  }),
                  elementName: name,
                  customGroup,
                  selectors,
                  modifiers,
                }),
              predefinedGroups,
              options,
            })
            let sortingNode = {
              isEslintDisabled: isNodeEslintDisabled(
                property,
                eslintDisabledLines,
              ),
              size: rangeToDiff(property, sourceCode),
              dependencyNames,
              node: property,
              dependencies,
              group,
              name,
            }
            if (
              shouldPartition({
                lastSortingNode,
                sortingNode,
                sourceCode,
                options,
              })
            ) {
              accumulator.push([])
            }
            accumulator.at(-1).push({
              ...sortingNode,
              partitionId: accumulator.length,
            })
            return accumulator
          },
          [[]],
        )
      }
      let formattedMembers = formatProperties(nodeObject.properties)
      function sortNodesExcludingEslintDisabled(ignoreEslintDisabledNodes) {
        let nodesSortedByGroups = formattedMembers.flatMap(nodes2 =>
          sortNodesByGroups({
            optionsByGroupIndexComputer:
              buildDefaultOptionsByGroupIndexComputer(options),
            comparatorByOptionsComputer: defaultComparatorByOptionsComputer,
            ignoreEslintDisabledNodes,
            groups: options.groups,
            nodes: nodes2,
          }),
        )
        return sortNodesByDependencies(nodesSortedByGroups, {
          ignoreEslintDisabledNodes,
        })
      }
      let nodes = formattedMembers.flat()
      reportAllErrors({
        availableMessageIds: {
          missedSpacingBetweenMembers: MISSED_SPACING_ERROR_ID,
          unexpectedDependencyOrder: DEPENDENCY_ORDER_ERROR_ID,
          extraSpacingBetweenMembers: EXTRA_SPACING_ERROR_ID,
          unexpectedGroupOrder: GROUP_ORDER_ERROR_ID,
          unexpectedOrder: ORDER_ERROR_ID,
        },
        sortNodesExcludingEslintDisabled,
        options,
        context,
        nodes,
      })
    }
    return {
      ObjectExpression: sortObject,
      ObjectPattern: sortObject,
    }
  },
  meta: {
    schema: {
      items: {
        properties: {
          ...buildCommonJsonSchemas(),
          ...buildCommonGroupsJsonSchemas({
            additionalCustomGroupMatchProperties:
              additionalCustomGroupMatchOptionsJsonSchema,
          }),
          useConfigurationIf: buildUseConfigurationIfJsonSchema({
            additionalProperties: {
              objectType: {
                description:
                  'Specifies whether to only match destructured objects or regular objects.',
                enum: ['destructured', 'non-destructured'],
                type: 'string',
              },
              hasNumericKeysOnly: {
                description:
                  'Specifies whether to only match objects that have exclusively numeric keys.',
                type: 'boolean',
              },
              declarationCommentMatchesPattern: scopedRegexJsonSchema,
              callingFunctionNamePattern: scopedRegexJsonSchema,
              declarationMatchesPattern: scopedRegexJsonSchema,
            },
          }),
          styledComponents: {
            description: 'Controls whether to sort styled components.',
            type: 'boolean',
          },
          partitionByComment: partitionByCommentJsonSchema,
          partitionByNewLine: partitionByNewLineJsonSchema,
        },
        additionalProperties: false,
        type: 'object',
      },
      uniqueItems: true,
      type: 'array',
    },
    messages: {
      [DEPENDENCY_ORDER_ERROR_ID]: DEPENDENCY_ORDER_ERROR,
      [MISSED_SPACING_ERROR_ID]: MISSED_SPACING_ERROR,
      [EXTRA_SPACING_ERROR_ID]: EXTRA_SPACING_ERROR,
      [GROUP_ORDER_ERROR_ID]: GROUP_ORDER_ERROR,
      [ORDER_ERROR_ID]: ORDER_ERROR,
    },
    docs: {
      url: 'https://perfectionist.dev/rules/sort-objects',
      description: 'Enforce sorted objects.',
      recommended: true,
    },
    type: 'suggestion',
    fixable: 'code',
  },
  defaultOptions: [defaultOptions],
  name: 'sort-objects',
})
function extractNamesFromPattern(pattern) {
  switch (pattern.type) {
    case AST_NODE_TYPES.AssignmentPattern:
      return extractNamesFromPattern(pattern.left)
    case AST_NODE_TYPES.ObjectPattern:
      return pattern.properties.flatMap(extractNamesFromObjectPatternProperty)
    case AST_NODE_TYPES.ArrayPattern:
      return pattern.elements.flatMap(extractNamesFromArrayPatternElement)
    case AST_NODE_TYPES.Identifier:
      return [pattern.name]
    /* v8 ignore next 2 */
    default:
      return []
  }
  function extractNamesFromArrayPatternElement(element) {
    if (!element) {
      return []
    }
    if (element.type === AST_NODE_TYPES.RestElement) {
      return extractNamesFromPattern(element.argument)
    }
    return extractNamesFromPattern(element)
  }
  function extractNamesFromObjectPatternProperty(property) {
    switch (property.type) {
      case AST_NODE_TYPES.RestElement:
        return extractNamesFromPattern(property.argument)
      case AST_NODE_TYPES.Property:
        return extractNamesFromPattern(property.value)
      /* v8 ignore next 2 -- @preserve Exhaustive guard. */
      default:
        throw new UnreachableCaseError(property)
    }
  }
}
function getNodeValue({ sourceCode, property }) {
  switch (property.value.type) {
    case AST_NODE_TYPES.ArrowFunctionExpression:
    case AST_NODE_TYPES.FunctionExpression:
      return null
    default:
      return sourceCode.getText(property.value)
  }
}
function getRootObject(node) {
  let objectRoot = node
  while (
    objectRoot.parent.type === AST_NODE_TYPES.Property &&
    objectRoot.parent.parent.type === AST_NODE_TYPES.ObjectExpression
  ) {
    objectRoot = objectRoot.parent.parent
  }
  return objectRoot
}
export { sortObjects as default }
