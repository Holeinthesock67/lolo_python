"""Frein lâché : règle commune du pilote et du rapport des décrochages (lot FR1, brake_watch.py)."""

import pytest

from openride_core import brake_watch as bw


def run(frames, loaded=True, speed=30.0):
    """`frames` : (t, puissance, cadence) ; rend les événements (t, genre)."""
    watch, out = bw.BrakeWatch(), []
    for t, p, c in frames:
        out += [(t, ev.kind) for ev in watch.step(t, p, c, speed, loaded)]
    return out


def stop_with_lag(lag_s, hz):
    """Effort à 320 W puis arrêt net ; la cadence annoncée reste à 85 tr/min pendant `lag_s`."""
    frames = [(k / hz, 320.0, 85.0) for k in range(int(5 * hz))]
    t0 = 5.0
    frames += [(t0 + k / hz, 0.0, 85.0 if k / hz < lag_s else 0.0) for k in range(int(8 * hz))]
    return frames


def real_loss(hz, seconds=6.0):
    """29/10 : 449 W puis 0 W, cadence gardée à 73 tr/min."""
    frames = [(k / hz, 449.0, 73.0) for k in range(int(5 * hz))]
    return frames + [(5.0 + k / hz, 0.0, 73.0) for k in range(int(seconds * hz))]


def test_pedals_kept():
    assert bw.pedals_kept(80.0, [80.0, 70.0, 60.0])
    assert not bw.pedals_kept(80.0, [80.0, 59.0])        # plus du quart de la cadence perdu
    assert not bw.pedals_kept(45.0, [45.0, 39.0])        # sous 40 tr/min
    assert not bw.pedals_kept(80.0, [])


@pytest.mark.parametrize("lag_s", [1.0, 1.5, 1.9])
@pytest.mark.parametrize("hz", [1.0, 8.0])
def test_stop_with_lagging_cadence_is_never_a_brake_loss(lag_s, hz):
    assert run(stop_with_lag(lag_s, hz)) == []


@pytest.mark.parametrize("hz", [1.0, 8.0])
def test_real_brake_loss_is_confirmed_two_seconds_after_the_drop(hz):
    events = run(real_loss(hz))
    assert [k for _, k in events] == ["brake_loss"]
    assert events[0] == (pytest.approx(5.0 + bw.CONFIRM_S), "brake_loss")


def test_brake_back_after_the_retake_and_never_twice_in_ten_seconds():
    frames = real_loss(8.0, seconds=2.5) + [(7.5 + k / 8, 330.0, 80.0) for k in range(8)]
    frames += [(8.5 + k / 8, 0.0, 80.0) for k in range(40)]   # nouvelle chute 3,5 s après : pas de reprise
    assert [k for _, k in run(frames)] == ["brake_loss", "power_back"]


def test_no_brake_loss_without_effort_or_slow_flywheel():
    assert run(real_loss(8.0), loaded=False) == []            # bloc ERG à 0 W
    assert run(real_loss(8.0), speed=10.0) == []              # volant presque arrêté à la chute
    low = [(k / 8, 140.0, 80.0) for k in range(40)] + [(5.0 + k / 8, 0.0, 80.0) for k in range(40)]
    assert run(low) == []                                     # moins de 150 W avant la chute


def test_power_not_back_and_rider_stopped():
    assert [k for _, k in run(real_loss(1.0, seconds=20.0))] == ["brake_loss", "power_not_back"]
    frames = real_loss(1.0, seconds=3.0) + [(8.0, 0.0, 0.0), (10.0, 300.0, 85.0)]
    assert [k for _, k in run(frames)] == ["brake_loss", "rider_stopped"]
