import sounddevice as sd
import numpy as np
from numpy.typing import NDArray
from scipy.io import wavfile
import os
import tempfile
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass
from logger import logger

AUDIO_DIR = "audio"

@dataclass
class AudioCapture:
    """Container for captured audio data"""
    samples: NDArray  # The raw audio samples
    sample_rate: int  # Sample rate in Hz
    wav_path: Optional[Path]  # Path to WAV file if saved
    channels: list[int]  # List of channel indices included

class AudioDeviceReader:
    def __init__(self, audio_dir: str = "audio"):
        """Initialize audio device reader"""
        self.audio_dir = audio_dir
        os.makedirs(audio_dir, exist_ok=True)
        
    def find_device_by_name(self, name: str) -> Optional[int]:
        """Find audio device by name and return its ID"""
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if name in device['name']:
                return i
        return None
    
    def get_device_channel_count(self, device_id: int) -> int:
        """Get the number of input channels for a device"""
        device_info = sd.query_devices(device_id)
        return int(device_info['max_input_channels'])
    
    def capture_audio(
        self,
        device_name: str,
        duration: float = 10,
        samplerate: int = 44100,
        channels: Optional[Union[int, list[int]]] = None,
        save_wav: bool = True,
        delete_wav: bool = True
    ) -> Optional[AudioCapture]:
        """
        Capture audio from specified device and channels
        
        Args:
            device_name: Name of the audio device to capture from
            duration: Recording duration in seconds
            samplerate: Sample rate in Hz
            channels: Optional channel selection:
                - None: record all available channels
                - int: record single channel
                - list[int]: record multiple specific channels
            save_wav: Whether to save the audio as a WAV file
            delete_wav: Whether to delete the WAV file after the program exits
            
        Returns:
            AudioCapture object containing the recorded data and metadata
        """
        device_id = self.find_device_by_name(device_name)
        if device_id is None:
            logger.info(f"Device '{device_name}' not found!")
            return None
        
        logger.info(f"Recording from device: {device_name} (ID: {device_id})...")
        
        # Get device info and channel count
        max_channels = self.get_device_channel_count(device_id)
        logger.info(f"Device has {max_channels} input channels")
        
        # Record all channels first
        recording = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=max_channels,
            dtype=np.float32,
            device=device_id
        )
        sd.wait()  # Wait until recording is finished
        
        # Handle channel selection
        selected_channels = list(range(max_channels))  # Default to all channels
        if channels is not None:
            if isinstance(channels, int):
                if 0 <= channels < max_channels:
                    recording = recording[:, channels:channels+1]  # Keep 2D shape
                    selected_channels = [channels]
                else:
                    raise ValueError(f"Channel {channels} is out of range (0-{max_channels-1})")
            elif isinstance(channels, list):
                if all(0 <= ch < max_channels for ch in channels):
                    recording = recording[:, channels]
                    selected_channels = channels
                else:
                    raise ValueError(f"One or more channels in {channels} are out of range (0-{max_channels-1})")
        
        logger.info(f"Recording complete. Data shape: {recording.shape}")
        logger.info(f"Data type: {recording.dtype}")
        logger.info(f"Max value: {np.max(np.abs(recording))}")
        
        # Save WAV file if requested
        wav_path = None
        if save_wav:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=delete_wav, dir=self.audio_dir) as temp_wav_file:
                # Convert float32 to int16
                audio_data_int = (recording * 32767).astype(np.int16)
                # Save to file
                wav_path = Path(temp_wav_file.name)
                wavfile.write(wav_path, samplerate, audio_data_int)
                logger.info(f"Saved recording to: {wav_path}")
        
        return AudioCapture(
            samples=recording,
            sample_rate=samplerate,
            wav_path=wav_path,
            channels=selected_channels
        )