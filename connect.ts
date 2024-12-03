#!/usr/bin/env deno --unstable-net run --allow-all
import "jsr:@std/dotenv/load";
import Anthropic from "npm:@anthropic-ai/sdk";
import { generateResponse } from "./agent.ts";
import { OSCHandler } from "./ableton.ts";
const abletonPort = 11000;
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

let webSocket: WebSocket | undefined;

// UDP listener on port 110001
const udpSocket = Deno.listenDatagram({ port: localOscPort, transport: "udp" });
const oscHandler = new OSCHandler(udpSocket);
const isLive = await oscHandler.isLive();
console.log("OSC WORKING?", isLive);

// Handle incoming messages from WebSocket
async function handleWebSocketMessage(event: MessageEvent) {
  const userMessage: Anthropic.MessageParam = {
    role: "user",
    content: event.data,
  };
  messages.push(userMessage);

  let continueLoop = true;
  while (continueLoop) {
    try {
      const stream = anthropic.messages.stream({
        messages,
        model: "claude-3-5-sonnet-20241022",
        system:
          "You are a music producer controlling Ableton Live. Use the tools available to respond to the user as best as possible. It's critical you respond in exclusively lower case.",
        max_tokens: 2048,
        tools,
      });

      stream.on("text", (textDelta) => {
        console.log("[Text Chunk]", textDelta);
        webSocket?.send(JSON.stringify(textDelta));
      });

      stream.on("end", () => {
        console.log("|END_MESSAGE|");
        webSocket?.send("<|END_MESSAGE|>");
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
        webSocket?.send(`Error: ${error.message}`);
      }
      continueLoop = false;
    }
  }
}

const headers = new Headers({
  "Access-Control-Allow-Origin": "*",
});

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

    const { socket: _socket, response } = Deno.upgradeWebSocket(req);
    webSocket = _socket;

    webSocket.addEventListener("message", handleWebSocketMessage);
    return response;
  }
);
