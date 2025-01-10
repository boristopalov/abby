import { type ChatMessage } from "../types.d.ts";

// Import the types from the backend
interface Genre {
  name: string;
  systemPrompt: string;
  isDefault: boolean;
}

interface GenresResponse {
  genres: string[];
  defaultGenre: string | null;
  currentGenre: string | null;
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
  const data: ParameterChange[] = await response.json();

  if (!response.ok) {
    throw new Error("Failed to fetch parameter changes");
  }
  return data;
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
