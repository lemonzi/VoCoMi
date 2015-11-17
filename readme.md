![VoCoMi](https://raw.githubusercontent.com/lemonzi/VoCoMi/master/logo.png)

VoCoMi (Voice-Controlled Mixer) is our hack submitted to the WearHacks Montreal 2015 Hackathon. It is a music sequencer for visually impaired people that does not require any visual feedback to be operated.

The system prompts input to the user using Nuance's TTS engine, and it understand voice commands through Nuance's speech recognition and understanding API's. Once a sample bank is selected, the user can browse its contents with gestures using the Myo armband and compose with them using a loop machine.

Installation
-----------

1. Clone or download the repo.
2. Make sure you have Python 3. You might have to run `pip3` and `python3` all the time (default if you use homebrew and don't touch anything).
3. Install Myo Connect and check that it works.
4. Get Nuance user and application API keys, and put them in `credentials.json`.
5. Install the `six`, `aiohttp`, `pyaudio`, and `numpy` Python packages from `pip`. Installl also the `pygame` (look for instructions online) and `pyspeex` (https://github.com/NuanceDev/pyspeex) packages. You may also have to install the `portaudio` and `speex` system packages beforehand (both available on homebrew).
6. Add myo-sdk to the LDPATH: `export DYLD_LIBRARY_PATH=$DYLD_LIBRARY_PATH:$(pwd)/myo-sdk/myo.framework`
7. Run `python3 vocomi.py` or `python vocomi.py`, depending on your setup.
8. Enjoy!

Troubleshooting
---------------

If you get an error getting the number of channels, it is because the system is using the wrong device to get audio input. Try changing the constant `INPUT_DEVICE` in `vocomi.py`.

You can change the audio samples (just put whatever `wav` files inside the `assets` sub-folders respecting the existing folder structure), but not the categories (that would require adapting the language model, and some code if you change the top-level categories with sub-groups).

