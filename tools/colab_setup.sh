# Paste into a fresh Colab (GPU runtime). Avoids piper-phonemize entirely.
!pip install -q openwakeword webrtcvad gtts ffmpeg-python numpy scipy tqdm datasets pydub
!apt-get install -y ffmpeg >/dev/null 2>&1
import os, sys
# gTTS-based synth clip (cell 1 substitute):
# !pip install -q gtts
