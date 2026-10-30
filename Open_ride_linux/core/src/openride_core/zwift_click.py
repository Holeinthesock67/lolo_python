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


class InputEvent(str, enum.Enum):
    PLUS_SHORT = "PLUS_SHORT"
    MINUS_SHORT = "MINUS_SHORT"
    PLUS_LONG = "PLUS_LONG"
    MINUS_LONG = "MINUS_LONG"
    # Autres boutons du Click V2 (contrat IPC révision 1.3) : A et Z, court et long ; Y, flèches :
    # un seul événement, quelle que soit la durée de l'appui.
    A_SHORT = "A_SHORT"
    A_LONG = "A_LONG"
    Z_SHORT = "Z_SHORT"
    Z_LONG = "Z_LONG"
    Y_SHORT = "Y_SHORT"
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


# Boutons suivis par PressClassifier ; B est lu comme « − ». Y et flèches : un seul événement.
BUTTONS = ("PLUS", "MINUS", "A", "Z", "Y", "LEFT", "RIGHT", "UP", "DOWN")
SINGLE_EVENT_BUTTONS = ("Y", "LEFT", "RIGHT", "UP", "DOWN")


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


MESSAGE_TYPES = ("boutons", "batterie", "maintien", "etat", "inconnu")


def classify_message(data: bytes) -> str:
    """Classe un message de notification du Click : 'boutons', 'batterie', 'maintien', 'etat' (état du
    boîtier gauche, voir `parse_status`) ou 'inconnu'."""
    if not data:
        return "inconnu"
    if data.startswith(STATUS_HEADER):
        return "etat"
    msg_type = data[0]
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
    Y et les flèches n'ont qu'un événement (`_SHORT`), quelle que soit la durée.
    """

    def __init__(self, short_max_s: float = SHORT_MAX_S, long_min_s: float = LONG_MIN_S) -> None:
        self.short_max_s = short_max_s
        self.long_min_s = long_min_s
        self._down_since: dict[str, float | None] = {name: None for name in BUTTONS}

    def update(self, button: str, pressed: bool, t: float) -> InputEvent | None:
        since = self._down_since[button]
        if pressed:
            if since is None:
                self._down_since[button] = t
            return None
        if since is None:
            return None
        self._down_since[button] = None
        if button in SINGLE_EVENT_BUTTONS:
            return InputEvent[f"{button}_SHORT"]
        duration = t - since
        if duration < self.short_max_s:
            return InputEvent[f"{button}_SHORT"]
        if duration >= self.long_min_s:
            return InputEvent[f"{button}_LONG"]
        return InputEvent[f"{button}_UNCLEAR"] if button in ("PLUS", "MINUS") else None

    def feed(self, buttons: ClickButtons, t: float) -> list[InputEvent]:
        events = []
        for name in BUTTONS:
            ev = self.update(name, getattr(buttons, f"{name.lower()}_pressed"), t)
            if ev is not None:
                events.append(ev)
        return events
