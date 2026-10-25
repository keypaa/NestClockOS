"""Energy-based speech endpointing (pure logic, testable without a mic)."""
PRE_FRAMES = 6
TAIL_FRAMES = 5
GLITCH_RMS = 0.5


class Endpointer:
    def __init__(self, frame_s=0.05, calib_s=0.4, silence_s=0.8, start_frames=3,
                 min_speech_s=0.25, max_s=10.0, start_timeout_s=6.0, min_threshold=0.012):
        self.frame_s, self.calib_s, self.silence_s = frame_s, calib_s, silence_s
        self.start_frames, self.min_speech_s, self.max_s = start_frames, min_speech_s, max_s
        self.start_timeout_s, self.min_threshold = start_timeout_s, min_threshold
        self.i = -1
        self.calib = []
        self.floor = None
        self.glitches = 0
        self.threshold = None
        self.state = "calibrating"
        self.run = 0
        self.onset = None
        self.last_loud = None
        self.quiet = 0.0

    def feed(self, rms):
        self.i += 1
        if self.state == "calibrating":
            if rms >= GLITCH_RMS:
                self.glitches += 1
                return "timeout" if self.glitches * self.frame_s > 3.0 else "wait"
            self.calib.append(rms)
            if len(self.calib) * self.frame_s >= self.calib_s:
                self.floor = sorted(self.calib)[len(self.calib) // 4]
                self.threshold = max(3.0 * self.floor, self.min_threshold)
                self.state = "waiting"
            return "wait"
        if self.state == "waiting":
            self.run = self.run + 1 if rms >= self.threshold else 0
            if self.run >= self.start_frames:
                self.state = "speech"
                self.onset = self.i - self.run + 1
                self.last_loud = self.i
                self.quiet = 0.0
            elif (self.i + 1) * self.frame_s >= self.calib_s + self.start_timeout_s:
                return "timeout"
            return "wait"
        if rms >= 0.6 * self.threshold:
            self.last_loud = self.i
            self.quiet = 0.0
        else:
            self.quiet += self.frame_s
        spoken = (self.last_loud - self.onset + 1) * self.frame_s
        if self.quiet >= self.silence_s:
            if spoken < self.min_speech_s:
                self.state, self.run, self.onset = "waiting", 0, None
                return "wait"
            return "done"
        if (self.i - self.onset) * self.frame_s >= self.max_s:
            return "done"
        return "wait"

    def span(self):
        return max(0, self.onset - PRE_FRAMES), self.last_loud + 1 + TAIL_FRAMES
