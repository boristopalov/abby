from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
from prompts import SYNTH_PROMPT
import pathlib
from typing import Optional


# Load environment variables from a .env file
load_dotenv()

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
            system_instruction=SYNTH_PROMPT
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