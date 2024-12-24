#!/usr/bin/env deno --unstable-net run --allow-all
import "jsr:@std/dotenv/load";
import Anthropic from "npm:@anthropic-ai/sdk";
import { Application } from "https://deno.land/x/oak/mod.ts";
import { generateResponse } from "./agent.ts";
import { OSCHandler } from "./ableton.ts";
import { analysisMessage, LOCAL_OSC_PORT, WEBSOCKET_PORT } from "./consts.ts";
import { CustomWebSocket, WebSocketMessage } from "./types.d.ts";
import router from "./routes.ts";
import { dbService } from "./db.ts";
import { context } from "./context.ts";
import { generateRandomSlug } from "./slugs.ts";

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
const udpSocket = Deno.listenDatagram({
  port: LOCAL_OSC_PORT,
  transport: "udp",
});
export const oscHandler = new OSCHandler(udpSocket);

const isLive = await oscHandler.isLive();
if (!isLive) {
  console.log("Unable to connect to Ableton. Exiting...");
  Deno.exit(0);
}

// TODO: fix this logic this shit is a bad idea
async function getRecentParameterChanges() {
  const changesSummary = oscHandler.getRecentParameterChanges();
  console.log("changes summary:", changesSummary);

  await processMessage(analysisMessage(JSON.stringify(changesSummary)));
  return;
}

// Handle incoming messages from WebSocket
async function handleWebSocketMessage(event: MessageEvent) {
  const data = JSON.parse(event.data);
  const msg = data.message;
  if (msg === "get-param-changes") {
    await getRecentParameterChanges();
    return;
  }
  if (data.type === "suggestion_response") {
    if (data.response === "yes") {
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
    content: msg,
  };
  await processMessage(userMessage);
}

// Update processMessage to use the Map
async function processMessage(message: Anthropic.MessageParam) {
  const session = dbService.getSession(context.currentSessionId!);
  if (!session) {
    throw new Error("No active session");
  }

  context.addMessage(message);
  if (message.role === "user") {
    dbService.addMessage(context.currentSessionId!, {
      text: message.content as string,
      isUser: true,
      type: "text",
    });
  }

  let continueLoop = true;
  while (continueLoop) {
    try {
      const stream = context.anthropic.messages.stream({
        messages: context.messages,
        model: "claude-3-5-sonnet-20241022",
        system: context.currentGenre.systemPrompt,
        max_tokens: 2048,
        tools,
      });

      stream.on("text", (textDelta) => {
        console.log("[Text Chunk]", textDelta);
        ws?.sendMessage({ type: "text", content: textDelta });
      });

      stream.on("end", () => {
        console.log("|END_MESSAGE|");
      });

      const finalMessagePromise = new Promise<void>((resolve) => {
        stream.on("finalMessage", async (msg) => {
          console.log("[Final Message]", msg);

          // Add assistant message to both stores
          context.addMessage({ role: msg.role, content: msg.content });

          let hasToolUse = false;
          ws?.sendMessage({ type: "end_message", content: "<|END_MESSAGE|>" });
          const toolResults: Anthropic.ToolResultBlockParam[] = [];
          for (const contentBlock of msg.content) {
            if (contentBlock.type === "tool_use") {
              hasToolUse = true;

              dbService.addMessage(context.currentSessionId!, {
                text: contentBlock.name,
                type: "tool",
                isUser: false,
              });

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
            } else {
              dbService.addMessage(context.currentSessionId!, {
                text: contentBlock.text,
                type: "text",
                isUser: false,
              });
            }
          }

          // we can exit if no tools needed
          if (!hasToolUse) {
            continueLoop = false;
          } else {
            // feed tool results back to the model
            context.addMessage({ role: "user", content: toolResults });
          }
          resolve();
        });
      });

      await Promise.all([stream.done(), finalMessagePromise]);
    } catch (error) {
      console.error("Error processing message:", error);
      if (error instanceof Error) {
        const errMsg = `Error: ${error.message}`;
        dbService.addMessage(context.currentSessionId!, {
          text: errMsg,
          type: "error",
          isUser: false,
        });
        ws?.sendMessage({ type: "error", content: errMsg });
      }
      continueLoop = false;
    }
  }
}

const headers = new Headers({
  "Access-Control-Allow-Origin": "*",
});

// Websocket stuff
// client should send websocket messages to port 8000
Deno.serve(
  {
    port: WEBSOCKET_PORT,
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
    if (sessionId !== context.currentSessionId) {
      context.clearMessages();
      context.currentSessionId = sessionId;
      const s = dbService.getSession(sessionId);
      if (!s) {
        dbService.createSession(generateRandomSlug(), sessionId);
      }
    }

    const { socket: _socket, response } = Deno.upgradeWebSocket(req);
    ws = extendWebSocket(_socket);
    // Wait for the connection to be established
    ws.addEventListener("open", async () => {
      ws?.addEventListener("message", handleWebSocketMessage);
      oscHandler.setWsClient(ws!);
      if (!context.handlersInitialized && !context.handlersLoading) {
        context.handlersLoading = true;
        await oscHandler.subscribeToDeviceParameters();
        context.handlersInitialized = true;
        context.handlersLoading = false;
        console.log("Finished setting up handlers for new session!");
      } else if (context.handlersInitialized) {
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
