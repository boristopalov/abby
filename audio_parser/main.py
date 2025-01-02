import sounddevice as sd
import numpy as np
from numpy.typing import NDArray
import io
from scipy.io import wavfile
import requests
import os
import tempfile

AUDIO_DIR = "audio"
def find_device_by_name(name: str):
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if name in device['name']:
            return i
    return None

def capture_audio(duration=5, samplerate=44100, delete=True) -> NDArray:
    device_id = find_device_by_name("BlackHole 16ch")
    if device_id is None:
        print("BlackHole device not found!")
        return
    
    print(f"Recording from BlackHole device (ID: {device_id})...")
    
    # Get device info
    device_info = sd.query_devices(device_id)
    print(f"Device info: {device_info}")
    
    recording = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=2,  # BlackHole 16ch
        dtype=np.float32,
        device=device_id
    )
    sd.wait()  # Wait until recording is finished
    
    print(f"Recording complete. Data shape: {recording.shape}")
    print(f"Data type: {recording.dtype}")
    print(f"Max value: {np.max(np.abs(recording))}")
    
    # Generate filename with timestamp
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=delete, dir=AUDIO_DIR) as temp_wav_file:
        # Convert float32 to int16
        audio_data_int = (recording * 32767).astype(np.int16)
        # Save to file
        wavfile.write(temp_wav_file, samplerate, audio_data_int)
        print(f"Saved recording to: {temp_wav_file.name}")
    
    return recording


def main():
    print(f"\nCreating dir {AUDIO_DIR}")
    os.makedirs(AUDIO_DIR, exist_ok=True)
    print("\nAttempting to record audio...")
    audio_data = capture_audio(delete=False)
    if audio_data is not None:
        print(f"\nRecording complete! Shape: {audio_data.shape}")
        print(f"Max amplitude: {np.max(np.abs(audio_data))}")
        
        # Example of sending to model (uncomment and modify when needed)
        # response = send_audio_to_model(
        #     audio_data,
        #     api_url="your-api-url",
        #     api_key="your-api-key"
        # )
        # print(response)

if __name__ == "__main__":
    main()
    

