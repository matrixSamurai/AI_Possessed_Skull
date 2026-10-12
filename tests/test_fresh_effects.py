import threading
import numpy as np
from malachi.ambience.engine import AmbienceEngine
from malachi.ambience.fresh_effects import FreshEffects, PROMPTS


def test_fresh_effect_selected_next_with_bounded_bank(settings):
    old = np.zeros(320, np.float32)
    fresh = np.ones(320, np.float32)
    engine = AmbienceEngine(settings, clips=[old] * 16)
    engine.current = old
    engine.install_fresh(fresh)
    assert len(engine.clips) == 16 and engine.current is old
    engine._choose()
    assert engine.current is fresh


def test_worker_coalesces_requests_and_discards_late_result(settings):
    entered, release = threading.Event(), threading.Event()
    calls, installed = [], []

    def generate(prompt, sequence):
        calls.append((prompt, sequence))
        entered.set()
        assert release.wait(2)
        return np.ones(320, np.float32)

    worker = FreshEffects(settings, installed.append, lambda e: None, generate)
    try:
        worker.request()
        assert entered.wait(1)
        for _ in range(20):
            worker.request()
        worker.close()
        release.set()
        worker.thread.join(1)
        assert len(calls) == 1 and not installed
    finally:
        release.set()
        worker.close()


def test_prompt_bag_uses_all_styles_before_repeat(settings):
    worker = FreshEffects(settings, lambda x: None, lambda e: None, lambda *a: None)
    try:
        prompts = [worker._prompt() for _ in PROMPTS]
        assert set(prompts) == set(PROMPTS)
        assert worker._prompt() != prompts[-1]
    finally:
        worker.close()


def test_generation_failure_keeps_cached_audio(settings):
    done = threading.Event()
    events = []

    def fail(*args):
        raise OSError("private credential should not be logged")

    def emit(event):
        events.append(event)
        done.set()

    worker = FreshEffects(settings, lambda x: None, emit, fail)
    try:
        worker.request()
        assert done.wait(1)
        assert "using cached effects" in events[0].detail
        assert "private credential" not in events[0].detail
    finally:
        worker.close()
