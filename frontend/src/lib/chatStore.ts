import { writable, get } from "svelte/store";
import type { ChatMessage } from "../types.d.ts";

// Store for global chat messages
export const globalMessages = writable<ChatMessage[]>([]);

// Store for track-specific chats
export const trackChats = writable<Record<string, ChatMessage[]>>({});

// Helper functions to manage chats
export function addTrackMessage(trackId: string, message: ChatMessage) {
  trackChats.update((chats) => {
    const trackMessages = chats[trackId] || [];
    return {
      ...chats,
      [trackId]: [...trackMessages, message],
    };
  });
}

export function addGlobalMessage(message: ChatMessage) {
  globalMessages.update((messages) => [...messages, message]);
}

// Get messages for a specific track
export function getTrackMessages(trackId: string) {
  const chats = get(trackChats);
  return chats[trackId] || [];
}

// Clear messages for a specific track
export function clearTrackMessages(trackId: string) {
  trackChats.update((chats) => {
    const { [trackId]: _, ...rest } = chats;
    return rest;
  });
}

// Clear all messages
export function clearAllMessages() {
  globalMessages.set([]);
  trackChats.set({});
}

// Initialize track chat if it doesn't exist
export function initializeTrackChat(trackId: string) {
  trackChats.update((chats) => {
    if (!chats[trackId]) {
      return {
        ...chats,
        [trackId]: [],
      };
    }
    return chats;
  });
}
