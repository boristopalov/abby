export interface ChatMessage {
  text: string;
  isUser: boolean;
  timestamp: number;
}

class MessageStorage {
  private readonly STORAGE_KEY = "chat_history";

  getMessages(): ChatMessage[] {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error("Error loading messages:", error);
      return [];
    }
  }

  addMessage(message: Omit<ChatMessage, "timestamp">): ChatMessage[] {
    try {
      const messages = this.getMessages();
      const newMessage = {
        ...message,
        timestamp: Date.now(),
      };

      const updatedMessages = [...messages, newMessage];
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(updatedMessages));
      return updatedMessages;
    } catch (error) {
      console.error("Error saving message:", error);
      return this.getMessages();
    }
  }

  clearMessages(): void {
    localStorage.removeItem(this.STORAGE_KEY);
  }
}

export const messageStorage = new MessageStorage();
