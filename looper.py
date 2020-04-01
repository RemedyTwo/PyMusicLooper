import os
import sys
import numpy as np
from mpg123 import Mpg123, Out123
import mpg123
import librosa

class MusicLooper:
    def __init__(self, filename):
        # Load the file if it exists
        if os.path.exists(filename) and os.path.isfile(filename):
            try:
                audio, sr = librosa.load(filename, sr=None, mono=True)
            except:
                raise TypeError("Unsupported file type.")
        else:
            raise FileNotFoundError("Specified file not found.")

        # Get the waveform data from the mp3 file
        self.audio = audio
        self.rate = sr
        self.playback_audio, _ = librosa.load(filename, sr=None, mono=False)

        # Initialize parameters for playback
        self.channels = self.playback_audio.shape[0]
        self.encoding = mpg123.ENC_FLOAT_32

    def find_loop_pairs(self, method='angle', min_duration_multiplier=0.2):
        _, beats = librosa.beat.beat_track(y=self.audio, sr=self.rate)
        chroma = librosa.feature.chroma_stft(y=self.audio, sr=self.rate)
        mel_spectrogram = librosa.feature.melspectrogram(y=self.audio, sr=self.rate)
        power_db = librosa.power_to_db(mel_spectrogram)
        min_duration = int(chroma.shape[-1] * min_duration_multiplier)
        candidate_pairs = []

        for i in range(beats.size):
            for j in range(i):
                if beats[i] - beats[j] < min_duration:
                    continue
                
                if method == 'euclid_dist':
                    dist = np.linalg.norm(chroma[..., beats[i]] - chroma[..., beats[j]])
                    if dist <= 0.15:
                        candidate_pairs.append((beats[j], beats[i], dist))
        
                elif method == 'angle':
                    angle = np.abs(self.angle_between(chroma[..., beats[i]], chroma[..., beats[j]]))           
                    if angle <= 10:
                        candidate_pairs.append((beats[j], beats[i], angle))
        
        print(len(candidate_pairs))
        most_similar_pairs = sorted(candidate_pairs, reverse=False, key=lambda x: x[2])[:10]
        pruned_list = []

        print(most_similar_pairs)

        for start, end, dist in most_similar_pairs:
            if self._is_db_similar(power_db[..., end], power_db[..., start], threshold=2.5):
                pruned_list.append((start, end, dist))

        print(pruned_list)

        return pruned_list

    def _is_db_similar(self, power_db_f1, power_db_f2, threshold):
        return np.abs(np.average(power_db_f1) - np.average(power_db_f2)) <= threshold
    
    def unit_vector(self, vector):
        """ Returns the unit vector of the vector """
        return vector / np.linalg.norm(vector)

    def angle_between(self, v1, v2):
        """ Returns the angle in degrees between vectors 'v1' and 'v2' """
        v1_u = self.unit_vector(v1)
        v2_u = self.unit_vector(v2)
        return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0)) * 360 / np.pi
    
    def frames_to_samples(self, frame):
        return librosa.core.frames_to_samples(frame)

    def frames_to_ftime(self, frame):
        time_sec = librosa.core.frames_to_time(frame, sr=self.rate)
        return "{:02.0f}:{:06.3f}".format(
                    time_sec // 60,
                    time_sec % 60
                    )

    def play_looping(self, start_offset, loop_offset):
        out = Out123()
        out.start(self.rate, self.channels, self.encoding)
        
        playback_frames  = librosa.util.frame(self.playback_audio.flatten(order='F'))
        adjusted_start_offset = start_offset * self.channels
        adjusted_loop_offset = loop_offset * self.channels

        i = adjusted_loop_offset - 1000
        try:
            while True:
                out.play(playback_frames[..., i])
                i += 1
                
                if i == adjusted_loop_offset:
                    i = adjusted_start_offset

        except KeyboardInterrupt:
            print() # so that the program ends on a newline

def loop_track(filename, prioritize_duration=False):
    try:
        # Load the file
        print("Loading {}...".format(filename))
        track = MusicLooper(filename)

        a = track.find_loop_pairs()
        # Use the loop point with the best similarity
        if len(a) == 0:
            print('No suitable loop point found.')

        if prioritize_duration:
            a = sorted(a, key=lambda x: np.abs(x[0] - x[1]), reverse=True)
        else:
            a = sorted(a, key=lambda x: x[-1])

        start, end, score = a[0]
        
        print("Playing with loop from {} back to {}, prioritizing {}, (score={})".format(
            track.frames_to_ftime(end),
            track.frames_to_ftime(start),
            'duration' if prioritize_duration else 'beat similarity',
            score))
        print("(press Ctrl+C to exit)")
        track.play_looping(start, end)

    except (TypeError, FileNotFoundError) as e:
        print("Error: {}".format(e))

if __name__ == '__main__':
    # Load the file
    if len(sys.argv) == 2:
        loop_track(sys.argv[1])
    else:
        print("Error: No file specified.",
                "\nUsage: python3 loop.py file.mp3")
