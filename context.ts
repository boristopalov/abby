import Anthropic from "npm:@anthropic-ai/sdk";
import { GENRE_SYSTEM_PROMPTS, TRIBAL_SCIFI_TECHNO } from "./prompts.ts";
import { dbService } from "./db.ts";

interface CurrentGenre {
  genre: string;
  systemPrompt: string;
}

export class ChatContext {
  private static instance: ChatContext;

  public currentSessionId: string | null = null;
  public handlersInitialized: boolean = false;
  public handlersLoading: boolean = false;
  public messages: Anthropic.MessageParam[] = [];
  public currentGenre: CurrentGenre = {
    genre: TRIBAL_SCIFI_TECHNO,
    systemPrompt: GENRE_SYSTEM_PROMPTS[TRIBAL_SCIFI_TECHNO],
  };
  public anthropic = new Anthropic({
    apiKey: Deno.env.get("ANTHROPIC_API_KEY"),
  });

  private constructor() {}

  public static getInstance(): ChatContext {
    if (!ChatContext.instance) {
      ChatContext.instance = new ChatContext();
    }
    return ChatContext.instance;
  }

  public addMessage(message: Anthropic.MessageParam): void {
    this.messages.push(message);
  }

  public clearMessages(): void {
    this.messages = [];
  }

  public setCurrentGenre(genre: string) {
    const genreData = dbService.getGenreByName(genre);
    if (!genreData) {
      throw new Error(`Genre ${genre} not found`);
    }
    context.currentGenre = {
      genre: genreData.name,
      systemPrompt: genreData.systemPrompt,
    };
  }
}

export const context = ChatContext.getInstance();
