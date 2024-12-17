import Anthropic from "npm:@anthropic-ai/sdk";

export const ABLETON_HISTORY_WINDOW = 10 * 60 * 1000 * 3; // 30m

export const analysisMessage = (
  changesSummary: string
): Anthropic.MessageParam => {
  return {
    role: "user",
    content: `Below are the recent parameter changes I've made in Ableton. Please analyze them and provide feedback or suggestions for improvement (if any- be somewhat conservative with your suggestions.):
 
 ${changesSummary}
 
 For each suggestion:
 1. Explain the reasoning
 2. List the exact parameter changes you'd make (including track, device, parameter, and specific values)
 3. Make sure the suggested change is within the valid range of the parameter
 4. Mark the end of each suggestion with [SUGGESTION]
 
 Example format:
 "I suggest reducing the reverb decay to create more space in the mix:
 Track: Synth Lead
 Device: Reverb
 Parameter: Decay Time
 4.2s → 2.1s
 [SUGGESTION]"`,
  };
};
