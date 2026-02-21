import logging
import os
import sys
import threading
import time

from config import IS_WIN

# pythonw.exe (Windows) sets stdout/stderr to None - redirect to devnull so libraries don't crash
if IS_WIN:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

# Setup logging first - writes to file so errors are visible even with pythonw.exe
_dir = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_dir, "dictation.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# Add NVIDIA CUDA DLLs to path before importing ctranslate2 (Windows only)
if IS_WIN:
    for _nvidia_dir in [
        os.path.join(_dir, ".venv", "Lib", "site-packages", "nvidia", "cublas", "bin"),
        os.path.join(_dir, ".venv", "Lib", "site-packages", "nvidia", "cudnn", "bin"),
    ]:
        if os.path.isdir(_nvidia_dir):
            os.add_dll_directory(_nvidia_dir)
            os.environ["PATH"] = _nvidia_dir + os.pathsep + os.environ.get("PATH", "")

from audio import AudioRecorder
from transcriber import Transcriber
from keyboard_hook import KeyboardHook
from feedback import beep_start, beep_stop, beep_done
from overlay import Overlay
from config import SAMPLE_RATE, MIN_AUDIO_DURATION, AUTO_STOP, TRIGGER_KEY_NAME


def main():
    def on_quit():
        if ctx["recorder"]:
            ctx["recorder"].shutdown()
        if ctx["hook"]:
            ctx["hook"].stop()
        log.info("Quit via overlay menu.")

    ui = Overlay(on_quit=on_quit)
    lock = threading.Lock()

    # All mutable state in one dict - avoids nonlocal closure issues
    ctx = {
        "recorder": None,
        "transcriber": None,
        "hook": None,
        "ready": False,
        "recording": False,
    }

    def process_audio():
        audio = ctx["recorder"].stop()
        beep_stop()
        ui.set_state("transcribing")

        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_AUDIO_DURATION:
            log.info(f"Skipped - too short ({duration:.2f}s)")
            ui.set_state("idle")
            return

        log.info(f"Transcribing {duration:.1f}s of audio...")
        t0 = time.time()
        text = ctx["transcriber"].transcribe(audio)
        elapsed = time.time() - t0

        if text:
            log.info(f"[{elapsed:.2f}s] {text}")
            ctx["hook"].type_text(text)
            beep_done()
            ui.set_state("done")
        else:
            log.info(f"No speech detected ({elapsed:.2f}s)")
            ui.set_state("idle")

    def on_record_start():
        with lock:
            if ctx["recording"] or not ctx["ready"]:
                return
            ctx["recording"] = True
        beep_start()
        ui.set_state("recording")
        if AUTO_STOP:
            ctx["recorder"].start(on_silence=on_auto_stop)
        else:
            ctx["recorder"].start()
        log.info("Recording started")

    def on_record_stop():
        with lock:
            if not ctx["recording"]:
                return
            ctx["recording"] = False
        log.info("Recording stopped (manual)")
        try:
            process_audio()
        except Exception as e:
            log.error(f"Processing failed: {e}", exc_info=True)
            ui.set_state("idle")

    def on_auto_stop():
        with lock:
            if not ctx["recording"]:
                return
            ctx["recording"] = False
        log.info("Recording stopped (silence detected)")
        try:
            process_audio()
        except Exception as e:
            log.error(f"Processing failed: {e}", exc_info=True)
            ui.set_state("idle")

    def start_keyboard():
        """Start keyboard hook on main thread (macOS Quartz requires main thread)."""
        try:
            ctx["hook"] = KeyboardHook(
                on_record_start=on_record_start,
                on_record_stop=on_record_stop,
            )
            if not ctx["hook"].start():
                log.error("Keyboard hook failed to start. Check Accessibility permission.")
                ui.set_state("error")
                return
            ctx["ready"] = True
            mode = "auto-stop" if AUTO_STOP else "hold-to-record"
            log.info(f"Ready ({mode}). Hold {TRIGGER_KEY_NAME} to dictate.")
            ui.set_state("idle")
        except Exception as e:
            log.error(f"Failed to start keyboard hook: {e}", exc_info=True)
            ui.set_state("error")

    def init_backend():
        try:
            ui.set_state("loading")
            ui.set_sublabel("MICROPHONE")
            ctx["recorder"] = AudioRecorder()
            ui.set_recorder(ctx["recorder"])
            ui.set_sublabel("WHISPER AI")
            ctx["transcriber"] = Transcriber()
            # Schedule keyboard hook on main thread (macOS Quartz event tap
            # must be added to the main thread's CFRunLoop)
            ui._root.after(0, start_keyboard)
        except Exception as e:
            log.error(f"Failed to initialize: {e}", exc_info=True)
            ui.set_state("error")

    threading.Thread(target=init_backend, daemon=True).start()

    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        if ctx["hook"]:
            ctx["hook"].stop()
        if ctx["recorder"]:
            ctx["recorder"].shutdown()
        log.info("Shut down.")


if __name__ == "__main__":
    main()
