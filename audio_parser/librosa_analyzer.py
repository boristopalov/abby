import librosa
import numpy as np
from dataclasses import dataclass
from typing import List, Dict
from logger import logger

@dataclass
class SpectralFeatures:
    centroid: float  # Brightness of the sound
    bandwidth: float  # Width of the frequency distribution
    rolloff: float   # Frequency below which 85% of energy exists
    peaks: List[float]  # Main frequency peaks (currently top 5)
    flatness: float  # How noise-like vs. tonal the sound is
    harmonic_percussive_ratio: float   # Ratio of harmonic to percussive energy

@dataclass
class TemporalFeatures:
    onset_count: int           # Number of detected onsets
    onset_density: float       # Onsets per second
    first_onset: float        # Time of first onset
    mean_onset_strength: float # Average strength of onsets

@dataclass
class DynamicFeatures:
    rms: float      # Root mean square energy
    peak: float     # Peak amplitude
    crest_factor: float  # Peak to RMS ratio
    dynamic_range: float # Difference between peak and valley

EPSILON = 1e-8  # Small value to prevent division by zero
SILENCE_THRESHOLD = -60  # dB threshold for silence detection

def is_silent(y: np.ndarray) -> bool:
    """Check if audio is effectively silent"""
    if len(y) == 0:
        return True
        
    # Convert to dB
    db = 20 * np.log10(np.abs(y).mean() + EPSILON)
    return db < SILENCE_THRESHOLD

class AudioAnalyzer:
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        logger.info(f"Initialized AudioAnalyzer with sample rate {sample_rate} Hz")
        
    def analyze_audio(self, y: np.ndarray) -> Dict:
        """
        Analyze audio signal and return comprehensive feature set
        """
        logger.info(f"Analyzing audio data of shape {y.shape}")
        
        # Check for silence first
        if is_silent(y):
            logger.info("Audio signal is silent")
            return {
                "spectral": SpectralFeatures(
                    centroid=0.0,
                    bandwidth=0.0,
                    rolloff=0.0,
                    peaks=[],
                    flatness=1.0,  # Perfect flatness for silence
                    harmonic_percussive_ratio=0.0
                ),
                "temporal": TemporalFeatures(
                    onset_count=0,
                    onset_density=0.0,
                    first_onset=0.0,
                    mean_onset_strength=0.0
                ),
                "dynamic": DynamicFeatures(
                    rms=0.0,
                    peak=0.0,
                    crest_factor=0.0,
                    dynamic_range=0.0
                ),
                "duration": len(y) / self.sr,
                "is_silent": True
            }
        
        spectral = self._analyze_spectral(y)
        temporal = self._analyze_temporal(y)
        dynamic = self._analyze_dynamics(y)
        
        return {
            "spectral": spectral,
            "temporal": temporal,
            "dynamic": dynamic,
            "duration": len(y) / self.sr,
            "is_silent": False
        }
    
    def _analyze_spectral(self, y: np.ndarray) -> SpectralFeatures:
        """Extract spectral features from the audio"""
        logger.debug("Analyzing spectral features")
        
        # Compute spectrogram
        D = librosa.stft(y)
        S = np.abs(D)
        
        # Compute spectral features with error handling
        try:
            centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=self.sr)))
        except Exception as e:
            logger.warning(f"Error computing spectral centroid: {e}")
            centroid = 0.0
            
        try:
            bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=self.sr)))
        except Exception as e:
            logger.warning(f"Error computing spectral bandwidth: {e}")
            bandwidth = 0.0
            
        try:
            rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=self.sr)))
        except Exception as e:
            logger.warning(f"Error computing spectral rolloff: {e}")
            rolloff = 0.0
            
        try:
            flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        except Exception as e:
            logger.warning(f"Error computing spectral flatness: {e}")
            flatness = 0.0
        
        # Find main frequency peaks with error handling
        try:
            freqs = librosa.fft_frequencies(sr=self.sr)
            magnitude_spectrum = np.abs(librosa.stft(y))
            mean_spectrum = np.mean(magnitude_spectrum, axis=1)
            peak_indices = librosa.util.peak_pick(mean_spectrum, 
                                                pre_max=20, 
                                                post_max=20, 
                                                pre_avg=20, 
                                                post_avg=20, 
                                                delta=0.1, 
                                                wait=20)
            peaks = [freqs[i] for i in peak_indices][:5]  # Get top 5 peaks
        except Exception as e:
            logger.warning(f"Error finding frequency peaks: {e}")
            peaks = []

        # Calculate harmonic/percussive ratio with error handling
        try:
            harmonic, percussive = librosa.effects.hpss(y)
            h_energy = np.sum(harmonic ** 2)
            p_energy = np.sum(percussive ** 2)
            hp_ratio = float(h_energy / (p_energy + EPSILON))
        except Exception as e:
            logger.warning(f"Error computing harmonic/percussive ratio: {e}")
            hp_ratio = 0.0

        return SpectralFeatures(
            centroid=centroid,
            bandwidth=bandwidth,
            rolloff=rolloff,
            peaks=peaks,
            flatness=flatness,
            harmonic_percussive_ratio=hp_ratio
        )
    
    def _analyze_temporal(self, y: np.ndarray) -> TemporalFeatures:
        """Extract temporal features from the audio"""
        logger.debug("Analyzing temporal features")
        
        try:
            # Onset detection
            onset_env = librosa.onset.onset_strength(y=y, sr=self.sr)
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=self.sr)
            onset_times = librosa.frames_to_time(onset_frames, sr=self.sr)
            
            # Calculate summary statistics
            duration = len(y) / self.sr
            onset_count = len(onset_times)
            onset_density = onset_count / (duration + EPSILON)
            first_onset = onset_times[0] if onset_count > 0 else 0.0
            mean_onset_strength = float(np.mean(onset_env))
            
        except Exception as e:
            logger.warning(f"Error in temporal analysis: {e}")
            onset_count = 0
            onset_density = 0.0
            first_onset = 0.0
            mean_onset_strength = 0.0
            
        return TemporalFeatures(
            onset_count=onset_count,
            onset_density=onset_density,
            first_onset=first_onset,
            mean_onset_strength=mean_onset_strength
        )
    
    def _analyze_dynamics(self, y: np.ndarray) -> DynamicFeatures:
        """Extract dynamic features from the audio"""
        logger.debug("Analyzing dynamic features")
        
        try:
            rms = float(np.sqrt(np.mean(y**2)))
            peak = float(np.max(np.abs(y)))
            crest_factor = peak / (rms + EPSILON)
            dynamic_range = 20 * np.log10((peak + EPSILON) / (rms + EPSILON))
            
        except Exception as e:
            logger.warning(f"Error in dynamics analysis: {e}")
            rms = 0.0
            peak = 0.0
            crest_factor = 0.0
            dynamic_range = 0.0
            
        return DynamicFeatures(
            rms=rms,
            peak=peak,
            crest_factor=crest_factor,
            dynamic_range=dynamic_range
        )


def format_analysis_for_llm(analysis: Dict) -> str:
    """
    Convert analysis results into a natural language description
    that would be more useful for an LLM
    """
    # Check if the audio was silent
    if analysis.get("is_silent", False):
        return "The audio appears to be silent, with no significant audio content detected."
    
    spectral: SpectralFeatures = analysis['spectral']
    temporal: TemporalFeatures = analysis['temporal']
    dynamic: DynamicFeatures = analysis['dynamic']
    
    description = []
    
    # Describe spectral characteristics
    description.append(f"The sound has a spectral centroid of {spectral.centroid:.1f} Hz, "
                      f"indicating {'bright' if spectral.centroid > 3000 else 'warm' if spectral.centroid > 1000 else 'dark'} tonality.")
    
    if spectral.peaks:
        description.append(f"Main frequency peaks are at: {', '.join(f'{p:.1f} Hz' for p in spectral.peaks)}.")

    # Describe harmonic/percussive relationship
    if spectral.harmonic_percussive_ratio > 2:
        description.append(f"The sound is predominantly harmonic with {spectral.harmonic_percussive_ratio:.1f}x more harmonic than percussive energy.")
    elif spectral.harmonic_percussive_ratio < 0.5:
        description.append(f"The sound is predominantly percussive with {1/spectral.harmonic_percussive_ratio:.1f}x more percussive than harmonic energy.")
    else:
        description.append(f"The sound has a balanced harmonic/percussive ratio of {spectral.harmonic_percussive_ratio:.1f}.")
    
    # Describe temporal characteristics
    description.append(f"The sound has {temporal.onset_count} distinct onsets occurring at a rate of {temporal.onset_density:.1f} per second, "
                      f"{'suggesting a busy/rhythmic pattern' if temporal.onset_density > 4 else 'indicating a sparse/sustained texture' if temporal.onset_density < 2 else 'with moderate rhythmic activity'}. "
                      f"{'The first onset occurs at {temporal.first_onset:.3f}s, indicating a pre-delay.' if temporal.first_onset > 0.01 else 'The sound starts immediately.'} "
                      f"The onsets have {'strong' if temporal.mean_onset_strength > 0.5 else 'moderate' if temporal.mean_onset_strength > 0.2 else 'soft'} attack characteristics "
                      f"(mean strength: {temporal.mean_onset_strength:.2f}).")
    
    # Describe dynamics
    description.append(f"Dynamically, the sound {'is highly compressed' if dynamic.crest_factor < 3 else 'has natural dynamics' if dynamic.crest_factor < 6 else 'has extreme dynamics'} "
                      f"with a crest factor of {dynamic.crest_factor:.1f}. "
                      f"The RMS level is {dynamic.rms:.3f} with peaks reaching {dynamic.peak:.3f}, "
                      f"giving a dynamic range of {dynamic.dynamic_range:.1f}dB. "
                      f"{'This suggests the sound might benefit from compression.' if dynamic.crest_factor > 8 else ''}"
                      f"{'The low crest factor indicates the sound is already heavily compressed.' if dynamic.crest_factor < 2 else ''}")
    
    return " ".join(description)

# Example usage:
if __name__ == "__main__":
    # Load an audio file
    audio_path = "your_audio.wav"
    y, sr = librosa.load(audio_path)
    
    # Create analyzer and get results
    analyzer = AudioAnalyzer(sr)
    analysis = analyzer.analyze_audio(y)
    
    # Get formatted description for LLM
    description = format_analysis_for_llm(analysis)
    print(description)