import { v4 as uuidv4 } from "uuid";
import { writable, type Writable } from "svelte/store";

class SessionStorage {
  private readonly ACTIVE_SESSION_KEY = "active_session";

  createSession() {
    const newId = uuidv4();
    this.setActiveSessionId(newId);
    activeSessionId.set(newId);
    return newId;
  }

  getActiveSessionId(): string | null {
    return localStorage.getItem(this.ACTIVE_SESSION_KEY);
  }

  setActiveSessionId(sessionId: string): void {
    localStorage.setItem(this.ACTIVE_SESSION_KEY, sessionId);
  }
}

export const sessionStorage = new SessionStorage();
const initialSession: string = sessionStorage.getActiveSessionId() || uuidv4();

export const activeSessionId: Writable<string> = writable(initialSession);
sessionStorage.setActiveSessionId(initialSession);
