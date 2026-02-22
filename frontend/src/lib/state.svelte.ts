import type { ParameterChange, Track, Project } from "../types.d.ts";

export const loading = $state({
  progress: 0,
});

export const indexing = $state({
  isIndexing: false,
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

export const projectState = $state<{
  projects: Project[];
  activeProjectId: number | null;
}>({
  projects: [],
  activeProjectId: null,
});

// Helper to persist active project to localStorage
export function setActiveProject(projectId: number | null) {
  projectState.activeProjectId = projectId;
  if (projectId !== null) {
    localStorage.setItem("activeProjectId", String(projectId));
  } else {
    localStorage.removeItem("activeProjectId");
  }
}

export function loadActiveProjectFromStorage(): number | null {
  const stored = localStorage.getItem("activeProjectId");
  if (stored) {
    const id = parseInt(stored, 10);
    projectState.activeProjectId = id;
    return id;
  }
  return null;
}
