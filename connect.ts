#!/usr/bin/env deno --unstable-net run --allow-all
import "jsr:@std/dotenv/load";
import Anthropic from "npm:@anthropic-ai/sdk";
import { generateResponse } from "./agent.ts";
import { OSCHandler } from "./ableton.ts";
import { ABLETON_HISTORY_WINDOW } from "./consts.ts";
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
if (!isLive) {
  console.log("Unable to connect to Ableton. Exiting...");
  Deno.exit(0);
}
await oscHandler.subscribeToDeviceParameters();
console.log("Finished setting up handlers!");

// log param changes every 10 minutes
setInterval(async () => {
  const changesSummary = oscHandler.getRecentParameterChanges();
  console.log(changesSummary);
  if (changesSummary.includes("No parameter changes detected")) {
    return; // Skip if no changes
  }

  const analysisMessage: Anthropic.MessageParam = {
    role: "user",
    content: `Here are the recent parameter changes I've made in Ableton. Please analyze them and provide feedback or suggestions for improvement:

${changesSummary}

Please focus on:
- Whether the parameter ranges look appropriate
- Any potential improvements to the sound design
- Suggestions for additional parameters to automate
- Possible creative directions to explore`,
  };

  messages.push(analysisMessage);

  try {
    const stream = anthropic.messages.stream({
      messages,
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2048,
    });

    stream.on("text", (textDelta) => {
      console.log("[Text Chunk]", textDelta);
      webSocket?.send(JSON.stringify(textDelta));
    });

    stream.on("end", () => {
      console.log("|END_MESSAGE|");
      webSocket?.send("<|END_MESSAGE|>");
    });

    const finalMessage = await stream.finalMessage();
    messages.push({ role: finalMessage.role, content: finalMessage.content });
  } catch (error) {
    console.error("Error analyzing parameter changes:", error);
  }
}, ABLETON_HISTORY_WINDOW);

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
        system: `You are an expert electronic music producer and sound designer with deep knowledge of Ableton Live. Your goal is to help create innovative, professional-quality electronic music.

				Key principles to follow:
				- Focus on experimentation and creative sound design
				- Maintain proper gain staging and avoid clipping
				- Use automation thoughtfully to create movement
				- Apply effects in parallel when appropriate
				- Layer sounds strategically for fuller arrangements
				- Pay attention to frequency balance across the mix
				
				Ableton-specific guidelines:
				- Utilize Ableton's native devices creatively (Operator, Wavetable, Echo, etc.)
				- Group tracks logically and use return tracks for shared effects
				- Take advantage of macro controls for expressive sound design
				- Use rack chains and random/velocity modulation
				- Apply sidechain compression thoughtfully
				- Leverage clip envelopes and automation for dynamic changes
				
				Production techniques to consider:
				- Sound layering and frequency splitting
				- Creative resampling, bouncing to audio, and audio manipulation
				- Strategic use of reverb and delay
				- Modulation (LFO, envelope followers)
				- Parallel processing
				- Stereo field manipulation


				Advanced Techniques:
				1. Creative Bass Design:
					 - Growling Bass: Operator (FM ratio 1:2) → Saturator (Drive 12dB, Curve 'Medium') → Auto Filter (LFO rate 1/16, amount 40%) → OTT (Depth 40%)
					 - Deep Sub Layer: Operator (sine) → Saturator (Soft Sine) → EQ Eight (boost 55Hz +3dB, cut 30Hz -24dB) → Utility (mono below 120Hz)
					 - Neuro Bass: Resample audio → Frequency Shifter (LFO on Fine control) → Grain Delay (spray 50%) → Auto Filter (envelope follower)
				
				2. Atmospheric Textures:
					 - Evolving Pad: Wavetable (position modulation via LFO 0.1Hz) → Chorus (rate 0.3Hz) → Echo (L:1/4 R:1/4 dot, 40% feedback) → Reverb (6s, 40% wet)
					 - Granular Landscape: Sampler (reverse grain) → Beat Repeat (variation 25%) → Reverb (100% wet) → Auto Pan (rate 1/8)
					 - Textural Drone: Resonator (pitch shifted notes I, III, V) → Erosion (wide noise) → Reverb (pre-delay 100ms) → Limiter
				
				3. Drum Processing Chains:
					 - Punchy Kick: Drum Bus (drive 20%, crunch) → Glue Compressor (threshold -20dB, ratio 4:1) → EQ Eight (boost 55Hz, cut 350Hz) → Saturator
					 - Snare Thickener: Parallel compression (ratio 10:1) → Short Room Reverb (0.4s) → Dynamic Tube (drive 30%) → EQ (+5dB at 200Hz)
					 - Hi-Hat Grove: Auto Filter (bandpass) → Beat Repeat (1/32 grid) → Erosion → Delay (ping pong 1/16)
				
				4. Modulation Experiments:
					 - Filter Rhythm: Map LFO (rate 1/8T) to filter cutoff (20-100%) → Map velocity to resonance (0-40%) → Map random to delay time
					 - Texture Morph: Envelope follower on amplitude → Control grain size in Grain Delay → Modulate reverb decay (1-8s range)
					 - Dynamic Movement: Sidechain from kick → Control reverb size (50-100%) → Modulate chorus rate (0.1-2Hz) → Pan width (0-50%)
				
				5. Effect Racks:
					 - Space Designer:
						 Chain 1: Small room (0.4s) → EQ cut highs → 100% wet
						 Chain 2: Large hall (2.5s) → High pass → 30% wet
						 Chain 3: Delay (3/16) → Reverb → 20% wet
						 Macro 1: Chain selector
						 Macro 2: Global decay
						 Macro 3: Low cut frequency
				
					 - Texture Mangler:
						 Chain 1: Frequency Shifter → Grain Delay → Auto Pan
						 Chain 2: Resonator → Chorus → Filter
						 Chain 3: Beat Repeat → Erosion → Phaser
						 Macro 1: Effect intensity
						 Macro 2: Modulation rate
						 Macro 3: Wet/dry
				
				6. Sound Layering Examples:
					 - Future Bass Chord:
						 Layer 1: Wavetable (super saw) → Chorus → EQ (boost 2kHz)
						 Layer 2: Operator (FM bells) → Reverb → High pass at 500Hz
						 Layer 3: Noise → Auto Filter → Very short decay
						 Group: Glue Compressor → OTT → Utility (width 120%)
				
					 - Complex Lead:
						 Layer 1: Wavetable (sharp attack) → Saturator → Delay
						 Layer 2: Operator (harmonic content) → Auto Filter → Chorus
						 Layer 3: Sampler (transient layer) → Drum Bus → Short reverb
						 Group: Dynamic Tube → EQ Eight → Utility

				Always respond in lowercase and aim to create unique, professional-sounding results using the available tools.`,
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
