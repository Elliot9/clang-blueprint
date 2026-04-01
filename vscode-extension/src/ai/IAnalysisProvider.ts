/**
 * ai/IAnalysisProvider.ts — Re-exports the interface from shared/types.
 *
 * Consumers within the ai/ directory import from here to keep import paths
 * consistent and avoid reaching up through multiple directory levels.
 */

export type { IAnalysisProvider } from '../shared/types';
