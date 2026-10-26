"""Recette guidée du Zwift Click (lot X8, recette 1.0 ligne 6).

    python -m openride_core.tools.click_recette                  # Click réel, 30 min
    python -m openride_core.tools.click_recette --minutes 10 --rappel 2
    python -m openride_core.tools.click_recette --sim            # sans matériel (Click simulé)
    python -m openride_core.tools.click_recette --materiel       # matériel à préparer

Avec les vrais fournisseurs du core (deux boîtiers, comme `build_inputs`), l'outil :
1. attend la connexion des boîtiers (un appui réveille chacun) ;
2. demande chaque bouton tour à tour (« + », « − » du boîtier gauche, B et Y du boîtier droit, appuis
   longs) et coche ce qu'il reçoit : événement décodé, boîtier qui l'a envoyé, délai de réponse ;
3. surveille ensuite pendant `--minutes` (30 par défaut) en demandant un appui sur chaque boîtier
   toutes les `--rappel` minutes : silences de chaque boîtier (aucune notification alors que le lien
   tient, le défaut du boîtier gauche de l'essai 69), coupures et reprises, notifications sans bouton
   (types de messages), batterie.

L'essai est guidé (module `guide`) : rappel du matériel, consigne en grand avec compte à rebours,
bip à chaque appui demandé, bip d'alerte quand un boîtier se tait ou se coupe, résultat de chaque
appui à l'écran et dans `guide.jsonl`.

Écrit `rapport.txt`, `rapport.json` et `notifications.csv` (une ligne par seconde et par boîtier) dans
`~/OpenRide/click_recette/<date>_<heure>/`. L'adresse des boîtiers n'est écrite que dans ce dossier local.
Code de sortie : 0 si toutes les étapes guidées sont reçues et qu'aucun boîtier ne s'est tu ni coupé,
1 sinon.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import zwift_click
from ..input_providers import ClickPair, ZwiftClickProvider
from ..zwift_click import InputEvent
from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "click_recette"
SILENCE_S = 2.0          # un boîtier connecté envoie environ 10 notifications par seconde
STEP_TIMEOUT_S = 30.0
BIT_NAMES = {bit: name for name, bit in zwift_click.KEYPAD_BITS.items()}
BUTTON_LABELS = {"PLUS": "+", "MINUS": "−"}


@dataclass
class GuidedStep:
    key: str
    prompt: str
    event: InputEvent
    button: str           # nom du bouton dans KEYPAD_BITS (touche attendue dans la trame)


STEPS = (
    GuidedStep("plus", "Appuie brièvement sur + (boîtier droit)", InputEvent.PLUS_SHORT, "PLUS"),
    GuidedStep("minus", "Appuie brièvement sur − (boîtier gauche)", InputEvent.MINUS_SHORT, "MINUS"),
    GuidedStep("b", "Appuie brièvement sur B (boîtier droit, « − » de secours)", InputEvent.MINUS_SHORT, "B"),
    GuidedStep("y", "Appuie sur Y (boîtier droit, pause)", InputEvent.PAUSE, "Y"),
    GuidedStep("plus_long", "Appui long sur + (une seconde)", InputEvent.PLUS_LONG, "PLUS"),
    GuidedStep("minus_long", "Appui long sur − (une seconde)", InputEvent.MINUS_LONG, "MINUS"),
)
REMINDER = GuidedStep("rappel", "Rappel : appuie brièvement sur − (boîtier gauche)",
                      InputEvent.MINUS_SHORT, "MINUS")


@dataclass
class UnitStats:
    """Tout ce qu'un boîtier a envoyé, par adresse."""
    address: str
    notifications: int = 0
    first_at: float | None = None
    last_at: float | None = None
    buttons: dict[str, int] = field(default_factory=dict)      # touche → nombre de trames où elle est appuyée
    events: dict[str, int] = field(default_factory=dict)       # événement décodé → nombre
    other_types: dict[str, int] = field(default_factory=dict)  # type de message sans bouton → nombre
    battery_pct: int | None = None
    silences: list[tuple[float, float]] = field(default_factory=list)   # (début, durée) avec le lien tenu
    connects: list[float] = field(default_factory=list)
    drops: list[float] = field(default_factory=list)
    per_second: dict[int, int] = field(default_factory=dict)

    @property
    def side(self) -> str:
        """Boîtier gauche (− et flèches) ou droit (+, A, B, Y, Z), d'après les touches reçues."""
        left = sum(self.buttons.get(b, 0) for b in ("MINUS", "LEFT", "UP", "RIGHT", "DOWN"))
        right = sum(self.buttons.get(b, 0) for b in ("A", "B", "Y", "Z"))
        if left and not right:
            return "gauche"
        if right:
            return "droit"
        return "?"

    def max_silence(self) -> float:
        return max((d for _, d in self.silences), default=0.0)


class Recorder:
    """Reçoit les trames brutes et les événements de chaque boîtier, suit liaisons et silences."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self.clock = clock
        self.t0 = clock()
        self.units: dict[str, UnitStats] = {}
        self.events: list[tuple[float, str, InputEvent]] = []   # (t, adresse, événement)
        self._silent_since: dict[str, float] = {}

    def t(self) -> float:
        return self.clock() - self.t0

    def unit(self, address: str) -> UnitStats:
        if address not in self.units:
            self.units[address] = UnitStats(address)
        return self.units[address]

    def raw(self, address: str, data: bytes) -> None:
        t = self.t()
        u = self.unit(address)
        u.notifications += 1
        u.first_at = t if u.first_at is None else u.first_at
        u.last_at = t
        u.per_second[int(t)] = u.per_second.get(int(t), 0) + 1
        since = self._silent_since.pop(address, None)
        if since is not None:
            u.silences.append((since, t - since))
        msg_type, fields = zwift_click.parse_async(data)
        if msg_type == zwift_click.MSG_KEYPAD_STATUS:
            mask = fields.get(1, zwift_click.KEYPAD_ALL_RELEASED) & 0xFFFFFFFF
            for bit in range(32):
                if not (mask >> bit) & 1:
                    name = BIT_NAMES.get(bit, f"bit{bit}")
                    u.buttons[name] = u.buttons.get(name, 0) + 1
        elif msg_type == zwift_click.MSG_CLICK_NOTIFICATION:
            buttons = zwift_click.parse_click_buttons(data)
            for name, down in (("PLUS", buttons.plus_pressed), ("MINUS", buttons.minus_pressed)):
                if down:
                    u.buttons[name] = u.buttons.get(name, 0) + 1
        elif msg_type == zwift_click.MSG_BATTERY_LEVEL:
            u.battery_pct = fields.get(2, u.battery_pct)
        else:
            key = f"0x{msg_type:02X}" if msg_type >= 0 else "vide"
            u.other_types[key] = u.other_types.get(key, 0) + 1

    def event(self, address: str, ev: InputEvent) -> None:
        u = self.unit(address)
        u.events[ev.value] = u.events.get(ev.value, 0) + 1
        self.events.append((self.t(), address, ev))

    def link(self, address: str, up: bool) -> None:
        (self.unit(address).connects if up else self.unit(address).drops).append(self.t())
        if not up:
            self._silent_since.pop(address, None)

    def check_silence(self, connected: dict[str, bool]) -> None:
        """À appeler régulièrement : ouvre un silence quand un boîtier connecté ne dit plus rien."""
        t = self.t()
        for address, up in connected.items():
            u = self.unit(address)
            if not up or address in self._silent_since or u.last_at is None:
                continue
            if t - u.last_at > SILENCE_S:
                self._silent_since[address] = u.last_at

    def silent(self) -> dict[str, float]:
        """Boîtiers muets en ce moment : adresse → début du silence."""
        return dict(self._silent_since)

    def close(self) -> None:
        t = self.t()
        for address, since in self._silent_since.items():
            self.unit(address).silences.append((since, t - since))
        self._silent_since.clear()


class TracedClickProvider(ZwiftClickProvider):
    """Fournisseur réel du core, avec un relevé de chaque trame et de chaque événement."""

    def __init__(self, recorder: Recorder, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recorder = recorder

    @property
    def unit_address(self) -> str:
        # Adresse réservée dès la recherche : la batterie arrive avant la fin de la connexion.
        return str(self._mine or self._conn_address)

    def _on_async(self, ch: Any, data: bytearray) -> None:
        before = self.events.qsize()
        self.recorder.raw(self.unit_address, bytes(data))
        super()._on_async(ch, data)
        # Les événements ajoutés à la file viennent de ce boîtier.
        added = list(self.events._queue)[before:]   # type: ignore[attr-defined]
        for ev in added:
            self.recorder.event(self.unit_address, ev)


@dataclass
class StepResult:
    key: str
    prompt: str
    ok: bool
    delay_s: float | None
    unit: str | None
    detail: str


async def wait_step(rec: Recorder, step: GuidedStep, timeout: float, after: float,
                    tick: Callable[[], None] | None = None) -> StepResult:
    """Attend l'événement de l'étape après `after` ; la touche attendue doit figurer dans la trame."""
    end = rec.t() + timeout
    seen_idx = 0
    while rec.t() < end:
        if tick:
            tick()
        for t, address, ev in rec.events[seen_idx:]:
            if t >= after and ev == step.event:
                u = rec.unit(address)
                key_ok = u.buttons.get(step.button, 0) > 0
                detail = f"{ev.value} reçu"
                if not key_ok:
                    detail += f", touche {step.button} jamais vue dans les trames"
                return StepResult(step.key, step.prompt, key_ok, t - after, address, detail)
        seen_idx = len(rec.events)
        await asyncio.sleep(0.05)
    return StepResult(step.key, step.prompt, False, None, None, f"{step.event.value} non reçu en {timeout:.0f} s")


Prompter = Callable[[str], None]


def unit_label(rec: Recorder, address: str | None) -> str:
    return "" if address is None else f" du boîtier {rec.unit(address).side} ({address})"


def plain_guide() -> Guide:
    """Guide sans écran ni son : de simples lignes (tests, sortie redirigée)."""
    return Guide("Recette du Zwift Click", sound=False, screen=False)


async def run_recette(providers: list[TracedClickProvider], rec: Recorder, minutes: float, reminder_min: float,
                      prompt: Prompter | None = None, step_timeout: float = STEP_TIMEOUT_S,
                      connect_timeout: float = 120.0, tick_s: float = 0.25,
                      guide: Guide | None = None) -> dict[str, Any]:
    g = guide or plain_guide()
    tasks = [asyncio.create_task(p.run()) for p in providers]
    link: dict[int, bool] = {}
    stop = asyncio.Event()
    n_steps = len(STEPS)

    def ask(text: str, seconds: float, index: int | None = None, total: int | None = None,
            detail: str = "") -> None:
        g.step(text, seconds, detail, index=index, total=total)
        if prompt:
            prompt(text)

    def show(res: StepResult) -> None:
        delay = f" en {res.delay_s:.1f} s" if res.delay_s is not None else ""
        g.measure(res.prompt, f"{res.detail}{unit_label(rec, res.unit)}{delay}", ok=res.ok)
        if not res.ok:
            g.sound.play("alerte")

    async def watch_links() -> None:
        alerted: set[str] = set()
        while not stop.is_set():
            for i, p in enumerate(providers):
                up = p.status == "CONNECTED"
                if up != link.get(i, False):
                    link[i] = up
                    rec.link(p.unit_address, up)
                    side = rec.unit(p.unit_address).side
                    if up:
                        g.note(f"boîtier {side} ({p.unit_address}) connecté à {rec.t():.0f} s")
                    else:
                        g.alert(f"Boîtier {side} coupé à {rec.t():.0f} s")
            rec.check_silence({p.unit_address: link.get(i, False) for i, p in enumerate(providers)})
            silent = rec.silent()
            for address, since in silent.items():
                if address not in alerted:
                    alerted.add(address)
                    g.alert(f"Boîtier {rec.unit(address).side} muet depuis {since:.0f} s : le lien tient "
                            "mais plus aucune notification")
            for address in alerted - set(silent):
                alerted.discard(address)
                g.banner = ""
                g.note(f"boîtier {rec.unit(address).side} reparle à {rec.t():.0f} s")
            g.tick()
            await asyncio.sleep(tick_s)

    watcher = asyncio.create_task(watch_links())
    results: list[StepResult] = []
    try:
        ask("Appuie sur un bouton de chaque boîtier pour les réveiller", connect_timeout)
        end = rec.t() + connect_timeout
        while rec.t() < end and sum(link.values()) < len(providers):
            await asyncio.sleep(0.2)
        connected = sum(link.values())
        g.measure("boîtiers connectés", f"{connected} sur {len(providers)}", ok=connected == len(providers))
        await asyncio.sleep(1.0)
        for k, step in enumerate(STEPS):
            after = rec.t()
            ask(step.prompt, step_timeout, k + 1, n_steps)
            res = await wait_step(rec, step, step_timeout, after, g.tick)
            show(res)
            results.append(res)
            await asyncio.sleep(0.5)
        # Surveillance.
        soak_end = rec.t() + minutes * 60.0
        next_reminder = rec.t() + reminder_min * 60.0
        surveil = ("Surveillance : roule normalement, ne touche pas au Click",
                   f"un appui sera demandé toutes les {reminder_min:g} min (bip)")
        g.step(surveil[0], soak_end - rec.t(), surveil[1])
        while rec.t() < soak_end:
            if rec.t() >= next_reminder:
                after = rec.t()
                ask(REMINDER.prompt, min(step_timeout, soak_end - rec.t() + 1.0))
                res = await wait_step(rec, REMINDER, min(step_timeout, soak_end - rec.t() + 1.0), after, g.tick)
                res.key = f"rappel_{int(after // 60)}min"
                show(res)
                results.append(res)
                next_reminder += reminder_min * 60.0
                if rec.t() < soak_end:
                    g.step(surveil[0], soak_end - rec.t(), surveil[1], beep=False)
            await asyncio.sleep(0.2)
    finally:
        stop.set()
        await watcher
        for p in providers:
            p.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
        rec.close()
    return build_report(rec, results, minutes)


def build_report(rec: Recorder, results: list[StepResult], minutes: float) -> dict[str, Any]:
    units = []
    for u in rec.units.values():
        if u.address == "?":
            continue
        span = (u.last_at or 0.0) - (u.first_at or 0.0)
        units.append({
            "address": u.address, "side": u.side, "notifications": u.notifications,
            "rate_per_s": u.notifications / span if span > 0 else 0.0,
            "buttons": u.buttons, "events": u.events, "other_types": u.other_types,
            "battery_pct": u.battery_pct, "connects": len(u.connects), "drops": len(u.drops),
            "drop_times_s": [round(t, 1) for t in u.drops],
            "silences": [{"start_s": round(s, 1), "duration_s": round(d, 1)} for s, d in u.silences],
            "max_silence_s": round(u.max_silence(), 1),
        })
    sides = {u["address"]: u["side"] for u in units}
    steps = [{**asdict(r), "side": sides.get(r.unit or "", None)} for r in results]
    guided = [r for r in results if not r.key.startswith("rappel")]
    ok = (all(r.ok for r in results) and bool(units)
          and all(not x["silences"] and not x["drops"] for x in units))
    return {"ok": ok, "minutes": minutes, "steps": steps,
            "guided_ok": sum(r.ok for r in guided), "guided_total": len(guided), "units": units}


def report_text(report: dict[str, Any]) -> str:
    lines = [f"Recette guidée du Zwift Click : {'tout passe' if report['ok'] else 'À REVOIR'}", "",
             f"Étapes guidées : {report['guided_ok']}/{report['guided_total']}"]
    for s in report["steps"]:
        delay = f" en {s['delay_s']:.1f} s" if s["delay_s"] is not None else ""
        unit = f" du boîtier {s['side']} ({s['unit']})" if s["unit"] else ""
        lines.append(f"  {'OK ' if s['ok'] else 'NON'} {s['prompt']} : {s['detail']}{unit}{delay}")
    lines += ["", f"Boîtiers (surveillance de {report['minutes']:g} min) :"]
    for u in report["units"]:
        lines.append(f"  Boîtier {u['side']} ({u['address']}) : {u['notifications']} notifications "
                     f"({u['rate_per_s']:.1f} par seconde), batterie {u['battery_pct'] if u['battery_pct'] is not None else '?'} %")
        lines.append(f"    touches vues : {', '.join(f'{BUTTON_LABELS.get(k, k)} ×{v}' for k, v in sorted(u['buttons'].items())) or 'aucune'}")
        lines.append(f"    événements : {', '.join(f'{k} ×{v}' for k, v in sorted(u['events'].items())) or 'aucun'}")
        lines.append(f"    connexions {u['connects']}, coupures {u['drops']}"
                     + (f" (à {', '.join(f'{t:.0f} s' for t in u['drop_times_s'])})" if u["drops"] else ""))
        if u["silences"]:
            lines.append(f"    SILENCES (lien tenu, plus de {SILENCE_S:.0f} s sans notification) : "
                         + ", ".join(f"{s['duration_s']:.0f} s à partir de {s['start_s']:.0f} s" for s in u["silences"]))
        else:
            lines.append("    aucun silence")
        if u["other_types"]:
            lines.append(f"    messages sans bouton : {', '.join(f'{k} ×{v}' for k, v in sorted(u['other_types'].items()))}")
    if not report["units"]:
        lines.append("  aucun boîtier n'a envoyé de notification")
    return "\n".join(lines) + "\n"


def write_outputs(rec: Recorder, report: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "rapport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "rapport.txt").write_text(report_text(report), encoding="utf-8")
    addrs = [u for u in rec.units if u != "?"]
    last = max((max(u.per_second, default=0) for u in rec.units.values()), default=0)
    with (out / "notifications.csv").open("w", encoding="utf-8") as fh:
        fh.write("t_s;" + ";".join(f"{rec.units[a].side}_{a}" for a in addrs) + "\n")
        for sec in range(last + 1):
            fh.write(f"{sec};" + ";".join(str(rec.units[a].per_second.get(sec, 0)) for a in addrs) + "\n")


def make_providers(rec: Recorder, cfg: Any, sim: Any = None) -> list[TracedClickProvider]:
    d, pair = cfg.drivers, ClickPair()
    kw: dict[str, Any] = {"device_finder": sim.find_device, "client_factory": sim.client_factory} if sim else {}
    addr_plus = None if sim else (d.click_address or None)
    addr_minus = None if sim else (d.click_minus_address or None)
    return [TracedClickProvider(rec, addr_plus, d.click_short_max_s, d.click_long_min_s, pair=pair, **kw),
            TracedClickProvider(rec, addr_minus, d.click_short_max_s, d.click_long_min_s, pair=pair,
                                optional=True, **kw)]


async def sim_user(world: Any, prompts: asyncio.Queue[str]) -> None:
    """Cycliste simulé : réveille les boîtiers puis fait ce que demande chaque consigne."""
    plus = world._box("+")    # boîtier droit
    minus = world._box("-")   # boîtier gauche
    loop = asyncio.get_running_loop()

    def tap(box: Any, button: str, duration: float = 0.12, delay: float = 0.0) -> None:
        loop.call_later(delay, box.set_button, button, True)
        loop.call_later(delay + duration, box.set_button, button, False)

    while True:
        text = await prompts.get()
        await asyncio.sleep(0.4)
        if "réveiller" in text:
            tap(plus, "+")
            tap(minus, "-")
        elif "long sur +" in text:
            await world.press("+", 1.0)
        elif "long sur −" in text:
            await world.press("-", 1.0)
        elif "sur +" in text:
            await world.press("+")
        elif "sur −" in text:
            await world.press("-")
        elif "sur B" in text:
            tap(plus, "B")
        elif "sur Y" in text:
            tap(plus, "Y")


async def main_async(args: argparse.Namespace) -> int:
    from .. import config as config_mod

    cfg = config_mod.load(args.config)
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    guide = Guide("Recette du Zwift Click", out / "guide.jsonl", sound=False if args.muet else None)
    guide.prepare("click_recette", wait=not args.sim and not args.sans_attente and sys.stdin.isatty(),
                  auto_s=0 if args.sim else 10.0)
    rec = Recorder(time.monotonic)
    prompt: Prompter | None = None
    extra: list[asyncio.Task[Any]] = []
    sim = None
    if args.sim:
        from .. import sim_scenarios
        spec = sim_scenarios.load_scenario(args.scenario) if args.scenario else {
            "click": {"appear_at": 0.0}, "trainer": None, "hr": None, "events": []}
        sim = sim_scenarios.build_world(spec, trainer=False, hr=False)
        prompts: asyncio.Queue[str] = asyncio.Queue()

        prompt = prompts.put_nowait
        extra = [asyncio.create_task(sim.run()), asyncio.create_task(sim_user(sim, prompts))]
    providers = make_providers(rec, cfg, sim)
    try:
        report = await run_recette(providers, rec, args.minutes, args.rappel, prompt,
                                   connect_timeout=20.0 if args.sim else 120.0, guide=guide)
    finally:
        if sim is not None:
            sim.stop()
        for t in extra:
            t.cancel()
        await asyncio.gather(*extra, return_exceptions=True)
    guide.finish(report["ok"], "Recette finie : tout passe" if report["ok"] else "Recette finie : voir le rapport")
    guide.close()
    write_outputs(rec, report, out)
    print()
    print(report_text(report), end="")
    print(f"Rapport : {out}")
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recette guidée du Zwift Click (lot X8).")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--minutes", type=float, default=30.0, help="durée de la surveillance (défaut 30)")
    ap.add_argument("--rappel", type=float, default=5.0, help="minutes entre deux rappels d'appui (défaut 5)")
    ap.add_argument("--sim", action="store_true", help="Click simulé (ble_sim), cycliste simulé")
    ap.add_argument("--scenario", help="avec --sim : scénario (nom ou fichier JSON) pour le Click simulé")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("-v", "--verbose", action="store_true", help="journal du Click à l'écran")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    args = ap.parse_args(argv)
    if args.materiel:
        from .guide import materials_text
        print(materials_text(["click_recette"]), end="")
        return 0
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    try:
        return asyncio.run(main_async(args))
    except (KeyboardInterrupt, EOFError):
        print("\nInterrompu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
