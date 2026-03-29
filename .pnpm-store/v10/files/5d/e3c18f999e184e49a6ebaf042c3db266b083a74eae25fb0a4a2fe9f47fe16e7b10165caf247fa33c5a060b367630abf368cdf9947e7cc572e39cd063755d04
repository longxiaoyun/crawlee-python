import { AST, TOMLVersionOption } from "toml-eslint-parser";
import { IDirective, TextSourceCodeBase, TraversalStep } from "@eslint/plugin-kit";
import * as _eslint_core0 from "@eslint/core";
import { File, FileProblem, Language, OkParseResult, RuleDefinition, RulesConfig } from "@eslint/core";
import { Linter, Scope } from "eslint";

//#region src/meta.d.ts
declare namespace meta_d_exports {
  export { name, version };
}
declare const name: string;
declare const version: string;
//#endregion
//#region src/language/token-store.d.ts

type FilterPredicate = (tokenOrComment: TOMLToken) => boolean;
type CursorWithSkipOptions = number | FilterPredicate | {
  includeComments?: boolean;
  filter?: FilterPredicate;
  skip?: number;
};
type CursorWithCountOptions = number | FilterPredicate | {
  includeComments?: boolean;
  filter?: FilterPredicate;
  count?: number;
};
//#endregion
//#region src/language/toml-source-code.d.ts
/**
 * TOML-specific syntax element type
 */
type TOMLSyntaxElement = AST.TOMLNode | AST.Token | AST.Comment;
type TOMLToken = AST.Token | AST.Comment;
/**
 * TOML Source Code Object
 */
declare class TOMLSourceCode extends TextSourceCodeBase<{
  LangOptions: Record<never, never>;
  RootNode: AST.TOMLProgram;
  SyntaxElementWithLoc: TOMLSyntaxElement;
  ConfigNode: AST.Comment;
}> {
  #private;
  readonly hasBOM: boolean;
  readonly parserServices: {
    isTOML?: boolean;
    parseError?: unknown;
  };
  readonly visitorKeys: Record<string, string[]>;
  private readonly tokenStore;
  /**
   * Creates a new instance.
   */
  constructor(config: {
    text: string;
    ast: AST.TOMLProgram;
    hasBOM: boolean;
    parserServices: {
      isTOML: boolean;
      parseError?: unknown;
    };
    visitorKeys?: Record<string, string[]> | null | undefined;
  });
  traverse(): Iterable<TraversalStep>;
  /**
   * Gets all tokens and comments.
   */
  get tokensAndComments(): TOMLToken[];
  getLines(): string[];
  getAllComments(): AST.Comment[];
  /**
   * Returns an array of all inline configuration nodes found in the source code.
   * This includes eslint-disable, eslint-enable, eslint-disable-line,
   * eslint-disable-next-line, and eslint (for inline config) comments.
   */
  getInlineConfigNodes(): AST.Comment[];
  /**
   * Returns directives that enable or disable rules along with any problems
   * encountered while parsing the directives.
   */
  getDisableDirectives(): {
    directives: IDirective[];
    problems: FileProblem[];
  };
  /**
   * Returns inline rule configurations along with any problems
   * encountered while parsing the configurations.
   */
  applyInlineConfig(): {
    configs: {
      config: {
        rules: RulesConfig;
      };
      loc: AST.SourceLocation;
    }[];
    problems: FileProblem[];
  };
  getNodeByRangeIndex(index: number): AST.TOMLNode | null;
  getFirstToken(node: TOMLSyntaxElement): AST.Token;
  getFirstToken(node: TOMLSyntaxElement, options?: CursorWithSkipOptions): TOMLToken | null;
  getLastToken(node: TOMLSyntaxElement): AST.Token;
  getLastToken(node: TOMLSyntaxElement, options?: CursorWithSkipOptions): TOMLToken | null;
  getTokenBefore(node: TOMLSyntaxElement): AST.Token | null;
  getTokenBefore(node: TOMLSyntaxElement, options?: CursorWithSkipOptions): TOMLToken | null;
  getTokensBefore(node: TOMLSyntaxElement, options?: CursorWithCountOptions): TOMLToken[];
  getTokenAfter(node: TOMLSyntaxElement): AST.Token | null;
  getTokenAfter(node: TOMLSyntaxElement, options?: CursorWithSkipOptions): TOMLToken | null;
  getFirstTokenBetween(left: TOMLSyntaxElement, right: TOMLSyntaxElement, options?: CursorWithSkipOptions): TOMLToken | null;
  getTokensBetween(left: TOMLSyntaxElement, right: TOMLSyntaxElement, paddingOrOptions?: number | FilterPredicate | CursorWithCountOptions): TOMLToken[];
  getTokens(node: AST.TOMLNode, options?: FilterPredicate | CursorWithCountOptions): TOMLToken[];
  getCommentsBefore(nodeOrToken: TOMLSyntaxElement): AST.Comment[];
  getCommentsAfter(nodeOrToken: TOMLSyntaxElement): AST.Comment[];
  isSpaceBetween(first: TOMLToken, second: TOMLToken): boolean;
  /**
   * Compatibility for ESLint's SourceCode API
   * @deprecated TOML does not have scopes
   */
  getScope(node?: AST.TOMLNode): Scope.Scope | null;
  /**
   * Compatibility for ESLint's SourceCode API
   * @deprecated TOML does not have scopes
   */
  get scopeManager(): Scope.ScopeManager | null;
  /**
   * Compatibility for ESLint's SourceCode API
   * @deprecated
   */
  isSpaceBetweenTokens(first: TOMLToken, second: TOMLToken): boolean;
  private _getChildren;
}
//#endregion
//#region src/language/toml-language.d.ts
/**
 * Parse result
 */
interface TOMLParseResult {
  ok: true;
  ast: AST.TOMLProgram;
}
/**
 * Language options for TOML
 * Currently no options are defined.
 */
type TOMLLanguageOptions = {
  parserOptions?: {
    tomlVersion?: TOMLVersionOption;
  };
};
/**
 * The TOML language implementation for ESLint.
 */
declare class TOMLLanguage implements Language<{
  LangOptions: TOMLLanguageOptions;
  Code: TOMLSourceCode;
  RootNode: AST.TOMLProgram;
  Node: AST.TOMLNode;
}> {
  /**
   * The type of file to read.
   */
  fileType: "text";
  /**
   * The line number at which the parser starts counting.
   */
  lineStart: 1;
  /**
   * The column number at which the parser starts counting.
   */
  columnStart: 0;
  /**
   * The name of the key that holds the type of the node.
   */
  nodeTypeKey: "type";
  /**
   * Validates the language options.
   */
  validateLanguageOptions(_languageOptions: TOMLLanguageOptions): void;
  normalizeLanguageOptions(languageOptions: TOMLLanguageOptions): TOMLLanguageOptions;
  /**
   * Parses the given file into an AST.
   */
  parse(file: File, context: {
    languageOptions?: TOMLLanguageOptions;
  }): OkParseResult<AST.TOMLProgram> | TOMLParseResult;
  /**
   * Creates a new SourceCode object for the given file and parse result.
   */
  createSourceCode(file: File, parseResult: OkParseResult<AST.TOMLProgram> | TOMLParseResult): TOMLSourceCode;
}
//#endregion
//#region src/index.d.ts
declare const configs: {
  base: Linter.Config[];
  recommended: Linter.Config[];
  standard: Linter.Config[];
  "flat/base": Linter.Config[];
  "flat/recommended": Linter.Config[];
  "flat/standard": Linter.Config[];
};
declare const rules: Record<string, RuleDefinition>;
declare const languages: {
  toml: TOMLLanguage;
};
declare const _default: {
  meta: typeof meta_d_exports;
  configs: {
    base: Linter.Config[];
    recommended: Linter.Config[];
    standard: Linter.Config[];
    "flat/base": Linter.Config[];
    "flat/recommended": Linter.Config[];
    "flat/standard": Linter.Config[];
  };
  rules: Record<string, RuleDefinition<_eslint_core0.RuleDefinitionTypeOptions>>;
  languages: {
    toml: TOMLLanguage;
  };
};
//#endregion
export { type TOMLLanguageOptions, type TOMLSourceCode, configs, _default as default, languages, meta_d_exports as meta, rules };