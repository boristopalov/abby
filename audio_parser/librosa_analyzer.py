import librosa
import numpy as np
from dataclasses import dataclass
from typing import List, Dict

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

class AudioAnalyzer:
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        
    def analyze_audio(self, y: np.ndarray) -> Dict:
        """
        Analyze audio signal and return comprehensive feature set
        """
        spectral = self._analyze_spectral(y)
        temporal = self._analyze_temporal(y)
        dynamic = self._analyze_dynamics(y)
        
        return {
            "spectral": spectral,
            "temporal": temporal,
            "dynamic": dynamic,
            "duration": len(y) / self.sr
        }
    
    def _analyze_spectral(self, y: np.ndarray) -> SpectralFeatures:
        """Extract spectral features from the audio"""
        # Compute spectrogram
        D = librosa.stft(y) # Fourier transform
        S = np.abs(D)

        
        # Compute spectral features
        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=self.sr)))
        bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=self.sr)))
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=self.sr)))
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
        
        # Find main frequency peaks
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

        """Calculate the ratio between harmonic and percussive energy"""
        harmonic, percussive = librosa.effects.hpss(y)
        h_energy = np.sum(harmonic ** 2)
        p_energy = np.sum(percussive ** 2)
        hp_ratio = float(h_energy / p_energy) if p_energy > 0 else float('inf')

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
            # Onset detection
            onset_env = librosa.onset.onset_strength(y=y, sr=self.sr)
            onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=self.sr)
            onset_times = librosa.frames_to_time(onset_frames, sr=self.sr)
            
            # Calculate summary statistics
            duration = len(y) / self.sr
            onset_count = len(onset_times)
            onset_density = onset_count / duration if duration > 0 else 0
            first_onset = onset_times[0] if onset_count > 0 else 0
            mean_onset_strength = float(np.mean(onset_env))
            
            
            return TemporalFeatures(
                onset_count=onset_count,
                onset_density=onset_density,
                first_onset=first_onset,
                mean_onset_strength=mean_onset_strength
            )

    
    def _analyze_dynamics(self, y: np.ndarray) -> DynamicFeatures:
        """Extract dynamic features from the audio"""
        rms = float(np.sqrt(np.mean(y**2)))
        peak = float(np.max(np.abs(y)))
        crest_factor = peak / (rms + 1e-8)  # Add small epsilon to avoid division by zero
        dynamic_range = 20 * np.log10(peak / (rms + 1e-8))  # In dB
        
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