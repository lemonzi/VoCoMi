"""PyAudio: Record audio and save to a PCM file."""

import pyaudio

def record(out_file, chunk=512, audio_format=pyaudio.paInt16, channels=1, rate=16000):
    p = pyaudio.PyAudio()

    stream = p.open(format=audio_format,
                    channels=channels,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk)

    print("* recording")

    frames = []

    # read and store the raw audio data
    while (True):
        try:
            data = stream.read(chunk)
            frames.append(data)
        except KeyboardInterrupt:
            break

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    # write raw data to pcm file
    with open('output_files/output.pcm', 'wb+') as pcm_file:
        pcm_file.write(b''.join(frames))

if __name__ == "__main__":
    record(out_file='output_files/output.pcm')