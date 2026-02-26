import {
  type ChatMessage,
  type ChatSession,
  type Project,
  // @ts-ignore
} from "../types.d.ts";

const SERVER_BASE_URI = `http://localhost:8000/api`;

export async function getSessionMessages(
  sessionId: string,
): Promise<ChatMessage[]> {
  const response = await fetch(
    `${SERVER_BASE_URI}/session/${sessionId}/messages`,
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
