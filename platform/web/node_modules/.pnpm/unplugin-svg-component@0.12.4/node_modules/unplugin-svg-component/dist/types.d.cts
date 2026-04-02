import { Config } from 'svgo';

interface Options {
    iconDir: string | string[];
    prefix?: string;
    hmr?: boolean;
    dts?: boolean;
    dtsDir?: string;
    svgSpriteDomId?: string;
    componentName?: string;
    preserveColor?: string | RegExp;
    componentStyle?: string;
    componentClass?: string;
    symbolIdFormatter?: (name: string, prefix: string) => string;
    optimizeOptions?: Config;
    projectType?: 'vue' | 'react' | 'auto';
    vueVersion?: VueVersion;
    treeShaking?: boolean;
    scanGlob?: string[];
    scanStrategy?: 'text' | 'component' | ((code: string[], options: Options) => string[]);
    /**
     * Controls the method of injecting SVG elements. Possible values:
     * 'replaceHtml'(default): Injects the SVG elements by replacing the HTML string.
     * 'dynamic': Injects the SVG elements through JavaScript dynamically.
     * Warning: if you are in ssr mode, you should use 'replaceHtml' strategy.
     */
    domInsertionStrategy?: 'replaceHtml' | 'dynamic';
}
type VueVersion = 2 | 3 | 'auto';
interface SvgSpriteInfo {
    sprite: string;
    symbolIds: Set<string>;
}

export type { Options, SvgSpriteInfo, VueVersion };
