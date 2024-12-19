import { Database } from "jsr:@db/sqlite@0.12";
import { GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO } from "./prompts.ts";

// Initialize database
const db = new Database("live.db");

// Create tables if they don't exist
db.exec(`
  CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    text TEXT NOT NULL,
    is_user BOOLEAN NOT NULL,
    type TEXT CHECK(type IN ('text', 'tool', 'error')) DEFAULT 'text',
    timestamp INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS parameter_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    track_name TEXT NOT NULL,
    device_id INTEGER NOT NULL,
    device_name TEXT NOT NULL,
    param_id INTEGER NOT NULL,
    param_name TEXT NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    timestamp INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    system_prompt TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE
  );
`);

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

export interface ParameterChange {
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

export class DatabaseService {
  // Session methods
  createSession(name: string, id: string): ChatSession {
    const timestamp = Date.now();
    db.prepare(
      "INSERT INTO sessions (id, name, created_at) VALUES (?, ?, ?)"
    ).run(id, name, timestamp);
    return {
      id,
      name,
      createdAt: timestamp,
      messages: [],
    };
  }

  getSession(sessionId: string): ChatSession | null {
    const session = db
      .prepare("SELECT id, name, created_at FROM sessions WHERE id = ?")
      .value<[string, string, number]>(sessionId);

    if (!session) return null;

    const messages = this.getMessages(sessionId);
    return {
      id: session[0],
      name: session[1],
      createdAt: session[2],
      messages,
    };
  }

  getAllSessions(): ChatSession[] {
    const sessions = db
      .prepare(
        "SELECT id, name, created_at FROM sessions ORDER BY created_at DESC"
      )
      .values<[string, string, number]>();

    return sessions.map((session) => ({
      id: session[0],
      name: session[1],
      createdAt: session[2],
      messages: this.getMessages(session[0]),
    }));
  }

  deleteSession(sessionId: string): void {
    db.prepare("DELETE FROM sessions WHERE id = ?").run(sessionId);
  }

  // Message methods
  addMessage(sessionId: string, message: Omit<ChatMessage, "timestamp">): void {
    const timestamp = Date.now();
    db.prepare(
      "INSERT INTO messages (session_id, text, is_user, type, timestamp) VALUES (?, ?, ?, ?, ?)"
    ).run(
      sessionId,
      message.text,
      message.isUser,
      message.type || "text",
      timestamp
    );
  }

  getMessages(sessionId: string): ChatMessage[] {
    return db
      .prepare(
        "SELECT text, is_user, type, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp ASC"
      )
      .values<[string, boolean, string, number]>(sessionId)
      .map((row) => ({
        text: row[0],
        isUser: row[1],
        type: row[2] as "text" | "tool" | "error",
        timestamp: row[3],
      }));
  }

  // Parameter change methods
  addParameterChange(change: ParameterChange): void {
    db.prepare(
      `
      INSERT INTO parameter_changes 
      (track_id, track_name, device_id, device_name, param_id, param_name, 
       old_value, new_value, min_value, max_value, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `
    ).run(
      change.trackId,
      change.trackName,
      change.deviceId,
      change.deviceName,
      change.paramId,
      change.paramName,
      change.oldValue,
      change.newValue,
      change.min,
      change.max,
      change.timestamp
    );
  }

  getRecentParameterChanges(limit = 100): ParameterChange[] {
    return db
      .prepare(
        `
      SELECT track_id, track_name, device_id, device_name, param_id, param_name,
             old_value, new_value, min_value, max_value, timestamp
      FROM parameter_changes 
      ORDER BY timestamp DESC 
      LIMIT ?
    `
      )
      .values<
        [
          number,
          string,
          number,
          string,
          number,
          string,
          number,
          number,
          number,
          number,
          number
        ]
      >(limit)
      .map((row) => ({
        trackId: row[0],
        trackName: row[1],
        deviceId: row[2],
        deviceName: row[3],
        paramId: row[4],
        paramName: row[5],
        oldValue: row[6],
        newValue: row[7],
        min: row[8],
        max: row[9],
        timestamp: row[10],
      }));
  }

  // Genre methods
  addGenre(name: string, systemPrompt: string, isDefault = false): void {
    if (isDefault) {
      // Reset any existing default
      db.prepare(
        "UPDATE genres SET is_default = FALSE WHERE is_default = TRUE"
      ).run();
    }
    db.prepare(
      "INSERT INTO genres (name, system_prompt, is_default) VALUES (?, ?, ?)"
    ).run(name, systemPrompt, isDefault);
  }

  getGenres(): { name: string; systemPrompt: string; isDefault: boolean }[] {
    return db
      .prepare("SELECT name, system_prompt, is_default FROM genres")
      .values<[string, string, boolean]>()
      .map((row) => ({
        name: row[0],
        systemPrompt: row[1],
        isDefault: row[2],
      }));
  }

  getDefaultGenre(): { name: string; systemPrompt: string } | null {
    const genre = db
      .prepare(
        "SELECT name, system_prompt FROM genres WHERE is_default = TRUE LIMIT 1"
      )
      .value<[string, string]>();
    return genre ? { name: genre[0], systemPrompt: genre[1] } : null;
  }

  setDefaultGenre(name: string): void {
    db.prepare(
      "UPDATE genres SET is_default = FALSE WHERE is_default = TRUE"
    ).run();
    db.prepare("UPDATE genres SET is_default = TRUE WHERE name = ?").run(name);
  }

  getGenreByName(name: string): { name: string; systemPrompt: string } | null {
    const genre = db
      .prepare("SELECT name, system_prompt FROM genres WHERE name = ?")
      .value<[string, string]>(name);
    return genre ? { name: genre[0], systemPrompt: genre[1] } : null;
  }

  initializeGenres() {
    // First check if genres already exist
    const existingGenres = this.getGenres();
    if (existingGenres.length > 0) return;

    // Add all genres from the GENRE_SYSTEM_PROMPTS
    Object.entries(GENRE_SYSTEM_PROMPTS).forEach(([name, prompt]) => {
      this.addGenre(name, prompt, name === TRIBAL_SCIFI_TECHNO); // Set Tribal/Sci-fi Techno as default
    });
  }
}

export const dbService = new DatabaseService();
dbService.initializeGenres();
