"""Machine à états d'une run du Cyber-Rogue (lot R6).

`RunEngine` enchaîne échauffement, salles, couloirs (carte, porte, relance), boss en trois phases et
retour au calme, en appelant la posture et le W'bal (R2), les salles (R3), le Firewall (R4) et le
combat (R5). Il joue un `Scenario` donné ; il ne choisit pas lui-même les salles (R15). Module pur :
la session (R8) fournit la position dans la salle et la vitesse, et applique la pente envoyée.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field, replace

from . import cards as cardlib
from .balance import DEFAULT_BALANCE, RogueBalance, balance_hash
from .combat import DONE, RECOVERY, CombatInputs, combat_start, combat_step
from .firewall import Firewall
from .posture import ARRET, PostureState, posture_step
from .rooms import Room, RoomRider, generate_room
from .wbal import WbalState, wbal_initial, wbal_step

WARMUP, ROOM, CORRIDOR, BOSS = "WARMUP", "ROOM", "CORRIDOR", "BOSS"
COOLDOWN, RESULTS = "COOLDOWN", "RESULTS"
WINDOW_KINDS = ("arch", "strike_target", "parry_zone", "pad", "purge", "tunnel")


@dataclass(frozen=True)
class Step:
    """Étape d'un scénario. Un couloir porte ses portes (deux salles proposées) ; sans portes, il ne
    propose qu'une carte (dernier couloir avant le boss). La salle jouée après un couloir à portes est
    celle de la porte choisie : elle ne figure pas dans la liste des étapes."""
    kind: str                            # warmup, room, corridor, boss, cooldown
    nominal_s: float
    archetype: str | None = None
    variant: str = ""
    objective: str = "threshold"
    doors: tuple = ()


@dataclass(frozen=True)
class Scenario:
    objective: str
    duration_min: int
    seed: int
    steps: tuple

    @property
    def rooms_total(self) -> int:
        return sum(1 for s in self.steps if s.kind == "room") + sum(
            1 for s in self.steps if s.kind == "corridor" and s.doors)


@dataclass(frozen=True)
class RunInputs:
    power_w: float
    cadence_rpm: float
    gear: int
    ftp_w: float
    s_m: float = 0.0                     # distance dans la salle en cours
    v_mps: float = 0.0
    buttons: frozenset = frozenset()     # Z_SHORT, Z_LONG, A_SHORT, A_LONG ; les vitesses sont à la session
    input_lost: bool = False             # Click perdu : le Firewall s'arrête


@dataclass
class RunOutputs:
    phase: str
    grade_enemy: float                   # pente de l'ennemi après cartes
    grade_sent: float                    # pente envoyée au trainer (formule centrée, bornée)
    force_gear: int | None               # retour automatique d'Overdrive : à appliquer une fois
    rogue: dict                          # objet `rogue` de `state`
    messages: list = field(default_factory=list)    # messages `room` et `loot` à émettre
    journal: list = field(default_factory=list)
    finished: bool = False


def grade_sent(grade_enemy: float, gear: int, b: RogueBalance = DEFAULT_BALANCE) -> float:
    """Formule centrée (décision Q2) : pente de l'ennemi + (vitesse − 6) points, bornée à la plage du trainer."""
    g = grade_enemy + (gear - b.gear_ref) * b.gear_grade_pts
    return min(max(g, b.sent_grade_min), b.sent_grade_max)


class RunEngine:
    def __init__(self, scenario: Scenario, rider: RoomRider, w_prime_j: float, cp_w: float,
                 balance: RogueBalance = DEFAULT_BALANCE, lives: int = 0) -> None:
        self.sc, self.rider, self.b = scenario, rider, balance
        self.lives = lives                  # vies en réserve (R9) : la défaite en consomme une, sans perte d'or
        self.lives_used = 0
        self.w_prime_j, self.cp_w = w_prime_j, cp_w
        self.idx = -1
        self.phase = WARMUP
        self.t_phase = 0.0
        self.t_total = 0.0
        self.posture = PostureState()
        self.wbal = wbal_initial(w_prime_j)
        self.deck: tuple = ()
        self.relics: tuple = ()
        self.gold = 0.0
        self.shield = balance.shield_max
        self.last_gear = balance.gear_ref
        self.next_room_id = 1
        self.rooms_started = 0
        self.room: Room | None = None
        self.room_id = 0
        self.boss_phase: int | None = None
        self.combat = None
        self.firewall: Firewall | None = None
        self.gold_lost_seen = 0.0
        # effets de cartes
        self.roller_hold_until = 0.0
        self.prev_raw = 0.0
        self.spring_until = 0.0
        self.overdrive_until = 0.0
        self.overdrive_ready_at = 0.0
        self.inversion_until = 0.0
        self.inversion_used = False
        self.force_gear: int | None = None
        # couloir et relique
        self.loot_id = 0
        self.stage: str | None = None       # "card", "door" ou None
        self.offer: tuple = ()
        self.focus: int | None = None
        self.rerolls = 0
        self.door_steps: tuple = ()
        self.door_ids: tuple = ()
        self.door_pick = 0
        self.relic_offered = False
        self.relic_taken = False
        # bilan
        self.rooms_won = self.rooms_fled = self.rooms_skipped = self.defeats = 0
        self.perfect_shifts = 0
        self.boss = "not_reached"
        self.result: str | None = None
        self.rooms_total0 = scenario.rooms_total
        self._spring_adr = 0.0
        self.cur_spec: Step | None = None
        self._journal: list = []
        self._hash_logged = False
        self._previews: dict = {}
        self._enter(0)

    # --- étapes -----------------------------------------------------------------------------

    def _enter(self, i: int) -> None:
        self.idx = i
        self.t_phase = 0.0
        step = self.sc.steps[i]
        self.phase = {"warmup": WARMUP, "room": ROOM, "corridor": CORRIDOR, "boss": BOSS,
                      "cooldown": COOLDOWN}[step.kind]
        self._journal.append(f"rogue phase={self.phase} step={i} t={self.t_total:.1f}")

    def _begin(self, inp, messages) -> None:
        """Démarre l'étape courante : salle, boss ou couloir."""
        if self.phase == ROOM:
            messages += self._start_room(self._step, self._take_room_id(), None, inp.gear, inp.s_m)
        elif self.phase == BOSS:
            n = sum(1 for s in self.sc.steps[:self.idx + 1] if s.kind == "boss")
            messages += self._start_room(self._step, self._take_room_id(), n, inp.gear, inp.s_m)
        elif self.phase == CORRIDOR:
            self._enter_corridor(inp, messages)

    @property
    def _step(self) -> Step:
        return self.sc.steps[self.idx]

    def _eff_balance(self) -> RogueBalance:
        key = (self.deck, self.relics)
        cached = getattr(self, "_bx", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        bx = self._compute_balance()
        self._bx = (key, bx)
        return bx

    def _compute_balance(self) -> RogueBalance:
        b = self.b
        window = b.ps_window_s + (b.relic_ps_window_bonus_s if "relic_window" in self.relics else 0.0)
        if "shifter" in self.deck:
            window = min(window * b.shifter_window_mult, b.shifter_window_max_s)
        shield_max = b.shield_max + (b.relic_shield_bonus if "relic_shield" in self.relics else 0.0)
        return replace(b, ps_window_s=window, shield_max=shield_max)

    def _gold_mult(self) -> float:
        return self.b.gold_mult * (self.b.relic_gold_mult if "relic_gold" in self.relics else 1.0)

    def _start_room(self, spec: Step, room_id: int, boss_phase: int | None, gear: int, s_m: float) -> list:
        self.room = self._previews.pop(room_id, None) or generate_room(
            spec.archetype, spec.variant, spec.objective, spec.nominal_s, self.rider,
            self.sc.seed * 1000 + room_id, self.b)
        self.room_id, self.boss_phase, self.cur_spec = room_id, boss_phase, spec
        bx = self._eff_balance()
        self.combat = replace(combat_start(self.room, self.sc.seed * 1000 + room_id, bx, shield=self.shield, gear=gear),
                              adrenaline=bx.adrenaline_start)
        self.firewall = Firewall(self.room, self.rider, bx, player_s=s_m)
        self.gold_lost_seen = 0.0
        self.inversion_used = False
        self.inversion_until = 0.0
        self.roller_hold_until = 0.0
        self.rooms_started += 1
        self._journal.append(f"rogue room id={room_id} archetype={spec.archetype} variant={self.room.variant} "
                             f"length={self.room.length_m:.0f}")
        return [self.room.to_message(room_id)]

    # --- boucle -----------------------------------------------------------------------------

    def step(self, dt: float, inp: RunInputs) -> RunOutputs:
        self._journal: list = []
        if not self._hash_logged:
            self._hash_logged = True
            self._journal.append(f"rogue balance hash={balance_hash(self.b)}")
        messages: list = []
        events: list = []
        self.t_total += dt
        self.t_phase += dt
        self.force_gear = None
        self.last_gear = inp.gear
        self.posture = posture_step(self.posture, inp.cadence_rpm, inp.power_w, dt, self.b)
        self.wbal = wbal_step(self.wbal, inp.power_w, inp.cadence_rpm, dt, cp_w=self.cp_w,
                              w_prime_j=self.w_prime_j, posture=self.posture.posture, balance=self.b)
        grade = 0.0
        if self.phase == WARMUP:
            grade = self._warmup(dt, inp, messages, events)
        elif self.phase == CORRIDOR:
            grade = self._corridor(dt, inp, messages, events)
        elif self.phase in (ROOM, BOSS, "RECOVERY"):
            grade = self._fight(dt, inp, messages, events)
        elif self.phase == COOLDOWN:
            if self.t_phase >= self._step.nominal_s:
                self._finish_run()
        out_phase = self.phase
        return RunOutputs(
            phase=out_phase, grade_enemy=grade, grade_sent=grade_sent(grade, inp.gear, self.b),
            force_gear=self.force_gear, rogue=self._state(inp, events), messages=messages,
            journal=list(self._journal), finished=self.phase == RESULTS)

    # --- échauffement et couloirs -------------------------------------------------------------

    def _warmup(self, dt, inp, messages, events) -> float:
        step = self._step
        if not self.relic_offered and self.t_phase >= self.b.warmup_relic_s:
            self.relic_offered = True
            self._open_offer(cardlib.draw(f"{self.sc.seed}|relic", self.b.cards_offered, (), cardlib.RELICS),
                             "card", messages)
        if self.stage:
            self._loot_buttons(inp, events, messages, relics=True)
        if self.t_phase >= step.nominal_s:
            self.stage, self.offer, self.focus = None, (), None
            self._next_after_warmup(inp, messages)
        return self.b.warmup_grade_max * min(self.t_phase / max(step.nominal_s, 1e-9), 1.0)

    def _next_after_warmup(self, inp, messages) -> None:
        self._enter(self.idx + 1)
        self._begin(inp, messages)

    def _take_room_id(self) -> int:
        rid = self.next_room_id
        self.next_room_id += 1
        return rid

    def _enter_corridor(self, inp, messages) -> None:
        step = self._step
        self.loot_id += 1
        self.rerolls = 0
        self.door_steps = step.doors
        self.door_ids = tuple(self._take_room_id() for _ in step.doors)
        self.door_pick = 0
        self._open_offer(cardlib.draw(f"{self.sc.seed}|corr|{self.loot_id}|0", self.b.cards_offered, self.deck),
                         "card", messages)
        for spec, rid in zip(step.doors, self.door_ids):    # une salle par porte, pour les aperçus
            room = generate_room(spec.archetype, spec.variant, spec.objective, spec.nominal_s,
                                 self.rider, self.sc.seed * 1000 + rid, self.b)
            self._previews[rid] = room          # la salle choisie est reprise telle quelle au lieu d'être recalculée
            messages.append(room.to_message(rid))

    def _open_offer(self, offer: tuple, stage: str, messages: list) -> None:
        self.offer, self.stage, self.focus = offer, stage, None
        messages.append(self._loot_message())

    def _loot_message(self) -> dict:
        pool = cardlib.ALL
        cards = [{"id": c, "name": pool[c].name, "kind": pool[c].kind, "text": pool[c].text,
                  "replaces_gear": pool[c].replaces_gear} for c in self.offer]
        if self.door_steps:
            doors = [{"side": side, "room_id": rid, "archetype": spec.archetype}
                     for side, spec, rid in zip(("left", "right"), self.door_steps, self.door_ids)]
        else:                               # sans porte : les deux côtés mènent à l'étape suivante
            nxt = self.sc.steps[min(self.idx + 1, len(self.sc.steps) - 1)]
            doors = [{"side": side, "room_id": self.next_room_id, "archetype": nxt.archetype or "boss"}
                     for side in ("left", "right")]
        cost = self.b.reroll_cost + self.b.reroll_step * self.rerolls
        return {"type": "loot", "v": 1, "corridor_id": self.loot_id, "cards": cards, "doors": doors,
                "reroll_cost": cost, "gold": int(self.gold)}

    def _loot_buttons(self, inp, events, messages, relics=False) -> None:
        n_doors = len(self.door_steps)
        for name in sorted(inp.buttons):
            if self.stage is None:
                return
            if name == "A_SHORT":
                if self.stage == "card":
                    self.focus = 0 if self.focus is None else (self.focus + 1) % len(self.offer)
                elif self.stage == "door":
                    self.focus = 3 if self.focus in (None, 4) else 4
            elif name in ("LEFT_SHORT", "RIGHT_SHORT"):
                # Flèches (plan des boutons §7.1) : carte précédente ou suivante, sans boucle ; porte de gauche
                # ou de droite. Sans carte choisie, la première flèche choisit la première carte.
                step = -1 if name == "LEFT_SHORT" else 1
                if self.stage == "card":
                    self.focus = 0 if self.focus is None else min(max(self.focus + step, 0), len(self.offer) - 1)
                elif self.stage == "door":
                    self.focus = 3 if step < 0 else 4
            elif name == "A_LONG" and self.focus is not None:
                if self.stage == "card":
                    cid = self.offer[self.focus]
                    if relics:
                        self.relics += (cid,)
                        if cid == "relic_shield":
                            self.shield += self.b.relic_shield_bonus
                    else:
                        self.deck = cardlib.deck_add(self.deck, cid)
                    events.append("card_taken")
                    self._journal.append(f"rogue card id={cid}")
                    self.stage, self.focus = ("door" if n_doors and not relics else None), None
                elif self.stage == "door":
                    self.door_pick = self.focus - 3
                    self.stage, self.focus = None, None
            elif name == "Z_SHORT" and self.stage == "card" and not relics:
                cost = self.b.reroll_cost + self.b.reroll_step * self.rerolls
                if self.gold >= cost:
                    self.gold -= cost
                    self.rerolls += 1
                    self.offer = cardlib.draw(f"{self.sc.seed}|corr|{self.loot_id}|{self.rerolls}",
                                              self.b.cards_offered, self.deck)
                    self.focus = None
                    messages.append(self._loot_message())

    def _corridor(self, dt, inp, messages, events) -> float:
        step = self._step
        bx = self._eff_balance()
        self.shield = min(self.shield + self.b.corridor_regen_per_s * dt, bx.shield_max)
        if self.stage:
            self._loot_buttons(inp, events, messages)
        if self.t_phase >= step.nominal_s:
            self.stage, self.offer, self.focus = None, (), None
            if step.doors:                      # sans choix : porte de gauche ; la salle garde l'indice du couloir
                spec, rid = step.doors[self.door_pick], self.door_ids[self.door_pick]
                self.phase, self.t_phase = ROOM, 0.0
                self.door_steps, self.door_ids = (), ()
                messages += self._start_room(spec, rid, None, inp.gear, inp.s_m)
                self._previews.clear()
            else:
                self._enter(self.idx + 1)
                self._begin(inp, messages)
        return 0.0

    # --- salles et boss -----------------------------------------------------------------------

    def _fight(self, dt, inp, messages, events) -> float:
        room, cs, b = self.room, self.combat, self.b
        bx = self._eff_balance()
        t = self.t_total
        contact = self.firewall.step(dt, inp.s_m, input_lost=inp.input_lost).contact if cs.phase == "FIGHT" else False
        raw = self._raw_grade(room, inp.s_m)

        # cartes : effets sur la pente et les dégâts
        mult = 1.0
        buttons = set(inp.buttons)
        if "cursed" in self.deck and inp.gear == b.cursed_gear:
            mult *= b.cursed_mult
            buttons.discard("Z_SHORT")
        if "overdrive" in self.deck:
            if self.overdrive_until and t >= self.overdrive_until:
                self.overdrive_until = 0.0
                self.overdrive_ready_at = t + b.overdrive_cooldown_s
                self.force_gear = b.overdrive_back_gear
            elif not self.overdrive_until and inp.gear == 12 and t >= self.overdrive_ready_at:
                self.overdrive_until = t + b.overdrive_s
        if self.overdrive_until:
            mult *= b.overdrive_mult
        if "springboard" in self.deck:
            if self.prev_raw <= b.springboard_grade < raw and inp.gear >= b.springboard_min_gear:
                self.spring_until = t + b.springboard_s
                self._spring_adr = b.springboard_adrenaline
            if t < self.spring_until:
                mult *= b.springboard_mult
        if "polarity" in self.deck and "Z_LONG" in inp.buttons and not self.inversion_used:
            self.inversion_used, self.inversion_until = True, t + b.inversion_s
        self.prev_raw = raw
        g = raw
        if "roller" in self.deck:
            if raw > b.roller_cap_grade:
                g, self.roller_hold_until = b.roller_cap_grade, t + b.roller_hold_s
            elif t < self.roller_hold_until:
                g = b.roller_cap_grade
        if t < self.inversion_until:
            g = min(max(-g, b.inversion_floor), b.room_grade_max)
        if self.overdrive_until:
            g += b.overdrive_grade_pts

        if self.phase == "RECOVERY":
            g = 0.0
        ci = CombatInputs(power_w=inp.power_w, cadence_rpm=inp.cadence_rpm, posture=self.posture.posture,
                          gear=inp.gear, ftp_w=inp.ftp_w, s_m=inp.s_m, v_mps=inp.v_mps, contact=contact,
                          buttons=frozenset(buttons), objective=self.cur_spec.objective, card_mult=mult,
                          w_bal_j=self.wbal.w_bal_j, run_gold=0.0 if self.lives > self.lives_used else self.gold)
        cs, ev = combat_step(cs, ci, room, bx, dt)
        events += ev
        # effets de cartes après le pas
        shield, adr = cs.shield, cs.adrenaline
        if "shifter" in self.deck:
            shield += b.shifter_shield * ev.count("perfect_shift")
        if "siphon" in self.deck and room.archetype == "puncheur":
            adr += b.siphon_adrenaline * ev.count("parry")
        if getattr(self, "_spring_adr", 0.0):
            adr += self._spring_adr
            self._spring_adr = 0.0
        if "heal" in self.deck and inp.gear == 1 and inp.cadence_rpm > b.heal_cadence_rpm and cs.phase == "FIGHT":
            shield += b.heal_per_s * dt
        cs = replace(cs, shield=min(shield, bx.shield_max), adrenaline=min(adr, b.adrenaline_max))
        self.combat = cs
        self.shield = cs.shield
        lost = cs.gold_lost - self.gold_lost_seen
        self.gold_lost_seen = cs.gold_lost
        self.gold = max(self.gold - lost, 0.0)
        if "defeat" in ev:
            self.defeats += 1
            if self.lives > self.lives_used and not self.boss_phase:
                self.lives_used += 1
                self._journal.append(f"rogue life_used total={self.lives_used}")
            self._journal.append(f"rogue defeat room={self.room_id}")
        if cs.phase == RECOVERY and self.phase != "RECOVERY":
            self.phase = "RECOVERY"
        if cs.phase == DONE:
            self._finish_room(cs, inp, messages, events)
        return g

    def _raw_grade(self, room: Room, s: float) -> float:
        return self.firewall.grade_at(max(s, 0.0))

    def _finish_room(self, cs, inp, messages, events) -> None:
        self.perfect_shifts += cs.perfect_shifts
        self._journal.append(f"rogue room_end id={self.room_id} outcome={cs.outcome} gold={cs.gold:.0f}")
        boss = self.boss_phase is not None
        if cs.outcome == "won":
            self.rooms_won += 0 if boss else 1
            self.gold += cs.gold * self._gold_mult()
        elif cs.outcome == "fled":
            self.rooms_fled += 0 if boss else 1
            self.gold += cs.gold * self._gold_mult()
        if boss:
            if cs.outcome == "boss_fled":
                self.boss = "fled"
            elif self.boss_phase == 3:
                self.boss = "won" if cs.outcome == "won" else "fled"
            elif self.boss == "not_reached":
                self.boss = "in_progress"
        self.room, self.combat, self.firewall = None, None, None
        if boss and (cs.outcome == "boss_fled" or self.boss_phase == 3):
            nxt = self.idx + 1
            while self.sc.steps[nxt].kind != "cooldown":
                nxt += 1
            self.boss_phase = None
            self._enter(nxt)
            return
        self.boss_phase = None
        if not boss:                                    # joueur en retard : couloirs raccourcis, salle retirée
            from .scenario import adapt_after_room
            self.sc, skipped = adapt_after_room(self.sc, self.idx, self.t_total, self.b)
            for _ in range(skipped):
                self.rooms_skipped += 1
                self.gold = max(self.gold - self.b.skip_gold_penalty, 0.0)
                events.append("room_skipped")
                self._journal.append(f"rogue room_skipped total={self.rooms_skipped}")
        self._enter(min(self.idx + 1, len(self.sc.steps) - 1))
        self._begin(inp, messages)

    # --- fin de run ---------------------------------------------------------------------------

    def _finish_run(self) -> None:
        self.phase = RESULTS
        self.result = "victory" if self.boss == "won" else "defeat"
        self._journal.append(f"rogue results result={self.result}")

    def abandon(self) -> dict:
        """Run arrêtée par `end_session` avant les résultats : bilan `abandoned`, sans perte d'or."""
        if self.phase != RESULTS:
            self.result = "abandoned"
            if self.boss == "in_progress":
                self.boss = "fled"
        return self.summary()

    def summary(self) -> dict:
        """Objet `summary.rogue` du contrat 1.4."""
        boss = "fled" if self.boss == "in_progress" else self.boss
        return {"result": self.result or "abandoned", "objective": self.sc.objective,
                "duration_min": self.sc.duration_min, "seed": self.sc.seed,
                "rooms_won": self.rooms_won, "rooms_fled": self.rooms_fled,
                "rooms_skipped": self.rooms_skipped, "rooms_total": self.rooms_total0,
                "defeats": self.defeats, "boss": boss, "gold": int(self.gold),
                "cards": list(self.relics + self.deck), "perfect_shifts": self.perfect_shifts,
                "unlocks": []}

    # --- état pour l'engine -------------------------------------------------------------------

    def _windows(self, s: float) -> list:
        if self.room is None:
            return []
        out = []
        for m in self.room.markers:
            if m.kind in WINDOW_KINDS and m.s_m + m.len_m + 3.0 >= s:
                out.append({"kind": m.kind, "s_start": round(m.s_m - 3.0 if m.len_m == 0 else m.s_m, 1),
                            "s_end": round(m.s_m + max(m.len_m, 3.0), 1)})
            if len(out) == 4:
                break
        return out

    def _state(self, inp, events) -> dict:
        cs, room = self.combat, self.room
        bx = self._eff_balance()
        hack = None
        if cs is not None and cs.hack_kind:
            hack = {"locked": cs.hack_kind == "blocked", "forced_gear": cs.forced_gear,
                    "until_s": round(cs.hack_t_s + self.b.hack_max_s, 1)}
        gap = self.firewall.state.gap_m if self.firewall is not None else 0.0
        return {
            "phase": self.phase, "room_id": self.room_id,
            "room_index": max(self.rooms_started, 1), "rooms_total": max(self.rooms_total0, 1),
            "archetype": room.archetype if room else None, "boss_phase": self.boss_phase,
            "s_room": round(inp.s_m, 1) if room else 0.0,
            "enemy_hp": round(cs.enemy_hp, 2) if cs else 0.0,
            "enemy_hp_max": round(cs.enemy_hp_max, 2) if cs else 0.0,
            "shield": round(self.shield, 1), "shield_max": bx.shield_max,
            "adrenaline": round(cs.adrenaline, 1) if cs else 0.0,
            "w_bal_j": round(self.wbal.w_bal_j, 1), "w_prime_j": self.w_prime_j,
            "posture": self.posture.posture, "firewall_gap_m": round(gap, 1),
            "gold": int(self.gold), "windows": self._windows(inp.s_m)[:4], "hack": hack,
            "overheat": bool(cs.overheat) if cs else False, "loot_focus": self.focus,
            "events": list(events)[:4],
        }

    # --- reprise ------------------------------------------------------------------------------

    def snapshot(self) -> bytes:
        """État complet de la run, pour la reprise après un plantage du core (à écrire en base 64)."""
        d = {k: v for k, v in self.__dict__.items() if k != "_journal"}
        return pickle.dumps(d, protocol=4)

    def restore(self, snap: bytes) -> None:
        self.__dict__.update(pickle.loads(snap))
