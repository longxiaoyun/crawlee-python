import { AST_NODE_TYPES } from '@typescript-eslint/utils'
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
import { validateNewlinesAndPartitionConfiguration } from '../utils/validate-newlines-and-partition-configuration.js'
import { buildDefaultOptionsByGroupIndexComputer } from '../utils/build-default-options-by-group-index-computer.js'
import { buildComparatorByOptionsComputer } from './sort-enums/build-comparator-by-options-computer.js'
import { buildCommonGroupsJsonSchemas } from '../utils/json-schemas/common-groups-json-schemas.js'
import { validateCustomSortConfiguration } from '../utils/validate-custom-sort-configuration.js'
import { validateGroupsConfiguration } from '../utils/validate-groups-configuration.js'
import { buildCommonJsonSchemas } from '../utils/json-schemas/common-json-schemas.js'
import { additionalCustomGroupMatchOptionsJsonSchema } from './sort-enums/types.js'
import { sortNodesByDependencies } from '../utils/sort-nodes-by-dependencies.js'
import { getEslintDisabledLines } from '../utils/get-eslint-disabled-lines.js'
import { isNodeEslintDisabled } from '../utils/is-node-eslint-disabled.js'
import { doesCustomGroupMatch } from '../utils/does-custom-group-match.js'
import { sortNodesByGroups } from '../utils/sort-nodes-by-groups.js'
import { createEslintRule } from '../utils/create-eslint-rule.js'
import { reportAllErrors } from '../utils/report-all-errors.js'
import { shouldPartition } from '../utils/should-partition.js'
import { getEnumMembers } from '../utils/get-enum-members.js'
import { computeGroup } from '../utils/compute-group.js'
import { rangeToDiff } from '../utils/range-to-diff.js'
import { getSettings } from '../utils/get-settings.js'
import { isSortable } from '../utils/is-sortable.js'
import { complete } from '../utils/complete.js'
const ORDER_ERROR_ID = 'unexpectedEnumsOrder'
const GROUP_ORDER_ERROR_ID = 'unexpectedEnumsGroupOrder'
const EXTRA_SPACING_ERROR_ID = 'extraSpacingBetweenEnumsMembers'
const MISSED_SPACING_ERROR_ID = 'missedSpacingBetweenEnumsMembers'
const DEPENDENCY_ORDER_ERROR_ID = 'unexpectedEnumsDependencyOrder'
let defaultOptions = {
  fallbackSort: { type: 'unsorted' },
  newlinesInside: 'newlinesBetween',
  sortByValue: 'ifNumericEnum',
  partitionByComment: false,
  partitionByNewLine: false,
  specialCharacters: 'keep',
  newlinesBetween: 'ignore',
  type: 'alphabetical',
  ignoreCase: true,
  locales: 'en-US',
  customGroups: [],
  alphabet: '',
  order: 'asc',
  groups: [],
}
const sortEnums = createEslintRule({
  create: context => ({
    TSEnumDeclaration: enumDeclaration => {
      let members = getEnumMembers(enumDeclaration)
      if (
        !isSortable(members) ||
        !members.every(({ initializer }) => initializer)
      ) {
        return
      }
      let settings = getSettings(context.settings)
      let options = complete(context.options.at(0), settings, defaultOptions)
      validateCustomSortConfiguration(options)
      validateGroupsConfiguration({
        selectors: [],
        modifiers: [],
        options,
      })
      validateNewlinesAndPartitionConfiguration(options)
      let { sourceCode, id } = context
      let eslintDisabledLines = getEslintDisabledLines({
        ruleName: id,
        sourceCode,
      })
      function extractDependencies(expression, enumName) {
        let dependencies = []
        let stack = [expression]
        while (stack.length > 0) {
          let node = stack.pop()
          if (
            node.type === AST_NODE_TYPES.MemberExpression &&
            node.object.type === AST_NODE_TYPES.Identifier &&
            node.object.name === enumName &&
            node.property.type === AST_NODE_TYPES.Identifier
          ) {
            dependencies.push(node.property.name)
          } else if (node.type === AST_NODE_TYPES.Identifier) {
            dependencies.push(node.name)
          }
          if ('left' in node) {
            stack.push(node.left)
          }
          if ('right' in node) {
            stack.push(node.right)
          }
          if ('expressions' in node) {
            stack.push(...node.expressions)
          }
        }
        return dependencies
      }
      let formattedMembers = members.reduce(
        (accumulator, member) => {
          let dependencies = extractDependencies(
            member.initializer,
            enumDeclaration.id.name,
          )
          let name =
            member.id.type === AST_NODE_TYPES.Literal
              ? member.id.value
              : sourceCode.getText(member.id)
          let group = computeGroup({
            customGroupMatcher: customGroup =>
              doesCustomGroupMatch({
                elementValue: sourceCode.getText(member.initializer),
                elementName: name,
                selectors: [],
                modifiers: [],
                customGroup,
              }),
            predefinedGroups: [],
            options,
          })
          let lastSortingNode = accumulator.at(-1)?.at(-1)
          let sortingNode = {
            value:
              member.initializer?.type === AST_NODE_TYPES.Literal
                ? (member.initializer.value?.toString() ?? null)
                : null,
            isEslintDisabled: isNodeEslintDisabled(member, eslintDisabledLines),
            numericValue: getExpressionNumberValue(member.initializer),
            size: rangeToDiff(member, sourceCode),
            dependencyNames: [name],
            node: member,
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
      let nodes = formattedMembers.flat()
      let isNumericEnum = nodes.every(
        sortingNode => sortingNode.numericValue !== null,
      )
      function sortNodesExcludingEslintDisabled(ignoreEslintDisabledNodes) {
        let nodesSortedByGroups = formattedMembers.flatMap(sortingNodes =>
          sortNodesByGroups({
            optionsByGroupIndexComputer:
              buildDefaultOptionsByGroupIndexComputer(options),
            comparatorByOptionsComputer:
              buildComparatorByOptionsComputer(isNumericEnum),
            ignoreEslintDisabledNodes,
            groups: options.groups,
            nodes: sortingNodes,
          }),
        )
        return sortNodesByDependencies(nodesSortedByGroups, {
          ignoreEslintDisabledNodes,
        })
      }
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
    },
  }),
  meta: {
    schema: [
      {
        properties: {
          ...buildCommonJsonSchemas(),
          ...buildCommonGroupsJsonSchemas({
            additionalCustomGroupMatchProperties:
              additionalCustomGroupMatchOptionsJsonSchema,
          }),
          sortByValue: {
            description: 'Specifies whether to sort enums by value.',
            enum: ['always', 'ifNumericEnum', 'never'],
            type: 'string',
          },
          partitionByComment: partitionByCommentJsonSchema,
          partitionByNewLine: partitionByNewLineJsonSchema,
        },
        additionalProperties: false,
        type: 'object',
      },
    ],
    messages: {
      [DEPENDENCY_ORDER_ERROR_ID]: DEPENDENCY_ORDER_ERROR,
      [MISSED_SPACING_ERROR_ID]: MISSED_SPACING_ERROR,
      [EXTRA_SPACING_ERROR_ID]: EXTRA_SPACING_ERROR,
      [GROUP_ORDER_ERROR_ID]: GROUP_ORDER_ERROR,
      [ORDER_ERROR_ID]: ORDER_ERROR,
    },
    docs: {
      url: 'https://perfectionist.dev/rules/sort-enums',
      description: 'Enforce sorted TypeScript enums.',
      recommended: true,
    },
    type: 'suggestion',
    fixable: 'code',
  },
  defaultOptions: [defaultOptions],
  name: 'sort-enums',
})
function getBinaryExpressionNumberValue(
  leftExpression,
  rightExpression,
  operator,
) {
  let left = getExpressionNumberValue(leftExpression)
  let right = getExpressionNumberValue(rightExpression)
  if (left === null || right === null) {
    return null
  }
  switch (operator) {
    case '**':
      return left ** right
    case '>>':
      return left >> right
    case '<<':
      return left << right
    case '+':
      return left + right
    case '-':
      return left - right
    case '*':
      return left * right
    case '/':
      return left / right
    case '%':
      return left % right
    case '|':
      return left | right
    case '&':
      return left & right
    case '^':
      return left ^ right
    /* v8 ignore next 2 -- @preserve Unsure if we can reach it. */
    default:
      return null
  }
}
function getExpressionNumberValue(expression) {
  switch (expression.type) {
    case AST_NODE_TYPES.BinaryExpression:
      return getBinaryExpressionNumberValue(
        expression.left,
        expression.right,
        expression.operator,
      )
    case AST_NODE_TYPES.UnaryExpression:
      return getUnaryExpressionNumberValue(
        expression.argument,
        expression.operator,
      )
    case AST_NODE_TYPES.Literal:
      return typeof expression.value === 'number' ? expression.value : null
    default:
      return null
  }
}
function getUnaryExpressionNumberValue(argumentExpression, operator) {
  let argument = getExpressionNumberValue(argumentExpression)
  if (argument === null) {
    return null
  }
  switch (operator) {
    case '+':
      return argument
    case '-':
      return -argument
    case '~':
      return ~argument
    /* v8 ignore next 2 -- @preserve Unsure if we can reach it. */
    default:
      return null
  }
}
export { sortEnums as default }
