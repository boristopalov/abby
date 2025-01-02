import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
from numpy.typing import NDArray
from prompts import SYNTH_PROMPT
import pathlib


# Load environment variables from a .env file
load_dotenv()

MODEL_ID = "gemini-2.0-flash-exp"
CONFIG = types.GenerateContentConfig(
    response_modalities=["TEXT"],
    system_instruction=SYNTH_PROMPT
)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={"api_version": "v1alpha"},
)


def complete_with_audio(audio_content: bytes) -> str:
  response = client.models.generate_content(
     model=MODEL_ID, 
     config=CONFIG, 
     contents=[types.Part.from_bytes(audio_content, "audio/wav"), "What do you hear in this audio?"]
  )
  return response.text

if __name__ == "__main__":
    path = "./audio/tmpmhoed03x.wav"
    audio_data = pathlib.Path(path).read_bytes()
    print(complete_with_audio(audio_data))
