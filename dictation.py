import logging
import os
import sys
import threading
import time

from config import IS_WIN
from paths import get_data_dir

# pythonw.exe (Windows) sets stdout/stderr to None - redirect to devnull so libraries don't crash
if IS_WIN:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

# Setup logging first - writes to file so errors are visible even with pythonw.exe
_dir = get_data_dir()
_log_handlers = [
    logging.FileHandler(os.path.join(_dir, "dictation.log"), encoding="utf-8"),
]
# Only add StreamHandler when stdout is a real terminal (not redirected to log file
# by Bark.app launcher, which would cause every line to appear twice).
if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
    _log_handlers.append(logging.StreamHandler())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger(__name__)

# Add NVIDIA CUDA DLLs to path before importing ctranslate2 (dev mode only).
# In frozen mode, PyInstaller bundles these DLLs directly.
if IS_WIN and not getattr(sys, "frozen", False):
    _sp = os.path.join(_dir, ".venv", "Lib", "site-packages", "nvidia")
    for _nvidia_dir in [
        os.path.join(_sp, "cublas", "bin"),
        os.path.join(_sp, "cudnn", "bin"),
        os.path.join(_sp, "cuda_runtime", "bin"),
        os.path.join(_sp, "cufft", "bin"),
        os.path.join(_dir, ".venv", "Lib", "site-packages", "ctranslate2"),
    ]:
        if os.path.isdir(_nvidia_dir):
            os.add_dll_directory(_nvidia_dir)
            os.environ["PATH"] = _nvidia_dir + os.pathsep + os.environ.get("PATH", "")

from audio import AudioRecorder
from transcriber import Transcriber
from keyboard_hook import KeyboardHook
from feedback import beep_start, beep_stop, beep_done, beep_error
from overlay import Overlay
from tray import SystemTray
from history import append_history
from version_check import check_for_update
from config import cfg, save_config, IS_MAC, SAMPLE_RATE, TRIGGER_KEY_NAME


def main():
    def on_quit():
        if ctx.get("tray"):
            ctx["tray"].stop()
        if ctx["recorder"]:
            ctx["recorder"].shutdown()
        if ctx["hook"]:
            ctx["hook"].stop()
        log.info("Quit.")

    ui = Overlay(on_quit=on_quit)
    tray = SystemTray(overlay=ui, on_quit=on_quit)
    ui.set_tray(tray)
    lock = threading.Lock()

    # All mutable state in one dict - avoids nonlocal closure issues
    ctx = {
        "recorder": None,
        "transcriber": None,
        "hook": None,
        "tray": tray,
        "ready": False,
        "recording": False,
        # Serialize MLX/whisper access -- two threads submitting GPU work
        # crashes. Lives in ctx so wedge recovery can swap in a fresh lock
        # (the orphaned hung thread never releases the old one).
        "transcribe_lock": threading.Lock(),
    }

    def recover_gpu_wedge(timeout):
        """A transcription call hung past the watchdog. Assume a wedged GPU:
        persist CPU mode, abandon the hung call, rebuild the model on CPU."""
        with lock:
            if ctx.get("recovering"):
                return
            ctx["recovering"] = True
        log.error(
            f"Transcription hung >{timeout:.0f}s - assuming GPU wedge. "
            "Switching to CPU mode (persisted; undo via tray > Use CPU)."
        )
        if not cfg["force_cpu"]:
            cfg["force_cpu"] = True
            save_config()
        ctx["ready"] = False
        ctx["transcribe_lock"] = threading.Lock()

        def _rebuild():
            # "loading" while the CPU model builds - decaying to idle here
            # would show a ready-green pill while ctx["ready"] is still False
            ui.set_state("loading")
            ui.set_sublabel("REBUILDING ON CPU...")
            try:
                ctx["transcriber"] = Transcriber(device="cpu")
                ctx["ready"] = True
                log.info("Recovered on CPU after GPU wedge.")
                ui.set_state("idle")
                ui.set_sublabel("CPU MODE (GPU HUNG)")
            except Exception:
                log.exception("CPU rebuild after GPU wedge failed")
                beep_error()
                ui.set_state("fatal")
                ui.set_sublabel("RECOVERY FAILED - restart Bark")
            finally:
                ctx["recovering"] = False

        threading.Thread(target=_rebuild, daemon=True).start()

    def process_audio():
        audio = ctx["recorder"].stop()
        beep_stop()
        ui.set_state("transcribing")

        duration = len(audio) / SAMPLE_RATE
        if duration < cfg["min_audio_duration"]:
            log.info(f"Skipped - too short ({duration:.2f}s)")
            ui.set_state("idle")
            return

        log.info(f"Transcribing {duration:.1f}s of audio...")
        t0 = time.time()

        # Run transcription on a watched worker thread. A wedged CUDA call
        # (driver hiccup, OOM stall) would otherwise hang this thread forever.
        # Note the model load is NOT inside this timeout -- only transcription.
        result = {}
        done = threading.Event()
        tlock = ctx["transcribe_lock"]

        def _worker():
            try:
                with tlock:
                    result["text"] = ctx["transcriber"].transcribe(audio)
            except Exception as e:
                result["error"] = e
            finally:
                done.set()

        threading.Thread(target=_worker, daemon=True).start()
        watchdog = max(60.0, duration * 3)
        if not done.wait(watchdog):
            beep_error()
            ui.set_state("error")
            ui.set_sublabel("GPU HUNG - SWITCHING TO CPU")
            recover_gpu_wedge(watchdog)
            return
        if "error" in result:
            log.error(f"Transcription failed: {result['error']}",
                      exc_info=result["error"])
            beep_error()
            ui.set_state("error")
            ui.set_sublabel("TRANSCRIPTION FAILED")
            return

        text = result.get("text", "")
        elapsed = time.time() - t0

        if text:
            log.info(f"[{elapsed:.2f}s] {text}")
            ctx["hook"].type_text(text)
            beep_done()
            if cfg["streaming_preview"]:
                ui.flash_transcript(text)
            append_history(text)
            ui.set_state("done")
        else:
            log.info(f"No speech detected ({elapsed:.2f}s)")
            ui.set_state("idle")

    def _streaming_preview_loop():
        """Background loop: grab audio snapshot every ~1.2s and show partial text."""
        while ctx["recording"]:
            time.sleep(1.2)
            if not ctx["recording"]:
                break
            try:
                snapshot = ctx["recorder"].get_audio_snapshot()
                if len(snapshot) < SAMPLE_RATE * 0.5:
                    continue
                # Non-blocking: skip preview if main transcription owns the GPU
                tlock = ctx["transcribe_lock"]
                if not tlock.acquire(blocking=False):
                    continue
                try:
                    preview = ctx["transcriber"].transcribe_preview(snapshot)
                finally:
                    tlock.release()
                if preview and ctx["recording"]:
                    snippet = preview[:30] + "..." if len(preview) > 30 else preview
                    ui.set_sublabel(snippet)
            except Exception as e:
                log.debug(f"Streaming preview error: {e}")

    def on_record_start():
        with lock:
            if ctx["recording"] or not ctx["ready"]:
                return
            ctx["recording"] = True
        beep_start()
        ui.set_state("recording")
        if cfg["auto_stop"]:
            ctx["recorder"].start(on_silence=on_auto_stop,
                                  on_max_duration=on_max_duration)
        else:
            ctx["recorder"].start(on_max_duration=on_max_duration)
        log.info("Recording started")
        if cfg["streaming_preview"]:
            threading.Thread(target=_streaming_preview_loop, daemon=True).start()

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
            beep_error()
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
            beep_error()
            ui.set_state("idle")

    def on_max_duration():
        with lock:
            if not ctx["recording"]:
                return
            ctx["recording"] = False
        log.info("Recording stopped (max duration failsafe)")
        try:
            process_audio()
        except Exception as e:
            log.error(f"Processing failed: {e}", exc_info=True)
            beep_error()
            ui.set_state("idle")

    def poll_keyboard():
        """Poll keyboard event queue (Mac only). Runs on main thread via after()."""
        if ctx["hook"]:
            ctx["hook"].poll_events()
        ui._root.after(30, poll_keyboard)

    def start_keyboard():
        """Start keyboard hook."""
        try:
            ctx["hook"] = KeyboardHook(
                on_record_start=on_record_start,
                on_record_stop=on_record_stop,
                on_paste_fail=lambda: (
                    beep_error(),
                    ui.set_sublabel("Paste failed, text in clipboard"),
                ),
            )
            if not ctx["hook"].start():
                log.error("Keyboard hook failed to start. Check Accessibility permission.")
                beep_error()
                ui.set_state("fatal")
                ui.set_sublabel("KEYBOARD HOOK FAILED - see dictation.log")
                return
            ctx["ready"] = True
            mode = "auto-stop" if cfg["auto_stop"] else "hold-to-record"
            log.info(f"Ready ({mode}). Hold {TRIGGER_KEY_NAME} to dictate.")
            ui.set_state("idle")
            # Mac: poll the event queue from tkinter's main loop
            if IS_MAC:
                poll_keyboard()
        except Exception as e:
            log.error(f"Failed to start keyboard hook: {e}", exc_info=True)
            beep_error()
            ui.set_state("fatal")
            ui.set_sublabel("KEYBOARD HOOK FAILED - see dictation.log")

    def init_backend():
        try:
            ui.set_state("loading")
            ui.set_sublabel("MICROPHONE")
            ctx["recorder"] = AudioRecorder()
            ui.set_recorder(ctx["recorder"])
            ui.set_sublabel("WHISPER AI")
            ctx["transcriber"] = Transcriber(
                on_progress=lambda text: ui.set_sublabel(text),
            )
            # Schedule on main thread so poll_keyboard's after() loop runs there
            ui._root.after(0, start_keyboard)
        except Exception as e:
            log.error(f"Failed to initialize: {e}", exc_info=True)
            beep_error()
            ui.set_state("fatal")
            ui.set_sublabel("SETUP FAILED - see dictation.log")
            # Tray balloon so the user isn't left with just a red dot
            if ctx.get("tray"):
                try:
                    ctx["tray"].notify(
                        "Bark failed to start",
                        f"{e} - check dictation.log for details.",
                    )
                except Exception:
                    pass

    # System tray icon -- start BEFORE init_backend so the icon is ready
    # to show error notifications if initialization fails
    tray.start()

    threading.Thread(target=init_backend, daemon=True).start()

    # Background version check
    def _check_version():
        latest = check_for_update()
        if latest:
            log.info(f"Update available: v{latest}")
            ui.set_sublabel(f"UPDATE v{latest}")
            tray.show_update(latest)

    threading.Thread(target=_check_version, daemon=True).start()

    try:
        ui.run()
    except KeyboardInterrupt:
        pass
    finally:
        tray.stop()
        if ctx["hook"]:
            ctx["hook"].stop()
        if ctx["recorder"]:
            ctx["recorder"].shutdown()
        log.info("Shut down.")


def _acquire_instance_lock():
    """Prevent multiple Bark instances from running simultaneously.

    Returns the lock file object (keep reference alive) or None if another
    instance is already running.
    """
    lock_path = os.path.join(get_data_dir(), ".bark.lock")
    if IS_WIN:
        # Windows: use msvcrt file locking
        # Open as r+/a+ so we don't truncate another instance's lock file,
        # and write a sentinel byte first so there's data to lock.
        try:
            import msvcrt
            # Create file if missing, don't truncate if exists
            if not os.path.exists(lock_path):
                open(lock_path, "w").close()
            lock_file = open(lock_path, "r+")
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            lock_file.seek(0)
            lock_file.write(str(os.getpid()))
            lock_file.truncate()
            lock_file.flush()
            return lock_file
        except (IOError, OSError):
            return None
    else:
        # Unix: use fcntl file locking
        try:
            import fcntl
            lock_file = open(lock_path, "w")
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
            return lock_file
        except (IOError, OSError):
            return None


if __name__ == "__main__":
    _lock = _acquire_instance_lock()
    if _lock is None:
        log.warning("Another Bark instance is already running. Exiting.")
        sys.exit(0)
    try:
        main()
    except Exception:
        log.exception("Fatal error")
        raise
