from pathlib import Path
from typing import Optional, List
import tempfile
from scipy.io import wavfile
import numpy as np
from dataclasses import dataclass

from librosa_analyzer import AudioAnalyzer, format_analysis_for_llm, SpectralFeatures, TemporalFeatures, DynamicFeatures
from llm_analyzer import LLMAnalyzer
from audio_device_reader import AudioDeviceReader, AudioCapture


@dataclass
class LibrosaAnalysis:
    """Container for librosa-based audio analysis"""
    spectral: SpectralFeatures
    temporal: TemporalFeatures
    dynamic: DynamicFeatures
    duration: float
    description: str


@dataclass
class ChannelAnalysis:
    """Analysis results for a single audio channel"""
    channel_index: int
    librosa_analysis: LibrosaAnalysis
    llm_analysis: Optional[str] = None  # LLM-generated string describing the audio
    llm_error: Optional[str] = None


@dataclass
class AudioAnalysisResult:
    """Complete analysis results for all channels"""
    channels: List[ChannelAnalysis]
    sample_rate: int
    device_name: str
    
    def get_channel(self, index: int) -> Optional[ChannelAnalysis]:
        """Get analysis for a specific channel"""
        for channel in self.channels:
            if channel.channel_index == index:
                return channel
        return None


def analyze_channels(
    capture: AudioCapture, 
    audio_analyzer: AudioAnalyzer,
    llm_analyzer: Optional[LLMAnalyzer] = None
) -> AudioAnalysisResult:
    """
    Analyze each channel in the captured audio
    
    Args:
        capture: AudioCapture object containing the recorded data
        audio_analyzer: AudioAnalyzer instance for signal processing
        llm_analyzer: Optional LLMAnalyzer instance for AI analysis
        
    Returns:
        AudioAnalysisResult containing analysis for all channels
    """
    channel_analyses: List[ChannelAnalysis] = []
    
    print(f"\nAnalyzing {len(capture.channels)} channels...")
    
    # For each channel in the recording
    for i, ch_idx in enumerate(capture.channels):
        print(f"\n=== Analyzing Channel {ch_idx} ===")
        
        # Extract single channel and save as temp WAV
        channel_data = capture.samples[:, i]
        
        # Get signal processing analysis
        librosa_results = audio_analyzer.analyze_audio(channel_data)
        description = format_analysis_for_llm(librosa_results)
        
        librosa_analysis = LibrosaAnalysis(
            spectral=librosa_results["spectral"],
            temporal=librosa_results["temporal"],
            dynamic=librosa_results["dynamic"],
            duration=librosa_results["duration"],
            description=description
        )
        
        # Add LLM analysis if requested
        llm_result = None
        llm_error = None
        if llm_analyzer:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav:
                channel_path = Path(temp_wav.name)
                wavfile.write(channel_path, capture.sample_rate, (channel_data * 32767).astype(np.int16))
                
                try:
                    llm_result = llm_analyzer.analyze_audio(channel_path.read_bytes())
                except Exception as e:
                    llm_error = str(e)
        
        channel_analysis = ChannelAnalysis(
            channel_index=ch_idx,
            librosa_analysis=librosa_analysis,
            llm_analysis=llm_result,
            llm_error=llm_error
        )
        channel_analyses.append(channel_analysis)
            
        # Print results
        print("\nSignal Analysis:")
        print(librosa_analysis.description)
        
        if llm_analyzer:
            print("\nLLM Analysis:")
            if llm_result:
                print(llm_result)
            elif llm_error:
                print(f"Error during LLM analysis: {llm_error}")
    
    return AudioAnalysisResult(
        channels=channel_analyses,
        sample_rate=capture.sample_rate,
        device_name=capture.device_name if hasattr(capture, 'device_name') else "unknown"
    )


def main():
    # Initialize components
    reader = AudioDeviceReader()
    audio_analyzer = AudioAnalyzer()
    llm_analyzer = LLMAnalyzer()
    
    # Example: Capture audio from BlackHole device
    print("\nCapturing audio from BlackHole...")
    capture = reader.capture_audio(
        device_name="BlackHole 16ch",
        channels=[0, 1],  # Only capture first two channels
        duration=10
    )

    if capture:
        # Analyze the captured audio
        results = analyze_channels(capture, audio_analyzer, llm_analyzer)
        
        # Example: Access results for a specific channel
        ch0 = results.get_channel(0)
        if ch0:
            print("\nChannel 0 Analysis Results:")
            print(f"Spectral Centroid: {ch0.librosa_analysis.spectral.centroid:.1f} Hz")
            print(f"Temporal Onsets: {ch0.librosa_analysis.temporal.onset_count}")
            if ch0.llm_analysis:
                print(f"LLM Analysis: {ch0.llm_analysis}...")
    
if __name__ == "__main__":
    main() 