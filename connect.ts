#!/usr/bin/env deno --unstable-net run --allow-all
import "jsr:@std/dotenv/load";
import Anthropic from "npm:@anthropic-ai/sdk";
import { Application } from "https://deno.land/x/oak/mod.ts";
import { generateResponse } from "./agent.ts";
import { OSCHandler } from "./ableton.ts";
import { analysisMessage } from "./consts.ts";
import { systemGenre, GENRE_SYSTEM_PROMPTS } from "./prompts.ts";
import { CustomWebSocket, WebSocketMessage } from "./types.d.ts";
import router from "./routes.ts";
const localOscPort = 11001;
const webSocketServerPort = 8000;

const anthropic = new Anthropic({
  apiKey: Deno.env.get("ANTHROPIC_API_KEY"), // Make sure to set this environment variable
});

const tools: Anthropic.Tool[] = [
  {
    name: "get_tracks_devices",
    description: "get all devices of all tracks",
    input_schema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "get_device_params",
    description: "get a specific device's params",
    input_schema: {
      type: "object",
      properties: {
        track_id: { type: "number" },
        device_id: { type: "number" },
      },
    },
  },
  {
    name: "set_device_param",
    description: "set a specific device's param",
    input_schema: {
      type: "object",
      properties: {
        track_id: { type: "number" },
        device_id: { type: "number" },
        param_id: { type: "number" },
        value: { type: "number" },
      },
      required: ["track_id", "device_id", "param_id", "value"],
    },
  },
];

const messages: Anthropic.MessageParam[] = [];

// Create the extension function
const extendWebSocket = (ws: WebSocket): CustomWebSocket => {
  const extended = ws as CustomWebSocket;
  extended.sendMessage = function (message: WebSocketMessage) {
    this.send(JSON.stringify(message));
  };
  return extended;
};

let ws: CustomWebSocket | undefined;

// UDP listener on port 110001
const udpSocket = Deno.listenDatagram({ port: localOscPort, transport: "udp" });
export const oscHandler = new OSCHandler(udpSocket);

const isLive = await oscHandler.isLive();
if (!isLive) {
  console.log("Unable to connect to Ableton. Exiting...");
  Deno.exit(0);
}

async function getRecentParameterChanges() {
  const changesSummary = oscHandler.getRecentParameterChanges();
  console.log("changes summary:", changesSummary);

  if (changesSummary.length === 0) {
    ws?.sendMessage({
      type: "error",
      content: "No recent changes to any devices",
    });
    return; // Skip if no changes
  }

  messages.push(analysisMessage(JSON.stringify(changesSummary)));

  try {
    const stream = anthropic.messages.stream({
      messages,
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2048,
    });

    let currentSuggestions = "";

    stream.on("text", (textDelta) => {
      console.log("[Text Chunk]", textDelta);
      currentSuggestions += textDelta;
      ws?.sendMessage({ type: "text", content: textDelta });
    });

    stream.on("end", () => {
      console.log("|END_MESSAGE|");
      ws?.sendMessage({ type: "end_message", content: "<|END_MESSAGE|>" });
    });

    const finalMessage = await stream.finalMessage();
    messages.push({ role: finalMessage.role, content: finalMessage.content });

    // does this work lol
    if (currentSuggestions.includes("[SUGGESTION]")) {
      // Send confirmation request to client
      ws?.sendMessage({
        type: "confirmation",
        content: "Would you like me to apply these changes? (yes/no)",
      });
    }
  } catch (error) {
    ws?.sendMessage({
      type: "error",
      content: `Error analyzing parameter changes: ${error}`,
    });
    console.error("Error analyzing parameter changes:", error);
  }
}

// Handle incoming messages from WebSocket
async function handleWebSocketMessage(event: MessageEvent) {
  console.log("EVENT: ", event.data);
  if (JSON.parse(event.data).message === "get-param-changes") {
    await getRecentParameterChanges();
    return;
  }
  if (event.data?.type === "suggestion_response") {
    if (event.data.response === "yes") {
      const executeMessage: Anthropic.MessageParam = {
        role: "user",
        content: `Yes, please make the suggestions you outlined.`,
      };
      await processMessage(executeMessage);
    }
    return;
  }
  const userMessage: Anthropic.MessageParam = {
    role: "user",
    content: event.data,
  };
  await processMessage(userMessage);
}

const headers = new Headers({
  "Access-Control-Allow-Origin": "*",
});

async function processMessage(message: Anthropic.MessageParam) {
  messages.push(message);

  let continueLoop = true;
  while (continueLoop) {
    try {
      const stream = anthropic.messages.stream({
        messages,
        model: "claude-3-5-sonnet-20241022",
        system:
          GENRE_SYSTEM_PROMPTS[
            systemGenre as keyof typeof GENRE_SYSTEM_PROMPTS
          ],
        max_tokens: 2048,
        tools,
      });

      stream.on("text", (textDelta) => {
        console.log("[Text Chunk]", textDelta);
        ws?.sendMessage({ type: "text", content: textDelta });
      });

      stream.on("end", () => {
        console.log("|END_MESSAGE|");
        ws?.sendMessage({ type: "end_message", content: "<|END_MESSAGE|>" });
      });

      const finalMessagePromise = new Promise<void>((resolve) => {
        stream.on("finalMessage", async (msg) => {
          console.log("[Final Message]", msg);
          messages.push({ role: msg.role, content: msg.content });

          let hasToolUse = false;
          const toolResults: Anthropic.ToolResultBlockParam[] = [];
          for (const contentBlock of msg.content) {
            if (contentBlock.type === "tool_use") {
              hasToolUse = true;
              ws?.sendMessage({
                type: "tool",
                content: contentBlock.name,
              });
              const response = await generateResponse(oscHandler, contentBlock);
              if (response.is_error) {
                throw new Error("tool usage failed!");
              }
              console.log("tool use result:", response);
              toolResults.push(response as Anthropic.ToolResultBlockParam);
            }
          }

          // we can exit if no tools needed
          if (!hasToolUse) {
            continueLoop = false;
          } else {
            // feed tool results back to the model
            messages.push({ role: "user", content: toolResults });
          }
          resolve();
        });
      });

      await Promise.all([stream.done(), finalMessagePromise]);
    } catch (error) {
      console.error("Error processing message:", error);
      if (error instanceof Error) {
        ws?.sendMessage({ type: "error", content: `Error: ${error.message}` });
      }
      continueLoop = false;
    }
  }
}

let currentSessionId: string | null = null;
let handlersInitialized = false;
let handlersLoading = false;

// Websocket stuff
// client should send websocket messages to port 8000
Deno.serve(
  {
    port: webSocketServerPort,
    hostname: "0.0.0.0",
  },
  // block all requests other than incoming websocket connections
  (req) => {
    if (req.headers.get("upgrade") != "websocket") {
      return new Response(null, { status: 501, headers });
    }

    const url = new URL(req.url);
    const sessionId = url.searchParams.get("sessionId");

    if (!sessionId) {
      return new Response("Session ID is required", { status: 400, headers });
    }

    // Clear message history if this is a new session
    if (sessionId !== currentSessionId) {
      messages.length = 0; // Clear the messages array
      currentSessionId = sessionId;
    }

    const { socket: _socket, response } = Deno.upgradeWebSocket(req);
    ws = extendWebSocket(_socket);
    // Wait for the connection to be established
    ws.addEventListener("open", async () => {
      ws?.addEventListener("message", handleWebSocketMessage);
      oscHandler.setWsClient(ws!);
      if (!handlersInitialized && !handlersLoading) {
        handlersLoading = true;
        await oscHandler.subscribeToDeviceParameters();
        handlersInitialized = true;
        handlersLoading = false;
        console.log("Finished setting up handlers for new session!");
      } else if (handlersInitialized) {
        ws?.sendMessage({ type: "loading_progress", content: 100 });
        console.log("Reusing existing parameter subscriptions");
      }
    });

    // Add cleanup when connection closes
    ws.addEventListener("close", () => {
      oscHandler.unsetWsClient();
    });
    return response;
  }
);

// REST stuff
const app = new Application();
app.use((ctx, next) => {
  ctx.response.headers.set("Access-Control-Allow-Origin", "*");
  ctx.response.headers.set(
    "Access-Control-Allow-Methods",
    "GET, POST, OPTIONS"
  );
  ctx.response.headers.set("Access-Control-Allow-Headers", "Content-Type");
  return next();
});
app.use(async (ctx, next) => {
  if (ctx.request.method === "OPTIONS") {
    ctx.response.status = 200;
    return;
  }
  await next();
});
app.use(router.routes());
app.use(router.allowedMethods());

app.listen({ port: 8080 });
console.log("REST server listening on port 8080");
