import numpy as np
import sounddevice as sd
from scipy.signal import stft
import queue
import sys

# Parameters
fs = 44100  # Sampling rate
nperseg = 1024  # Length of each segment for STFT

# Create a queue to hold incoming audio frames
audio_q = queue.Queue()


# Callback function to capture audio from the microphone
def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    # Put the incoming audio data into the queue
    audio_q.put(indata.copy())


# Start the audio stream
stream = sd.InputStream(callback=audio_callback, channels=1, samplerate=fs)
with stream:
    try:
        # Continuously process the incoming audio
        while True:
            # Retrieve a frame of audio data from the queue
            data = audio_q.get()

            # Adjust nperseg if it's larger than the length of the data
            current_nperseg = min(len(data), nperseg)
            noverlap = current_nperseg // 2  # Set noverlap to half of current_nperseg

            # Compute the STFT
            frequencies, times, Zxx = stft(data[:, 0], fs=fs, nperseg=current_nperseg, noverlap=noverlap)
            Zxx = np.abs(Zxx)  # Get the magnitude

            # Normalize and scale the magnitude data
            max_magnitude = Zxx.max() if Zxx.size > 0 else 1
            scaled_magnitude = (Zxx / max_magnitude) * 25  # Scale to range [0, 25]
            scaled_magnitude = scaled_magnitude.astype(int)  # Convert to integer for discrete levels

            # Normalize and scale frequency data
            min_freq, max_freq = frequencies[0], frequencies[-1]
            scaled_frequencies = (frequencies - min_freq) / (max_freq - min_freq) * 99  # Scale to range [0, 99]
            scaled_frequencies = scaled_frequencies.astype(int)  # Convert to integer for discrete levels

            # Create a dictionary for the frame
            frame_data = {}
            for freq, mag in zip(scaled_frequencies, scaled_magnitude[:, 0]):
                if mag > 0:  # Only consider points where magnitude is greater than zero
                    frame_data[f"{freq}-{mag}-0"] = 0

            # Print the frame data as a dictionary
            if frame_data:  # Only print if there's data in the frame
                # print(f"Frame (time index): {times[0]:.2f} seconds")
                print(frame_data)

            # Optional: Break after a certain condition or time
            # if some_condition:
            #     break

    except KeyboardInterrupt:
        print("\nStreaming stopped by user")
