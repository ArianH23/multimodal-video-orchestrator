import librosa
import numpy as np
from typing import Tuple, List
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d


def detect_drop(audio_path: str, sr: int = 22050) -> Tuple[float, List[float]]:
    """
    Detects the main drop and potential drops in a song.

    Parameters:
    -----------
    audio_path : str
        Path to the audio file
    sr : int
        Sample rate (default: 22050 Hz)

    Returns:
    --------
    main_drop_time : float
        Time in seconds of the main drop
    all_drops : List[float]
        List of all potential drop times in seconds
    """

    # Load audio file
    y, sr = librosa.load(audio_path, sr=sr)

    # 1. Calculate onset strength envelope (detects sudden changes)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    # 2. Calculate spectral features
    # RMS energy (loudness)
    rms = librosa.feature.rms(y=y)[0]

    # Spectral centroid (brightness)
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]

    # Spectral rolloff (frequency below which 85% of energy is concentrated)
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]

    # 3. Resample features to match onset envelope length
    target_len = len(onset_env)
    rms_resampled = np.interp(
        np.linspace(0, len(rms), target_len),
        np.arange(len(rms)),
        rms
    )

    # 4. Combine features into a "drop score"
    # Normalize each feature
    onset_norm = (onset_env - np.mean(onset_env)) / (np.std(onset_env) + 1e-8)
    rms_norm = (rms_resampled - np.mean(rms_resampled)) / (np.std(rms_resampled) + 1e-8)

    # Weight features (drops typically have high onset + high energy)
    drop_score = 0.6 * onset_norm + 0.4 * rms_norm

    # 5. Smooth the score
    drop_score_smooth = gaussian_filter1d(drop_score, sigma=2)

    # 6. Find peaks in the drop score
    # Calculate dynamic threshold based on score distribution
    threshold = np.percentile(drop_score_smooth, 80)

    peaks, properties = find_peaks(
        drop_score_smooth,
        height=threshold,
        distance=sr // 512 * 8,  # Minimum 8 seconds between drops
        prominence=0.5
    )

    # 7. Convert frame indices to time
    times = librosa.frames_to_time(peaks, sr=sr, hop_length=512)

    # 8. Find the main drop (usually the highest peak)
    if len(peaks) > 0:
        main_drop_idx = peaks[np.argmax(drop_score_smooth[peaks])]
        main_drop_time = librosa.frames_to_time(main_drop_idx, sr=sr, hop_length=512)
    else:
        # Fallback: find global maximum
        main_drop_idx = np.argmax(drop_score_smooth)
        main_drop_time = librosa.frames_to_time(main_drop_idx, sr=sr, hop_length=512)
        times = [main_drop_time]

    return main_drop_time, times.tolist()


def detect_drop_advanced(audio_path: str, sr: int = 22050,
                         plot: bool = False) -> dict:
    """
    Advanced drop detection with additional analysis.

    Parameters:
    -----------
    audio_path : str
        Path to the audio file
    sr : int
        Sample rate
    plot : bool
        Whether to plot the analysis (requires matplotlib)

    Returns:
    --------
    dict with keys:
        'main_drop': float - main drop time in seconds
        'all_drops': list - all detected drops
        'top3': list - top 3 drops sorted by time
        'confidence': float - confidence score (0-1)
        'build_up_start': float - estimated build-up start time
    """

    y, sr = librosa.load(audio_path, sr=sr)

    # Calculate features
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

    # Energy and spectral features
    rms = librosa.feature.rms(y=y)[0]
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)

    # Resample RMS to match onset envelope
    target_len = len(onset_env)
    rms_resampled = np.interp(
        np.linspace(0, len(rms), target_len),
        np.arange(len(rms)),
        rms
    )

    # Detect sudden energy increases
    energy_diff = np.diff(rms_resampled, prepend=rms_resampled[0])
    energy_diff_smooth = gaussian_filter1d(energy_diff, sigma=2)

    # Combine signals
    onset_norm = (onset_env - np.mean(onset_env)) / (np.std(onset_env) + 1e-8)
    energy_norm = (energy_diff_smooth - np.mean(energy_diff_smooth)) / (np.std(energy_diff_smooth) + 1e-8)

    drop_score = 0.5 * onset_norm + 0.5 * energy_norm
    drop_score_smooth = gaussian_filter1d(drop_score, sigma=3)

    # Find peaks
    threshold = np.percentile(drop_score_smooth, 75)
    peaks, properties = find_peaks(
        drop_score_smooth,
        height=threshold,
        distance=sr // 512 * 8,
        prominence=0.3
    )

    times = librosa.frames_to_time(peaks, sr=sr, hop_length=512)

    # Main drop
    if len(peaks) > 0:
        main_drop_idx = peaks[np.argmax(properties['peak_heights'])]
        main_drop_time = librosa.frames_to_time(main_drop_idx, sr=sr, hop_length=512)
        confidence = float(np.max(properties['peak_heights']) / np.max(drop_score_smooth))

        # Estimate build-up (look back for energy valley)
        lookback = max(0, main_drop_idx - sr // 512 * 16)  # Look back 16 seconds
        valley_idx = lookback + np.argmin(rms_resampled[lookback:main_drop_idx])
        build_up_start = librosa.frames_to_time(valley_idx, sr=sr, hop_length=512)
    else:
        main_drop_idx = np.argmax(drop_score_smooth)
        main_drop_time = librosa.frames_to_time(main_drop_idx, sr=sr, hop_length=512)
        confidence = 0.5
        build_up_start = max(0, main_drop_time - 16)
        times = [main_drop_time]

    # Optional plotting
    if plot:
        try:
            import matplotlib.pyplot as plt

            time_frames = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=512)

            fig, axes = plt.subplots(3, 1, figsize=(14, 10))

            axes[0].plot(time_frames, onset_env, label='Onset Strength', alpha=0.7)
            axes[0].set_ylabel('Onset Strength')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            axes[1].plot(time_frames, rms_resampled, label='RMS Energy', alpha=0.7)
            axes[1].set_ylabel('Energy')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

            axes[2].plot(time_frames, drop_score_smooth, label='Drop Score', linewidth=2)
            axes[2].scatter(times, drop_score_smooth[peaks], color='red', s=100,
                            zorder=5, label='Detected Drops')
            axes[2].axvline(main_drop_time, color='green', linestyle='--',
                            linewidth=2, label='Main Drop')
            axes[2].set_xlabel('Time (s)')
            axes[2].set_ylabel('Drop Score')
            axes[2].legend()
            axes[2].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.show()
        except ImportError:
            print("Matplotlib not available for plotting")

    # Get top 3 drops by peak height
    top3_drops = []
    if len(peaks) > 0:
        # Sort peaks by their heights (prominence)
        sorted_indices = np.argsort(properties['peak_heights'])[::-1]
        top3_indices = sorted_indices[:min(3, len(sorted_indices))]
        top3_peaks = peaks[top3_indices]
        top3_drops = [float(librosa.frames_to_time(idx, sr=sr, hop_length=512))
                      for idx in top3_peaks]
        # Sort by time order
        top3_drops.sort()

    return {
        'main_drop': float(main_drop_time),
        'all_drops': [float(t) for t in times],
        'top3': top3_drops,
        'confidence': float(confidence),
        'build_up_start': float(build_up_start)
    }


# Example usage
if __name__ == "__main__":
    # Basic detection
    main_drop, all_drops = detect_drop("4.music/El Viento del Alma.mp3")
    print(f"Main drop at: {main_drop:.2f} seconds")
    print(f"All drops at: {[f'{t:.2f}s' for t in all_drops]}")

    # Advanced detection
    result = detect_drop_advanced("4.music/El Viento del Alma.mp3", plot=False)
    print(f"\nAdvanced Analysis:")
    print(f"Main drop: {result['main_drop']:.2f}s")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Build-up starts: {result['build_up_start']:.2f}s")