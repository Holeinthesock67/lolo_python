"""Lot BR5 (R5 de la stratégie des bots) : gestes de base des bots du Grand Prix et du Dernier survivant (`bot_tactics.MODE_TACTICS`).

Règle du propriétaire (21 novembre) : ce qui est propre au mode passe d'abord (voie d'esquive du Grand Prix,
sprint de survie et économie du Dernier survivant) ; les gestes de base (répondre aux attaques, attaquer avant
l'arche) ne jouent que quand le mode n'a rien à dire. L'abri (roue suivie, lots AS1 et AS2) marchait déjà dans
tous les modes. Vérification en simulation : courses complètes où le cycliste attaque.
"""

from __future__ import annotations

from openride_core import bot_tactics as bt
from openride_core.bots import SURVIVAL_SAFE_CP, ProfileBot

from test_grandprix_session import env as gp_env  # noqa: F401  (fixture partagée)
from test_survivor_session import env  # noqa: F401  (fixture partagée)


def bot(mode: str, profile: str = "rouleur") -> ProfileBot:
    b = ProfileBot(profile, bot_id="bot1")
    b.set_scale(1.0)
    bt.start_race([b], 1, mode)
    return b


def test_table_rows_of_the_two_modes() -> None:
    gp, ds = bt.MODE_TACTICS["grandprix"], bt.MODE_TACTICS["survivor"]
    assert gp.responses and not gp.relays and not gp.attacks       # pas de relais organisés au Grand Prix
    assert ds.responses and ds.attacks and not ds.relays
    assert not (gp.form or ds.form)                                 # calibrage des bots inchangé (± 2 %)
    assert not (gp.racing or ds.racing)                             # comportements de piste : vélodrome seul
    assert set(bt.GAME_MODES) == {"grandprix", "survivor"}


def test_safe_survivor_saves_energy_instead_of_chasing() -> None:
    """À l'abri (plus de 5 s devant le dernier), le mode dit « économise » : pas de réponse."""
    b = bot("survivor")
    b.tactics.respond_to, b.tactics.respond_until = "rider", 1e9
    b.survival = (800.0, False, True, 350.0)
    assert b.mode_speaks()
    b.step(0.05)
    assert b.tactics.respond_to is None
    assert b.power_w <= SURVIVAL_SAFE_CP * b.cp_w + 1e-6


def test_survival_sprint_keeps_priority_over_an_attack() -> None:
    b = bot("survivor")
    b.tactics.attack_until, b.tactics.attack_factor = 1e9, 1.3
    b.survival = (300.0, True, False, 350.0)
    assert b.mode_speaks()
    b.step(0.05)
    assert b.tactics.attack_until < 0 and b.power_w == b.spec.survival * b.cp_w


def test_threatened_far_from_the_arch_answers_an_attack() -> None:
    """Menacé mais loin de l'arche : le mode se tait, le bot suit le départ (1,25 × CP)."""
    b = bot("survivor")
    b.survival = (900.0, True, False, 350.0)
    assert not b.mode_speaks()
    b.tactics.respond_to, b.tactics.respond_until = "rider", 1e9
    b.step(0.05)
    assert b.tactics.respond_to == "rider" and b.power_w >= bt.RESPONSE_FACTOR * b.cp_w - 1e-6


def test_grandprix_lane_held_silences_the_response() -> None:
    b = bot("grandprix")
    b.tactics.respond_to, b.tactics.respond_until = "rider", 1e9
    b.mode_hold = True                       # esquive du lot GP3 : voie tenue
    b.step(0.05)
    assert b.tactics.respond_to is None
    b.mode_hold = False
    b.tactics.respond_to, b.tactics.respond_until = "rider", 1e9
    b.step(0.05)
    assert b.power_w >= bt.RESPONSE_FACTOR * b.cp_w - 1e-6


def test_field_judges_no_departure_while_the_mode_holds_the_bot() -> None:
    """Le cycliste part (écart qui grandit) : un bot tenu par le mode ne le juge pas, un bot libre le suit."""
    held, free = (ProfileBot("rouleur", bot_id=i) for i in ("held", "free"))
    for b in (held, free):
        b.set_scale(1.0)
        b.tactics.character = bt.Character(follow_flat=1.0)
        b.physics.v = 10.0
    bt.start_race([held, free], 1, "grandprix")
    held.mode_hold = True
    field = bt.Field()
    rider_s = 5.0
    t = 0.0
    while t < bt.RESPONSE_START_S + 6.0:
        t += bt.TICK_S
        if t > bt.RESPONSE_START_S:
            rider_s += 3.0 * bt.TICK_S       # 3 m/s plus vite que les bots : 0,3 s d'écart de plus par seconde
        for b in (held, free):
            b.physics.s += 10.0 * bt.TICK_S
        rider_s += 10.0 * bt.TICK_S
        bt.update_field(field, [held, free], (rider_s, 11.0), bt.TICK_S)
    assert free.tactics.responses == 1 and held.tactics.responses == 0


def test_start_race_releases_a_lane_held_in_the_previous_race() -> None:
    b = bot("grandprix")
    b.mode_hold = True
    bt.start_race([b], 2, "none")
    assert not b.mode_hold


def _surge(run, s, total_s: float, at_s: float, dur_s: float, hi_w: float) -> None:
    """Le cycliste attaque : `hi_w` pendant `dur_s` à partir de `at_s`, puis revient à sa puissance."""
    base = s.driver.base_power_w
    run(s, at_s)
    s.driver.base_power_w = hi_w
    run(s, dur_s)
    s.driver.base_power_w = base
    run(s, total_s - at_s - dur_s)


def test_grandprix_bots_answer_the_rider_attack(gp_env) -> None:
    make, run, _, _ = gp_env
    s, _, errors = make(7560, opponents=4, laps=3)
    s.bot_tactics_seed = 1
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    bots, gp = list(s.bots), s.grandprix
    assert {b.tactics.mode for b in bots} == {"grandprix"}
    _surge(run, s, 900.0, 90.0, 40.0, 480.0)
    assert sum(b.tactics.responses for b in bots) >= 1
    assert sum(b.tactics.attacks for b in bots) == 0                # pas d'attaque au Grand Prix
    assert all(r.finished is not None for r in gp.racers.values() if r.id in ("me", "bot1"))


def test_survivor_bots_attack_and_answer_then_one_elimination_per_arch(env) -> None:
    make, run, _ = env[0], env[1], env[2]
    s, _, errors = make(7570, power_w=260.0, opponents=4, spacing_km=1, level_pct=100)
    s.bot_tactics_seed = 1
    s._on_command("start", {"mode": "survivor"}, 2)
    assert not errors
    bots, surv = list(s.bots), s.survivor
    assert {b.tactics.mode for b in bots} == {"survivor"}
    _surge(run, s, 1500.0, 90.0, 40.0, 480.0)
    assert sum(b.tactics.responses for b in bots) >= 1 and sum(b.tactics.attacks for b in bots) >= 1
    assert surv.winner is not None
    outs = sorted(r.out_arch for r in surv.racers.values() if r.out_arch is not None)
    assert outs == [1, 2, 3, 4]                                     # une élimination par arche


def test_wtf_and_classic_keep_their_rows(gp_env) -> None:
    make = gp_env[0]
    s, _, _ = make(7580)
    assert s._mode_tactics(None) is None and s._mode_tactics("survivor") == "survivor"
    s.wtf = object()                         # WTF : règles propres, bots sans tactique (inchangé)
    assert s._mode_tactics("grandprix") is None
