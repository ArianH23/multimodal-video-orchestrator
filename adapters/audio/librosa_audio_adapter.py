from domain.ports.audio_analyzer import AudioAnalyzerPort
from domain.models.audio_analysis import AudioDropAnalysis


class LibrosaAudioAdapter(AudioAnalyzerPort):

    def analyze_drops(self, audio_path: str, min_drop_time: float = 8.0, min_tail_time: float = 8.0) -> AudioDropAnalysis:
        import librosa
        import numpy as np
        from scipy.signal import find_peaks
        from scipy.ndimage import gaussian_filter1d

        y, sr = librosa.load(audio_path, sr=22050)

        total_duration = librosa.get_duration(y=y, sr=sr)

        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)[0]

        target_len = len(onset_env)
        rms_resampled = np.interp(
            np.linspace(0, len(rms), target_len),
            np.arange(len(rms)),
            rms
        )

        energy_diff = np.diff(rms_resampled, prepend=rms_resampled[0])
        energy_diff_smooth = gaussian_filter1d(energy_diff, sigma=2)

        onset_norm = (onset_env - np.mean(onset_env)) / (np.std(onset_env) + 1e-8)
        energy_norm = (energy_diff_smooth - np.mean(energy_diff_smooth)) / (np.std(energy_diff_smooth) + 1e-8)

        drop_score = 0.5 * onset_norm + 0.5 * energy_norm
        drop_score_smooth = gaussian_filter1d(drop_score, sigma=3)

        threshold = np.percentile(drop_score_smooth, 75)
        peaks, properties = find_peaks(
            drop_score_smooth,
            height=threshold,
            distance=sr // 512 * 8,
            prominence=0.3
        )

        times = librosa.frames_to_time(peaks, sr=sr, hop_length=512)

        valid_indices = [i for i, t in enumerate(times) if t >= min_drop_time]

        times = librosa.frames_to_time(peaks, sr=sr, hop_length=512)

        # ENFORCE BOTH DOMAIN RULES:
        # Must be after min_drop_time AND leave enough room before total_duration
        max_drop_time = total_duration - min_tail_time
        valid_indices = [i for i, t in enumerate(times) if min_drop_time <= t <= max_drop_time]

        if valid_indices:
            valid_peaks = peaks[valid_indices]
            valid_heights = properties['peak_heights'][valid_indices]
            valid_times = times[valid_indices]

            best_idx = np.argmax(valid_heights)
            main_drop_idx = valid_peaks[best_idx]
            main_drop_time = valid_times[best_idx]
            confidence = float(valid_heights[best_idx] / np.max(drop_score_smooth))

            lookback = max(0, main_drop_idx - sr // 512 * 16)
            valley_idx = lookback + np.argmin(rms_resampled[lookback:main_drop_idx])
            build_up_start = librosa.frames_to_time(valley_idx, sr=sr, hop_length=512)

            sorted_valid_indices = np.argsort(valid_heights)[::-1]
            top3_indices = sorted_valid_indices[:min(3, len(sorted_valid_indices))]
            top3_drops = [float(valid_times[i]) for i in top3_indices]
            top3_drops.sort()
            all_valid_drops = [float(t) for t in valid_times]

        else:
            # Fallback: If no natural peaks exist after 8 seconds, force find the maximum energy after 8s
            min_frame = librosa.time_to_frames(min_drop_time, sr=sr, hop_length=512)
            max_frame = librosa.time_to_frames(max_drop_time, sr=sr, hop_length=512)

            # Ensure we don't go out of bounds if the song is extremely short
            if min_frame < max_frame and min_frame < len(drop_score_smooth):
                safe_window = drop_score_smooth[min_frame:max_frame]
                main_drop_idx = min_frame + np.argmax(safe_window)
            else:
                # Absolute worst-case scenario (song is shorter than minimum required length)
                main_drop_idx = min_frame

            main_drop_time = librosa.frames_to_time(main_drop_idx, sr=sr, hop_length=512)
            confidence = 0.3
            build_up_start = max(0, main_drop_time - 16)
            top3_drops = [float(main_drop_time)]
            all_valid_drops = [float(main_drop_time)]

        return AudioDropAnalysis(
            main_drop=float(main_drop_time),
            all_drops=all_valid_drops,
            top3=top3_drops,
            confidence=float(confidence),
            build_up_start=float(build_up_start)
        )
