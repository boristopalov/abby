import { type ChatMessage, type ChatSession, type Project } from "../types.d.ts";

// Import the types from the backend
interface Genre {
  name: string;
  systemPrompt: string;
  isDefault: boolean;
}

interface GenresResponse {
  genres: string[];
  defaultGenre: string | undefined;
  currentGenre: string | undefined;
}

interface ParameterChange {
  trackId: number;
  trackName: string;
  deviceId: number;
  deviceName: string;
  paramId: number;
  paramName: string;
  oldValue: number;
  newValue: number;
  min: number;
  max: number;
  timestamp: number;
}

interface RandomGenreResponse {
  genre: string;
}

const SERVER_BASE_URI = `http://localhost:8000/api`;

export async function fetchGenres(): Promise<GenresResponse> {
  const response = await fetch(`${SERVER_BASE_URI}/genres`);
  const data: GenresResponse = await response.json();
  if (!response.ok) {
    throw new Error("Failed to fetch genres");
  }
  return data;
}

export async function setGenre(genre: string): Promise<boolean> {
  const response = await fetch(`${SERVER_BASE_URI}/genres/set-current`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ genre }),
  });
  if (!response.ok) {
    throw new Error("Failed to set genre");
  }
  return true;
}

export async function setDefaultGenre(genre: string): Promise<boolean> {
  const response = await fetch(`${SERVER_BASE_URI}/genres/set-default`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ genre }),
  });
  if (!response.ok) {
    throw new Error("Failed to set default genre");
  }
  return true;
}

export async function getRecentParameterChanges(): Promise<ParameterChange[]> {
  const response = await fetch(`${SERVER_BASE_URI}/parameter-changes`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error("Failed to fetch parameter changes");
  }
  console.log("RECENT CHANGES:", data.changes);
  return data.changes as ParameterChange[];
}

export async function generateRandomGenre(): Promise<string> {
  const response = await fetch(`${SERVER_BASE_URI}/random-genre`);
  const data: RandomGenreResponse = await response.json();
  if (!response.ok) {
    throw new Error("Failed to generate random genre");
  }
  return data.genre;
}

export async function getSessionMessages(
  sessionId: string
): Promise<ChatMessage[]> {
  const response = await fetch(
    `${SERVER_BASE_URI}/session/${sessionId}/messages`
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error("Failed to fetch session messages");
  }

  console.log("MESSAGES:", data.messages);
  return data.messages;
}

export async function getSessions(): Promise<ChatSession[]> {
  const response = await fetch(`${SERVER_BASE_URI}/sessions`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error("Failed to fetch sessions");
  }

  return data.sessions;
}

// Project API calls

export async function getProjects(): Promise<Project[]> {
  const response = await fetch(`${SERVER_BASE_URI}/projects`);
  const data = await response.json();

  if (!response.ok) {
    throw new Error("Failed to fetch projects");
  }

  return data.projects;
}

export async function createProject(name: string): Promise<Project> {
  const response = await fetch(`${SERVER_BASE_URI}/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Failed to create project");
  }

  return data;
}

export async function deleteProject(projectId: number): Promise<void> {
  const response = await fetch(`${SERVER_BASE_URI}/projects/${projectId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Failed to delete project");
  }
}

export async function reindexProject(projectId: number): Promise<Project> {
  const response = await fetch(
    `${SERVER_BASE_URI}/projects/${projectId}/reindex`,
    {
      method: "POST",
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Failed to reindex project");
  }

  return data;
}
