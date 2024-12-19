import { GENRE_SYSTEM_PROMPTS } from "./prompts.ts";
import { context } from "./context.ts";

const GENRE_PROMPT = `Create a new weird, niche, experimental music genre system prompt. The prompt should:

1. Have a unique genre name that combines 2-3 musical styles or concepts
2. Include detailed Ableton Live device chains with specific parameter values
3. Follow this structure:
   - Key ableton devices to use
   - Essential device chains
   - Audio effect racks
   - Mixing guidelines
   - Processing techniques
   - Remember to/guidelines section

Format the response as:
GENRE_NAME: "your genre name here"
PROMPT: """
your detailed prompt here
"""

Be creative but practical - the genre should be technically implementable in Ableton Live.`;

export async function generateRandomGenre() {
  try {
    const response = await context.anthropic.messages.create({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2048,
      messages: [{ role: "user", content: GENRE_PROMPT }],
    });

    // Handle the content properly based on the response type
    const content =
      response.content[0].type === "text" ? response.content[0].text : "";

    const genreMatch = content.match(/GENRE_NAME:\s*"([^"]+)"/);
    const promptMatch = content.match(/PROMPT:\s*"""\n([\s\S]+?)"""/);

    if (!genreMatch || !promptMatch) {
      throw new Error("Failed to parse genre response");
    }

    const genreName = genreMatch[1];
    const prompt = promptMatch[1].trim();

    // Add the new genre to the GENRE_SYSTEM_PROMPTS
    GENRE_SYSTEM_PROMPTS[genreName] = prompt;
    return {
      genreName,
      prompt,
    };
  } catch (error) {
    console.error("Error generating random genre:", error);
    throw error;
  }
}
