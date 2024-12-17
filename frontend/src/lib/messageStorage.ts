import { v4 as uuidv4 } from "uuid";
import { writable, type Writable } from "svelte/store";

export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp: number;
  type?: "text" | "tool" | "error";
}

export interface ChatSession {
  id: string;
  name: string;
  createdAt: number;
  messages: ChatMessage[];
}

interface SessionsMap {
  [key: string]: ChatSession;
}

class MessageStorage {
  private readonly SESSIONS_KEY = "chat_sessions";
  private readonly ACTIVE_SESSION_KEY = "active_session";

  private generateSessionId(): string {
    return uuidv4();
  }

  createSession(
    name: string = `Chat ${new Date().toLocaleDateString()}`
  ): ChatSession {
    const sessions = this.getAllSessions();
    const newSession: ChatSession = {
      id: this.generateSessionId(),
      name,
      createdAt: Date.now(),
      messages: [],
    };
    console.log("Creating session");

    sessions[newSession.id] = newSession;
    this.saveSessions(sessions);
    this.setActiveSession(newSession.id);
    return newSession;
  }

  getAllSessions(): SessionsMap {
    try {
      const stored = localStorage.getItem(this.SESSIONS_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error("Error loading sessions:", error);
      return {};
    }
  }

  getSessionsList(): ChatSession[] {
    return Object.values(this.getAllSessions()).sort(
      (a, b) => b.createdAt - a.createdAt
    );
  }

  getSession(sessionId: string): ChatSession | null {
    const sessions = this.getAllSessions();
    return sessions[sessionId];
  }

  getActiveSessionId(): string | null {
    return localStorage.getItem(this.ACTIVE_SESSION_KEY);
  }

  setActiveSession(sessionId: string): void {
    localStorage.setItem(this.ACTIVE_SESSION_KEY, sessionId);
    activeSession.set(this.getSession(sessionId)!);
  }

  getActiveSession(): ChatSession | null {
    const activeId = this.getActiveSessionId();
    if (activeId) {
      const session = this.getSession(activeId);
      if (!session) {
        return null;
      }
      return session;
    }
    return null;
  }

  getMessages(sessionId: string): ChatMessage[] | undefined {
    return this.getSession(sessionId)?.messages;
  }

  // TIL Omit type
  addMessage(message: Omit<ChatMessage, "timestamp">): ChatSession {
    const sessions = this.getAllSessions();
    const session = this.getActiveSession();

    if (!session) {
      throw new Error("No active session");
    }

    const newMessage: ChatMessage = {
      ...message,
      timestamp: Date.now(),
    };

    session.messages.push(newMessage);
    sessions[session.id] = session;
    console.log("SESSION:", session);
    this.saveSessions(sessions);

    activeSession.update((curr) => ({
      ...curr,
      messages: session.messages,
    })); // update svelte store
    return session;
  }

  deleteSession(sessionId: string): void {
    const sessions = this.getAllSessions();
    delete sessions[sessionId];
    this.saveSessions(sessions);

    if (this.getActiveSessionId() === sessionId) {
      this.createSession();
    }
  }

  deleteActiveSession(): void {
    const sessions = this.getAllSessions();
    const activeSessionId = this.getActiveSessionId();
    if (activeSessionId) {
      delete sessions[activeSessionId];
      this.createSession();
    }
  }

  renameSession(sessionId: string, newName: string): void {
    const sessions = this.getAllSessions();
    if (sessions[sessionId]) {
      sessions[sessionId].name = newName;
      this.saveSessions(sessions);
    }
  }

  private saveSessions(sessions: SessionsMap): void {
    localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(sessions));
  }

  clearAllSessions(): void {
    localStorage.removeItem(this.SESSIONS_KEY);
    localStorage.removeItem(this.ACTIVE_SESSION_KEY);
  }
}

export const messageStorage = new MessageStorage();
const initialSession: ChatSession = messageStorage.getActiveSession() || {
  id: uuidv4(),
  name: `Chat ${new Date().toLocaleDateString()}`,
  messages: [],
  createdAt: Date.now(),
};
if (!localStorage.getItem("chat_sessions")) {
  localStorage.setItem(
    "chat_sessions",
    JSON.stringify({
      [initialSession.id]: { ...initialSession },
    })
  );
}
export const activeSession: Writable<ChatSession> = writable(initialSession);
messageStorage.setActiveSession(initialSession.id);
