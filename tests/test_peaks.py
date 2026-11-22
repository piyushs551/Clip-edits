import numpy as np

from dailyclip import peaks


def test_window_energy_shapes():
    s = (np.ones(8000) * 1000).astype(np.int16)  # 1 s at 8 kHz
    e, win = peaks.window_energy(s)
    assert win == 0.05 and len(e) == 20


def test_find_peaks_threshold_and_min_gap():
    win = 0.05
    e = np.full(2000, 0.001)           # 100 s of quiet
    for t in (10.0, 10.5, 40.0, 70.0):  # two bursts 0.5 s apart, then two others
        e[int(t / win)] = 1.0 if t != 10.5 else 0.9
    found = peaks.find_peaks(e, win, percentile=95, min_gap_s=4.0)
    times = [round(p["time"]) for p in found]
    assert times == [10, 40, 70]       # 10.5 suppressed by 4 s min gap


def test_find_peaks_empty_and_silence():
    assert peaks.find_peaks(np.zeros(0), 0.05) == []
    assert peaks.find_peaks(np.zeros(100), 0.05) == []


def test_max_peaks_keeps_strongest():
    win = 0.05
    e = np.full(4000, 0.001)
    for i, t in enumerate((10, 30, 50, 70, 90)):
        e[int(t / win)] = 0.5 + i * 0.1
    found = peaks.find_peaks(e, win, max_peaks=2)
    assert [round(p["time"]) for p in found] == [70, 90]
