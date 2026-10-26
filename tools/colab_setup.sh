# Paste into a fresh Colab (GPU runtime). Avoids piper-phonemize entirely.
# Chosen wake phrase (phonetic): hey_pik_sel  -> model output: my_custom_model/hey_pik_sel.onnx
!apt-get install -y espeak-ng >/dev/null 2>&1
!pip install -q openwakeword webrtcvad gtts ffmpeg-python numpy scipy tqdm datasets pydub
!apt-get install -y ffmpeg >/dev/null 2>&1
import os, sys
