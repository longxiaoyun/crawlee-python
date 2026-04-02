import * as webpack from 'webpack';
import { Options } from './types.cjs';
import 'svgo';

declare const _default: (options: Options) => webpack.WebpackPluginInstance;

export { _default as default };
