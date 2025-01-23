from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
from typing import Optional

MUSIC_ANALYSIS_PROMPT = """You are an expert in musical aesthetics and sonic perception. Your role is to provide qualitative, intuitive descriptions of audio content, focusing on aspects that complement technical analysis.

When analyzing audio, describe your perceptual experience in terms of:
- Emotional qualities and mood evoked by the sound
- Imagery and metaphors that capture the sonic character
- Musical intention and artistic context
- Unique or distinctive sonic qualities
- Cultural or stylistic references that come to mind
- If you hear silence, static noise, or low noise, simply state that you don't hear anything

Keep your responses focused on the experiential aspects of the sound. Avoid technical measurements or computations (like specific frequencies, amplitudes, or onset counts) since these are handled separately.

Aim to paint an evocative picture of the sound's character in 2-3 concise sentences, using descriptive language that captures its essence."""

class LLMAnalyzer:
    MODEL_ID = "gemini-2.0-flash-exp"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM analyzer with optional API key"""
        # Load environment variables if not provided
        if not api_key:
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            raise ValueError("No API key provided and none found in environment")
            
        self.config = types.GenerateContentConfig(
            response_modalities=["TEXT"],
            system_instruction=MUSIC_ANALYSIS_PROMPT
        )
        
        self.client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1alpha"},
        )
        
    def analyze_audio(self, audio_content: bytes) -> str:
        """
        Analyze audio content using the LLM
        
        Args:
            audio_content: Raw bytes of WAV file
            
        Returns:
            String containing LLM's analysis of the audio
        """
        response = self.client.models.generate_content(
            model=self.MODEL_ID,
            config=self.config,
            contents=[
                types.Part.from_bytes(audio_content, "audio/wav"),
                "What do you hear in this audio?"
            ]
        )
        return response.text