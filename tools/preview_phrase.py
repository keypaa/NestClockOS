"""Preview a wake-word phrase (TTS) locally or in Colab, no piper needed."""
import argparse, os, subprocess, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phrase", nargs="?", default="hey_pik_sel")
    ap.add_argument("--engine", choices=["gtts","flite","espeak"], default="gtts")
    ap.add_argument("--out", default="test_generation.wav")
    args = ap.parse_args()
    text = args.phrase.replace("_", " ")
    subprocess.run(["which", args.engine] + (["gtts-cli"] if args.engine == "gtts" else []), check=False)
    if args.engine == "gtts":
        try:
            import gtts
            gtts.gTTS(text, lang="en", slow=False).save("/tmp/tts.mp3")
            subprocess.run(["ffmpeg","-y","-i","/tmp/tts.mp3","-ar","16000","-ac","1","-c:a","pcm_s16le", args.out], check=True)
        except ImportError:
            print("gTTS not installed; pip install gtts")
            sys.exit(1)
    elif args.engine == "flite":
        subprocess.run(["flite","-t",text,"-o",args.out], check=True)
    elif args.engine == "espeak":
        subprocess.run(["espeak-ng","-s","150","-w",args.out,text], check=True)
    print("wrote", args.out)

if __name__ == "__main__":
    main()
