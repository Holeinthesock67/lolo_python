"""Protocole du Zwift Click et classification des appuis (SRS §4.2).

Protocole rétro-ingénié (réf. jat255/zwift_click_handling, ajchellew/zwiftplay), à valider au
sprint 0 :
- service propriétaire 00000001-19ca-4651-86e5-fa29dcdd09d1 ;
- handshake sans chiffrement : écrire b"RideOn" sur SYNC_RX, la réponse arrive sur SYNC_TX ;
- notifications des boutons sur ASYNC : 1 octet de type puis un message protobuf.
  Type 0x37 (Click ancien) : champ 1 = bouton +, champ 2 = bouton −, valeur 0 = appuyé, 1 = relâché.
  Type 0x23 (Click récent, mesuré) : champ 1 = tableau de bits, 0 = appuyé ; bit 12 = +, bit 8 = −.

Click V2 (paire, relevé bouton par bouton sur le matériel le 24 octobre, voir KEYPAD_BITS) :
boîtier droit + (bit 12), A (4), B (5), Y (6), Z (7) ; boîtier gauche − (bit 8), flèches gauche
(0), haut (1), droite (2), bas (3). Chaque boîtier n'envoie que ses propres boutons. Sans « déblocage » par l'appli Zwift dans les 24 h, le
boîtier gauche cesse d'envoyer ses boutons environ une minute après la connexion (la liaison
reste active ; constat aussi publié par BikeControl et zwiftboard) : le bouton B du boîtier
droit fait donc aussi « − ».
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

CLICK_NAME = "Zwift Click"
ZWIFT_SERVICE = "00000001-19ca-4651-86e5-fa29dcdd09d1"
ZWIFT_ASYNC = "00000002-19ca-4651-86e5-fa29dcdd09d1"
ZWIFT_SYNC_RX = "00000003-19ca-4651-86e5-fa29dcdd09d1"
ZWIFT_SYNC_TX = "00000004-19ca-4651-86e5-fa29dcdd09d1"
ZWIFT_UNKNOWN_6 = "00000006-19ca-4651-86e5-fa29dcdd09d1"

RIDE_ON = b"RideOn"
# Redémarrage à distance d'un boîtier (rétro-ingénierie : zwiftboard, OpenRadlr ; à valider sur le matériel) :
# un octet seul sur SYNC_RX, le boîtier se réannonce en quelques secondes.
RESET_POD = b"\x18"
# Message d'état du boîtier gauche (OpenRadlr) : en-tête, longueur, puis protobuf dont le champ 2 est le
# « mode ». 0 : boutons en clair ; 1 : verrouillé par Zwift (environ une minute après la connexion).
STATUS_HEADER = bytes([0xFF, 0x05, 0x00, 0xEA, 0x05])
STATUS_MODE_FIELD = 2
STATUS_MODE_LOCKED = 1
# Lot K9, essai D (zwiftboard, « verified on Click V2 hardware », docs/RECHERCHE_CLICK_GAUCHE.md §3.3) :
# activation complète en trois écritures sur SYNC_RX à 100 ms d'intervalle, puis `ff 04 00` en réponse à
# l'écho `RideOn` (SYNC_TX) et à chaque défi `0xFF` (ASYNC) pour garder un boîtier déjà déverrouillé.
ACTIVATION = (RIDE_ON + bytes([0x02, 0x03]), bytes([0x00, 0x08, 0x00]), bytes([0x00, 0x08, 0x10]))
ACTIVATION_GAP_S = 0.1
KEEP_UNLOCKED = bytes([0xFF, 0x04, 0x00])
CHALLENGE_BYTE = 0xFF
# `[drivers] click_reset_locked` : que faire du verrou du boîtier gauche (SRS §4.2).
#   reset : redémarrage `0x18` dès le verrou (défaut depuis le 30 octobre, essai C) ;
#   keep  : activation complète et `ff 04 00` pour garder le déverrouillage, `0x18` seulement si le
#           verrou revient quand même (essai D, lot K9) ;
#   off   : rien, le boîtier gauche reste muet (B du droit fait « − »).
LOCK_POLICIES = ("reset", "keep", "off")

MSG_CONTROLLER_NOTIFICATION = 0x07  # Zwift Play
MSG_EMPTY = 0x15
MSG_BATTERY_LEVEL = 0x19
MSG_CLICK_NOTIFICATION = 0x37
# Zwift Click récent (mesuré au sprint 0) : état des boutons envoyé en continu (~10 Hz).
MSG_KEYPAD_STATUS = 0x23
KEYPAD_ALL_RELEASED = 0xFFFFFFFF
KEYPAD_PLUS_BIT = 12   # bit à 0 = appuyé ; à confirmer sur le matériel (sprint 0)
KEYPAD_MINUS_BIT = 8
KEYPAD_B_BIT = 5      # bouton B du boîtier droit : « − » qui marche sans déblocage Zwift
KEYPAD_Y_BIT = 6      # bouton Y du boîtier droit : interrompre et revenir
# Tous les boutons du Click V2 (bit du tableau 0x23, à 0 quand le bouton est appuyé), tous lus. Leur
# rôle dans chaque mode : spécification générale §7.1 (seule référence).
KEYPAD_BITS = {
    "LEFT": 0, "UP": 1, "RIGHT": 2, "DOWN": 3,   # flèches, boîtier gauche
    "A": 4, "B": 5, "Y": 6, "Z": 7,              # boîtier droit
    "MINUS": 8,                                  # boîtier gauche
    "PLUS": 12,                                  # boîtier droit
}

SHORT_MAX_S = 0.500
LONG_MIN_S = 0.900   # abaissé de 1,2 s après essai réel (appuis longs naturels : 0,7 à 1,1 s)
REPEAT_GAP_S = 0.35  # écart de regroupement de référence (R14) ; défaut de la séance : 0, voir SRS §4.2


class InputEvent(str, enum.Enum):
    PLUS_SHORT = "PLUS_SHORT"
    MINUS_SHORT = "MINUS_SHORT"
    PLUS_LONG = "PLUS_LONG"
    MINUS_LONG = "MINUS_LONG"
    # Autres boutons du Click V2 (contrat IPC révision 1.3) : A et Z, court et long ; flèches : un seul
    # événement, quelle que soit la durée de l'appui. Y : court ou long (Y_LONG, révision 1.11), sans zone
    # floue : tout appui de moins de 0,9 s reste Y_SHORT, pour qu'une pause ne se perde jamais.
    A_SHORT = "A_SHORT"
    A_LONG = "A_LONG"
    Z_SHORT = "Z_SHORT"
    Z_LONG = "Z_LONG"
    Y_SHORT = "Y_SHORT"
    Y_LONG = "Y_LONG"   # demi-tour en roulant (spécification générale §7.1, révision 1.11)
    LEFT_SHORT = "LEFT_SHORT"
    RIGHT_SHORT = "RIGHT_SHORT"
    UP_SHORT = "UP_SHORT"
    DOWN_SHORT = "DOWN_SHORT"
    # Appui ni court ni long (zone morte) : sans effet, relayé à l'engine pour l'expliquer au joueur
    # (contrat IPC, ajout compatible du 26 octobre).
    PLUS_UNCLEAR = "PLUS_UNCLEAR"
    MINUS_UNCLEAR = "MINUS_UNCLEAR"


def decode_protobuf_varints(payload: bytes) -> dict[int, int]:
    """Décode un message protobuf ne contenant que des varints (type de fil 0).

    Les champs d'un autre type sont sautés quand c'est possible ; un message tronqué
    renvoie ce qui a pu être lu.
    """
    out: dict[int, int] = {}
    i = 0

    def varint() -> int:
        nonlocal i
        shift = result = 0
        while i < len(payload):
            b = payload[i]
            i += 1
            result |= (b & 0x7F) << shift
            if not b & 0x80:
                return result
            shift += 7
        raise ValueError("varint tronqué")

    try:
        while i < len(payload):
            key = varint()
            field_no, wire = key >> 3, key & 0x07
            if wire == 0:
                out[field_no] = varint()
            elif wire == 2:
                n = varint()   # « i += varint() » lirait i avant que varint() ne l'avance
                i += n
            elif wire == 1:
                i += 8
            elif wire == 5:
                i += 4
            else:
                break
    except ValueError:
        pass
    return out


# Boutons suivis par PressClassifier ; B est lu comme « − ». Flèches : un seul événement. Y : court ou long,
# sans zone floue (moins de 0,9 s : court).
BUTTONS = ("PLUS", "MINUS", "A", "Z", "Y", "LEFT", "RIGHT", "UP", "DOWN")
SINGLE_EVENT_BUTTONS = ("LEFT", "RIGHT", "UP", "DOWN")
NO_DEAD_ZONE_BUTTONS = ("Y",)


@dataclass
class ClickButtons:
    plus_pressed: bool
    minus_pressed: bool
    y_pressed: bool = False
    a_pressed: bool = False
    z_pressed: bool = False
    left_pressed: bool = False
    right_pressed: bool = False
    up_pressed: bool = False
    down_pressed: bool = False


MESSAGE_TYPES = ("boutons", "batterie", "maintien", "etat", "defi", "inconnu")


def classify_message(data: bytes) -> str:
    """Classe un message de notification du Click : 'boutons', 'batterie', 'maintien', 'etat' (état du
    boîtier gauche, voir `parse_status`), 'defi' (autre message commençant par `0xFF`, auquel le choix
    `keep` répond `ff 04 00`) ou 'inconnu'."""
    if not data:
        return "inconnu"
    if data.startswith(STATUS_HEADER):
        return "etat"
    msg_type = data[0]
    if msg_type == CHALLENGE_BYTE:
        return "defi"
    if msg_type in (MSG_KEYPAD_STATUS, MSG_CLICK_NOTIFICATION, MSG_CONTROLLER_NOTIFICATION):
        return "boutons"
    if msg_type == MSG_BATTERY_LEVEL:
        return "batterie"
    if msg_type == MSG_EMPTY:
        return "maintien"
    return "inconnu"


def parse_status(data: bytes) -> int | None:
    """Mode du message d'état (0 : boutons en clair, 1 : verrouillé), ou None si ce n'en est pas un."""
    if not data.startswith(STATUS_HEADER) or len(data) < len(STATUS_HEADER) + 1:
        return None
    return decode_protobuf_varints(bytes(data[len(STATUS_HEADER) + 1:])).get(STATUS_MODE_FIELD, 0)


def parse_async(data: bytes) -> tuple[int, dict[int, int]]:
    """Renvoie (type de message, champs protobuf décodés)."""
    if not data:
        return -1, {}
    return data[0], decode_protobuf_varints(bytes(data[1:]))


def parse_click_buttons(data: bytes) -> ClickButtons | None:
    msg_type, fields = parse_async(data)
    if msg_type == MSG_KEYPAD_STATUS:
        # Tableau de bits : un bit à 0 signifie « appuyé » ; champ absent = rien d'appuyé.
        mask = fields.get(1, KEYPAD_ALL_RELEASED) & 0xFFFFFFFF
        return ClickButtons(plus_pressed=not (mask >> KEYPAD_PLUS_BIT) & 1,
                            minus_pressed=not (mask >> KEYPAD_MINUS_BIT) & 1
                            or not (mask >> KEYPAD_B_BIT) & 1,
                            **{f"{name.lower()}_pressed": not (mask >> KEYPAD_BITS[name]) & 1
                               for name in ("Y", "A", "Z", "LEFT", "RIGHT", "UP", "DOWN")})
    if msg_type != MSG_CLICK_NOTIFICATION:
        return None
    # Sémantique proto3 : un champ absent vaut 0, c'est-à-dire « appuyé ».
    return ClickButtons(plus_pressed=fields.get(1, 0) == 0, minus_pressed=fields.get(2, 0) == 0)


class PressClassifier:
    """Transforme les états appuyé/relâché horodatés en événements normalisés.

    L'événement est émis au relâchement : moins de 500 ms -> court, 900 ms ou plus -> long,
    entre les deux -> PLUS_UNCLEAR ou MINUS_UNCLEAR pour + et −, rien pour A et Z (SRS §4.2).
    Les flèches n'ont qu'un événement (`_SHORT`), quelle que soit la durée. Y n'a pas de zone floue : long à
    0,9 s ou plus (Y_LONG), court en dessous, pour que la pause ne se perde jamais.

    Rafale (constat R14 du 8 novembre) : bouton maintenu, le Click V2 envoie une suite d'appuis
    et de relâchements toutes les 0,2 à 0,3 s au lieu d'un seul appui. Avec `repeat_gap_s` > 0,
    un nouvel appui du même bouton moins de `repeat_gap_s` après son relâchement continue l'appui
    en cours : l'événement attend donc `repeat_gap_s` après le relâchement (`poll`). Une rafale de
    `LONG_MIN_S` ou plus, du premier appui au dernier relâchement, donne un seul `_LONG` ; plus
    courte, elle rend un `_SHORT` par appui, pour ne pas perdre de vrais appuis courts répétés.
    Seuls +, −, A, Z et Y sont concernés (les flèches n'ont pas d'appui long). `repeat_gap_s = 0` :
    comportement d'avant, événement dès le relâchement.
    """

    LONG_BUTTONS = tuple(b for b in BUTTONS if b not in SINGLE_EVENT_BUTTONS)

    def __init__(self, short_max_s: float = SHORT_MAX_S, long_min_s: float = LONG_MIN_S,
                 repeat_gap_s: float = 0.0) -> None:
        self.short_max_s = short_max_s
        self.long_min_s = long_min_s
        self.repeat_gap_s = repeat_gap_s
        self._down_since: dict[str, float | None] = {name: None for name in BUTTONS}
        # Rafale en cours, par bouton : (début du premier appui, heures de chaque relâchement).
        self._run: dict[str, tuple[float, list[float]] | None] = {name: None for name in BUTTONS}

    def _classify(self, button: str, duration: float) -> InputEvent | None:
        if button in NO_DEAD_ZONE_BUTTONS:
            return InputEvent[f"{button}_LONG" if duration >= self.long_min_s else f"{button}_SHORT"]
        if duration < self.short_max_s:
            return InputEvent[f"{button}_SHORT"]
        if duration >= self.long_min_s:
            return InputEvent[f"{button}_LONG"]
        return InputEvent[f"{button}_UNCLEAR"] if button in ("PLUS", "MINUS") else None

    def _close_run(self, button: str) -> list[tuple[InputEvent, float]]:
        run = self._run[button]
        self._run[button] = None
        if run is None:
            return []
        start, releases = run
        released = releases[-1]
        duration = released - start
        if len(releases) > 1:
            if duration >= self.long_min_s:
                return [(InputEvent[f"{button}_LONG"], released)]
            # Chaque tape garde l'heure de son relâchement : la paire ne les prend pas pour un relais.
            return [(InputEvent[f"{button}_SHORT"], r) for r in releases]
        ev = self._classify(button, duration)
        return [] if ev is None else [(ev, released)]

    def update_timed(self, button: str, pressed: bool, t: float) -> list[tuple[InputEvent, float]]:
        """Comme `update`, avec l'heure du relâchement qui a fini chaque événement (pour la paire)."""
        out: list[tuple[InputEvent, float]] = []
        run = self._run[button]
        since = self._down_since[button]
        if run is not None and since is None and t - run[1][-1] > self.repeat_gap_s:
            out = self._close_run(button)   # relâché depuis plus que l'écart : la rafale est finie
            run = None
        if pressed:
            if since is None:
                self._down_since[button] = t if run is None else run[0]
            return out
        if since is None:
            return out
        self._down_since[button] = None
        if button in SINGLE_EVENT_BUTTONS:
            return out + [(InputEvent[f"{button}_SHORT"], t)]
        self._run[button] = (since, [t]) if run is None else (run[0], run[1] + [t])
        if self.repeat_gap_s <= 0:
            out += self._close_run(button)
        return out

    def update(self, button: str, pressed: bool, t: float) -> InputEvent | None:
        evs = self.update_timed(button, pressed, t)
        return evs[-1][0] if evs else None

    def poll_timed(self, t: float) -> list[tuple[InputEvent, float]]:
        """Événements des rafales finies : plus d'appui depuis `repeat_gap_s` après le relâchement."""
        out: list[tuple[InputEvent, float]] = []
        for name in self.LONG_BUTTONS:
            run = self._run[name]
            if run is not None and self._down_since[name] is None and t - run[1][-1] > self.repeat_gap_s:
                out += self._close_run(name)
        return out

    def poll(self, t: float) -> list[InputEvent]:
        return [ev for ev, _ in self.poll_timed(t)]

    def feed_timed(self, buttons: ClickButtons, t: float) -> list[tuple[InputEvent, float]]:
        events: list[tuple[InputEvent, float]] = []
        for name in BUTTONS:
            events += self.update_timed(name, getattr(buttons, f"{name.lower()}_pressed"), t)
        return events

    def feed(self, buttons: ClickButtons, t: float) -> list[InputEvent]:
        return [ev for ev, _ in self.feed_timed(buttons, t)]
