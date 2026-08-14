"""
Audio Test Sample Generator
Generates clean sample WAV audio files for test submissions and demonstrations.
"""

import os
import wave
import struct
import math

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(SAMPLE_DIR, exist_ok=True)


def create_sample_wav(filename: str, duration_sec: float = 3.5, sample_rate: int = 44100, freq_hz: float = 440.0):
    file_path = os.path.join(SAMPLE_DIR, filename)
    num_frames = int(duration_sec * sample_rate)
    
    with wave.open(file_path, "w") as wf:
        wf.setnchannels(1)       # Mono
        wf.setsampwidth(2)      # 16-bit
        wf.setframerate(sample_rate)
        
        for i in range(num_frames):
            # Create a decaying acoustic harmonic tone mimicking speech/voice
            t = float(i) / sample_rate
            amplitude = 16000.0 * math.sin(2.0 * math.pi * freq_hz * t) * math.exp(-t * 0.3)
            # Add subtle harmonic
            amplitude += 4000.0 * math.sin(2.0 * math.pi * (freq_hz * 2.0) * t)
            
            sample_val = int(max(-32767, min(32767, amplitude)))
            wf.writeframesraw(struct.pack("<h", sample_val))
            
    print(f"Generated test audio: {file_path} (Duration: {duration_sec}s, Sample Rate: {sample_rate}Hz)")
    return file_path


if __name__ == "__main__":
    create_sample_wav("demo_voice_sample_1.wav", duration_sec=4.2, sample_rate=44100, freq_hz=320.0)
    create_sample_wav("demo_voice_sample_2.wav", duration_sec=2.8, sample_rate=16000, freq_hz=480.0)
