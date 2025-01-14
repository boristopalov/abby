import type { ParameterChange, Track } from "../types.d.ts";
export const loading = $state({
  progress: 0,
});
export const parameterChanges = $state<{
  changes: ParameterChange[];
}>({
  changes: [],
});
export const tracks = $state<{
  tracks: Track[];
}>({
  tracks: [],
});
export const genres = $state<{
  availableGenres: string[];
  activeGenre: string;
}>({
  availableGenres: [],
  activeGenre: "",
});
