import Anthropic from "npm:@anthropic-ai/sdk";

export const ABLETON_HISTORY_WINDOW = 10 * 60 * 1000 * 3; // 30m
export const LOCAL_OSC_PORT = 11001;
export const WEBSOCKET_PORT = 8000;

export const analysisMessage = (
  changesSummary: string
): Anthropic.MessageParam => {
  return {
    role: "user",
    content: `Below are the recent parameter changes I've made in Ableton. Please analyze them and provide feedback or suggestions for improvement:
 
 ${changesSummary}
 
 For each suggestion:
 1. Explain the reasoning
 2. List the exact parameter changes you'd make (including track, device, parameter, and specific values)
 3. Make sure the suggested change is within the valid range of the parameter

 You may also provide suggestions on other tracks/devices, which you can query through the get_tracks_devices tool.
`,
  };
};
