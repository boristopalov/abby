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

TRIBAL_SCIFI_TECHNO = "Tribal Sci-fi Techno"

GENRE_SYSTEM_PROMPTS = {
    TRIBAL_SCIFI_TECHNO: """
Key Ableton devices:
- Operator for tribal percussion synthesis
- Wavetable for sci-fi atmospheres
- Echo for tribal delay patterns
- Corpus for metallic resonances
- Drum Rack for layered percussion

Essential device chains:
1. Tribal Bass: Operator > Saturator > Auto Filter
2. Sci-fi Pads: Wavetable > Chorus > Echo
3. Tech Percussion: Drum Rack > Corpus > Erosion

Audio effect racks:
1. Tribal Space: Echo > Reverb > Utility
2. Future Distortion: Saturator > Amp > Cabinet
3. Metallic Resonator: Corpus > Frequency Shifter > Auto Pan

Mixing guidelines:
- Keep kick drum centered and prominent
- Pan tribal elements wide
- Use sends for sci-fi atmospheres
- Maintain clear separation between percussion and pads

Processing techniques:
- Use frequency shifting for metallic textures
- Apply tribal-inspired delay patterns
- Create evolving sci-fi textures with automation
- Layer organic and synthetic percussion

Remember to:
- Balance tribal and futuristic elements
- Maintain driving techno rhythm
- Create contrast between organic and synthetic sounds
- Use automation for evolving textures
- Keep arrangement dynamic and engaging
"""
} 

def format_prompt(genre, bpm, llm_generated_description, formatted_audio_analysis, existing_devices, user_prompt):
  return f"""
    Genre: {genre}
    Project BPM: {bpm}
    Track Description: {llm_generated_description}
    Audio Analysis: {formatted_audio_analysis}
    Existing Devices: {existing_devices}
    User Request: {user_prompt}
    """