from pathlib import Path
from typing import Optional, List
import tempfile
from scipy.io import wavfile
import numpy as np
from dataclasses import dataclass
import concurrent.futures
from logger import logger

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


def analyze_single_channel(
    channel_data: np.ndarray,
    channel_idx: int,
    sample_rate: int,
    audio_analyzer: AudioAnalyzer,
    llm_analyzer: Optional[LLMAnalyzer] = None
) -> ChannelAnalysis:
    """
    Analyze a single audio channel with parallel processing of librosa and LLM analysis
    
    Args:
        channel_data: Audio samples for this channel
        channel_idx: Index of this channel
        sample_rate: Sample rate of the audio
        audio_analyzer: AudioAnalyzer instance
        llm_analyzer: Optional LLMAnalyzer instance
        
    Returns:
        ChannelAnalysis for this channel
    """
    logger.info(f"Analyzing channel {channel_idx}")
    
    # Create thread pool for parallel analysis
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Submit librosa analysis
        librosa_future = executor.submit(audio_analyzer.analyze_audio, channel_data)
        
        # Submit LLM analysis if requested
        llm_future = None
        if llm_analyzer:
            # Create WAV file for LLM analysis
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav:
                channel_path = Path(temp_wav.name)
                wavfile.write(channel_path, sample_rate, (channel_data * 32767).astype(np.int16))
                audio_bytes = channel_path.read_bytes()
                llm_future = executor.submit(llm_analyzer.analyze_audio, audio_bytes)
        
        # Wait for librosa analysis and create description
        try:
            librosa_results = librosa_future.result()
            description = format_analysis_for_llm(librosa_results)
            librosa_analysis = LibrosaAnalysis(
                spectral=librosa_results["spectral"],
                temporal=librosa_results["temporal"],
                dynamic=librosa_results["dynamic"],
                duration=librosa_results["duration"],
                description=description
            )
        except Exception as e:
            logger.error(f"Error in librosa analysis for channel {channel_idx}: {e}")
            librosa_analysis = None
        
        # Wait for LLM analysis if it was requested
        llm_result = None
        llm_error = None
        if llm_future:
            try:
                llm_result = llm_future.result()
            except Exception as e:
                llm_error = str(e)
                logger.error(f"Error in LLM analysis for channel {channel_idx}: {e}")
    
    channel_analysis = ChannelAnalysis(
        channel_index=channel_idx,
        librosa_analysis=librosa_analysis,
        llm_analysis=llm_result,
        llm_error=llm_error
    )
    
    # Print results
    logger.info(f"\n=== Channel {channel_idx} Analysis ===")
    if librosa_analysis:
        logger.info("\nSignal Analysis:")
        logger.info(librosa_analysis.description)
    
    if llm_analyzer:
        logger.info("\nLLM Analysis:")
        if llm_result:
            logger.info(llm_result)
        elif llm_error:
            logger.info(f"Error during LLM analysis: {llm_error}")
            
    return channel_analysis


def analyze_channels(
    capture: AudioCapture, 
    audio_analyzer: AudioAnalyzer,
    llm_analyzer: Optional[LLMAnalyzer] = None,
    max_workers: Optional[int] = None
) -> AudioAnalysisResult:
    """
    Analyze each channel in the captured audio in parallel
    
    Args:
        capture: AudioCapture object containing the recorded data
        audio_analyzer: AudioAnalyzer instance for signal processing
        llm_analyzer: Optional LLMAnalyzer instance for AI analysis
        max_workers: Maximum number of parallel workers (None for CPU count)
        
    Returns:
        AudioAnalysisResult containing analysis for all channels
    """
    logger.info(f"Starting parallel analysis of {len(capture.channels)} channels")
    channel_analyses: List[ChannelAnalysis] = []
    
    # Create thread pool for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all channel analysis tasks
        future_to_channel = {
            executor.submit(
                analyze_single_channel,
                capture.samples[:, i],
                ch_idx,
                capture.sample_rate,
                audio_analyzer,
                llm_analyzer
            ): ch_idx
            for i, ch_idx in enumerate(capture.channels)
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_channel):
            channel_idx = future_to_channel[future]
            try:
                channel_analysis = future.result()
                channel_analyses.append(channel_analysis)
                logger.info(f"Completed analysis of channel {channel_idx}")
            except Exception as e:
                logger.error(f"Analysis failed for channel {channel_idx}: {e}")
                # Add empty analysis for failed channel
                channel_analyses.append(ChannelAnalysis(
                    channel_index=channel_idx,
                    librosa_analysis=None,
                    llm_analysis=None,
                    llm_error=str(e)
                ))
    
    # Sort channels by index for consistent ordering
    channel_analyses.sort(key=lambda x: x.channel_index)
    
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
    logger.info("\nCapturing audio from BlackHole...")
    capture = reader.capture_audio(
        device_name="BlackHole 16ch",
        channels=[0, 1],  # Only capture first two channels
        duration=10
    )

    if capture:
        # Analyze the captured audio in parallel
        results = analyze_channels(
            capture, 
            audio_analyzer, 
            llm_analyzer,
            max_workers=None  # Use CPU count
        )
        
        # Example: Access results for a specific channel
        ch0 = results.get_channel(0)
        if ch0 and ch0.librosa_analysis:  # Check for failed analysis
            logger.info("\nChannel 0 Analysis Results:")
            logger.info(f"Spectral Centroid: {ch0.librosa_analysis.spectral.centroid:.1f} Hz")
            logger.info(f"Temporal Onsets: {ch0.librosa_analysis.temporal.onset_count}")
            if ch0.llm_analysis:
                logger.info(f"LLM Analysis: {ch0.llm_analysis}")
    
if __name__ == "__main__":
    main() 