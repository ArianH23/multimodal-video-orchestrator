from domain.ports.audio_analyzer import AudioAnalyzerPort


class AudioAnalysisService:
    def __init__(self, analyzer: AudioAnalyzerPort):
        self.analyzer = analyzer

    def get_epic_drop_time(self, audio_path: str, video_duration: int, zoom_out_duration: int) -> float:
        print(f"Analyzing audio waveform for: {audio_path}")

        minimum_buildup_time = 8.0

        # Calculate how much audio we need AFTER the drop.
        # If the video is 12s + 4s zoom out, and the drop happens at 8s,
        # we need at least 8 seconds of audio remaining.
        required_tail_time = (video_duration + zoom_out_duration) - minimum_buildup_time

        analysis = self.analyzer.analyze_drops(
            audio_path=audio_path,
            min_drop_time=minimum_buildup_time,
            min_tail_time=required_tail_time
        )

        print(f"Main drop securely located at {analysis.main_drop:.2f}s")
        return analysis.main_drop