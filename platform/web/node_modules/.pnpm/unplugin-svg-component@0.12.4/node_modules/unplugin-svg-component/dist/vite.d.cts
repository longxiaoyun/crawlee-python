import * as vite from 'vite';
import { Options } from './types.cjs';
import 'svgo';

declare const _default: (options: Options) => vite.Plugin | vite.Plugin[];

export { _default as default };
