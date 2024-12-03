// Add these types at the top of the file
interface ChatMessage {
  content: string;
  sender: "user" | "assistant";
}

document.getElementById("enterChat")?.addEventListener("click", function () {
  const ws = new WebSocket("ws://localhost:8000"); // Adjust port as needed
  let currentAssistantMessage: HTMLDivElement | null = null;

  ws.addEventListener("open", () => {
    console.log("Connected to WebSocket server");
  });

  ws.addEventListener("error", (error) => {
    console.error("WebSocket error:", error);
  });

  ws.addEventListener("message", (event) => {
    console.log("WS Message from server:", event.data);

    if (event.data === "<|END_MESSAGE|>") {
      // Message is complete, reset the current message tracker
      currentAssistantMessage = null;
      return;
    }

    if (!currentAssistantMessage) {
      // Start a new message block
      currentAssistantMessage = renderMessage({
        content: formatMessage(event.data),
        sender: "assistant",
      });
    } else {
      // Append to existing message block
      const contentElement = currentAssistantMessage.querySelector(".content");
      if (contentElement) {
        contentElement.textContent += formatMessage(event.data);
      }
    }
  });

  const authSection = document.getElementById("auth-section");
  if (authSection) authSection.style.display = "none";

  const chatSection = document.getElementById("chat-section");
  if (chatSection) chatSection.style.display = "flex";

  function sendMessage() {
    const messageInput = document.getElementById(
      "messageInput"
    ) as HTMLInputElement;
    if (!messageInput) {
      return;
    }
    const content = messageInput.value.trim();

    if (!content) return;

    // Render user message immediately
    renderMessage({
      content: content,
      sender: "user",
    });
    ws.send(JSON.stringify(content));

    // Clear input
    messageInput.value = "";
  }

  function renderMessage(message: ChatMessage): HTMLDivElement {
    const messagesDiv = document.getElementById("messages");
    if (!messagesDiv) throw new Error("Messages div not found");

    const messageElement = document.createElement("div");
    messageElement.classList.add("message", message.sender);

    const contentElement = document.createElement("div");
    contentElement.classList.add("content");
    contentElement.textContent = message.content;

    messageElement.appendChild(contentElement);
    messagesDiv.appendChild(messageElement);

    // Auto scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    return messageElement;
  }

  function formatMessage(text: string): string {
    return (
      text
        // Remove extra quotes
        .replace(/^"|"$/g, "")
        // Replace \n with actual newlines
        .replace(/\\n/g, "\n")
    );
  }

  // allow enter
  const messageInput = document.getElementById("messageInput");
  messageInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      sendMessage();
    }
  });
});
