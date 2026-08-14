"""
Audio Processing Test Suite
Validates duration, sample rate, bitrate, loudness dB, and SNR noise estimation.
"""

import unittest
import os
from app.audio_processor import process_audio_submission
from pipeline.generate_sample_audio import create_sample_wav, SAMPLE_DIR


class TestAudioProcessor(unittest.TestCase):
    def setUp(self):
        self.sample_wav = os.path.join(SAMPLE_DIR, "test_audio.wav")
        create_sample_wav("test_audio.wav", duration_sec=3.0, sample_rate=44100)

    def tearDown(self):
        if os.path.exists(self.sample_wav):
            try:
                os.remove(self.sample_wav)
            except Exception:
                pass

    def test_audio_properties_extracted(self):
        metrics = process_audio_submission(self.sample_wav, "test_audio.wav")
        self.assertAlmostEqual(metrics["duration_sec"], 3.0, delta=0.2)
        self.assertEqual(metrics["sample_rate_khz"], 44.1)
        self.assertGreater(metrics["bitrate_kbps"], 500.0) # 16-bit 44.1kHz mono is ~705.6 kbps
        self.assertLess(metrics["loudness_db"], 0.0)
        self.assertGreater(metrics["loudness_db"], -40.0)
        self.assertIn("SNR", metrics["quality_score"])


if __name__ == "__main__":
    unittest.main()
