import re
from typing import Tuple
from ..core.context import get_context
from ..core.prompts import GENRE_SYSTEM_PROMPTS

GENRE_PROMPT = """Create a new weird, niche, experimental music genre system prompt. The prompt should:

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
PROMPT: \"\"\"
your detailed prompt here
\"\"\"

Be creative but practical - the genre should be technically implementable in Ableton Live."""

async def generate_random_genre() -> Tuple[str, str]:
    try:
        context = get_context()
        response = await context.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            messages=[{"role": "user", "content": GENRE_PROMPT}]
        )

        content = response.content[0].text if response.content[0].type == "text" else ""

        genre_match = re.search(r'GENRE_NAME:\s*"([^"]+)"', content)
        prompt_match = re.search(r'PROMPT:\s*"""\n([\s\S]+?)"""', content)

        if not genre_match or not prompt_match:
            raise ValueError("Failed to parse genre response")

        genre_name = genre_match.group(1)
        prompt = prompt_match.group(1).strip()

        # Add the new genre to the GENRE_SYSTEM_PROMPTS
        GENRE_SYSTEM_PROMPTS[genre_name] = prompt
        
        return genre_name, prompt
    except Exception as e:
        print("Error generating random genre:", str(e))
        raise 