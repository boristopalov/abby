import Anthropic from "npm:@anthropic-ai/sdk";
import { OSCHandler } from "./ableton.ts";

async function callFunction(
  oscHandler: OSCHandler,
  toolCall: Anthropic.ToolUseBlock
) {
  console.log("calling Ableton OSC function with args:", toolCall);
  const args = toolCall.input as Record<string, any>;
  switch (toolCall.name) {
    case "get_tracks_devices":
      return await oscHandler.getTracksDevices();
    case "get_device_params":
      return await oscHandler.getParameters(args.track_id, args.device_id);
    case "set_device_param":
      return await oscHandler.setParameter(
        args.track_id,
        args.device_id,
        args.param_id,
        args.value
      );
    default:
      throw new Error(
        `No function found. Received callFunction() args: ${toolCall}`
      );
  }
}

export const generateResponse = async (
  oscHandler: OSCHandler,
  tool: Anthropic.ToolUseBlock
) => {
  try {
    const result = await callFunction(oscHandler, tool);
    return {
      type: "tool_result",
      tool_use_id: tool.id,
      content: JSON.stringify(result),
      is_error: !result,
    };
  } catch (error) {
    console.error("Error using tool:", error);
    throw error;
  }
};
