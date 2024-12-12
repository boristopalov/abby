import { v4 as uuidv4 } from "uuid";

export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp: number;
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
    return sessions[sessionId] || null;
  }

  getActiveSessionId(): string | null {
    return localStorage.getItem(this.ACTIVE_SESSION_KEY);
  }

  setActiveSession(sessionId: string): void {
    localStorage.setItem(this.ACTIVE_SESSION_KEY, sessionId);
  }

  getActiveSession(): ChatSession | null {
    const activeId = this.getActiveSessionId();
    if (!activeId) return null;
    return this.getSession(activeId);
  }

  addMessage(message: Omit<ChatMessage, "timestamp">): ChatSession {
    const sessions = this.getAllSessions();
    const activeId = this.getActiveSessionId();

    if (!activeId) {
      throw new Error("No active session");
    }

    const session = sessions[activeId];
    if (!session) {
      throw new Error("Active session not found");
    }

    const newMessage: ChatMessage = {
      ...message,
      timestamp: Date.now(),
    };

    session.messages.push(newMessage);
    this.saveSessions(sessions);
    return session;
  }

  deleteSession(sessionId: string): void {
    const sessions = this.getAllSessions();
    delete sessions[sessionId];
    this.saveSessions(sessions);

    if (this.getActiveSessionId() === sessionId) {
      const remainingSessions = Object.values(sessions);
      const newActiveSession = remainingSessions[0];
      if (newActiveSession) {
        this.setActiveSession(newActiveSession.id);
      } else {
        localStorage.removeItem(this.ACTIVE_SESSION_KEY);
      }
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
