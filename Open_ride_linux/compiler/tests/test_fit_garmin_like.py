"""Import de FIT tels que les montres Garmin et Garmin Connect les écrivent (lot X56).

Les FIT sont fabriqués octet par octet ici, sans aucun vrai fichier (règle de confidentialité) :
en-tête de 12 ou 14 octets, définitions grand-boutistes, en-têtes à temps compressé, champs
développeur (capteurs tiers), messages inconnus ou propres au fabricant, positions invalides en tête
d'activité, fichiers chaînés. Chaque variante doit donner la même trace que le fichier simple, et
le FIT d'une séance OpenRide doit se recompiler en parcours (rouler une sortie déjà faite).
"""

from __future__ import annotations

import struct

import pytest

from openride_compiler.errors import CompileError
from openride_compiler.track_formats import parse_fit, sniff_format

FIT_EPOCH = 631065600
T = 1_790_000_000 - FIT_EPOCH
INVALID_SINT32 = 0x7FFFFFFF
BASE = {"enum": (0x00, "B"), "uint8": (0x02, "B"), "uint16": (0x84, "H"), "sint32": (0x85, "i"),
        "uint32": (0x86, "I"), "uint32z": (0x8C, "I")}
CRC_TABLE = (0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
             0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400)


def crc16(data: bytes, crc: int = 0) -> int:
    """CRC du protocole FIT (quartet par quartet)."""
    for byte in data:
        for nibble in (byte & 0xF, byte >> 4):
            tmp = CRC_TABLE[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc ^= tmp ^ CRC_TABLE[nibble]
    return crc


def semicircles(deg: float) -> int:
    return int(round(deg * 2**31 / 180))


class FitBytes:
    """Encodeur FIT minimal : définitions, données, temps compressé, champs développeur."""

    def __init__(self) -> None:
        self.body = bytearray()
        self.defs: dict[int, tuple[str, list[tuple[int, str]]]] = {}

    def define(self, local: int, global_num: int, fields: list[tuple[int, str]], big: bool = False,
               dev: list[tuple[int, int, int]] | None = None) -> None:
        endian = ">" if big else "<"
        out = bytes([0x40 | local | (0x20 if dev else 0), 0, 1 if big else 0])
        out += struct.pack(endian + "H", global_num) + bytes([len(fields)])
        for num, base in fields:
            out += bytes([num, struct.calcsize(BASE[base][1]), BASE[base][0]])
        if dev:
            out += bytes([len(dev)]) + b"".join(bytes(d) for d in dev)
        self.body += out
        self.defs[local] = (endian, fields)

    def data(self, local: int, values: list[int], extra: bytes = b"", time_offset: int | None = None) -> None:
        endian, fields = self.defs[local]
        header = local if time_offset is None else 0x80 | (local << 5) | (time_offset & 0x1F)
        self.body += bytes([header]) + b"".join(
            struct.pack(endian + BASE[base][1], v) for (_, base), v in zip(fields, values)) + extra

    def build(self, header_size: int = 14) -> bytes:
        head = struct.pack("<BBHI4s", header_size, 0x20 if header_size == 14 else 0x10, 2189,
                           len(self.body), b".FIT")
        if header_size == 14:
            head += struct.pack("<H", crc16(head))
        data = head + bytes(self.body)
        return data + struct.pack("<H", crc16(data))


def track(n: int = 60) -> list[tuple[float, float, float]]:
    return [(45.2 + i * 1e-4, 5.7 + i * 1e-4, 200.0 + i * 0.5) for i in range(n)]


def garmin_fit(compressed: bool = False, big: bool = False, dev: bool = False, foreign: bool = False,
               header_size: int = 14, no_fix_first: int = 0) -> bytes:
    w = FitBytes()
    w.define(0, 0, [(0, "enum"), (1, "uint16"), (2, "uint16"), (3, "uint32z"), (4, "uint32")], big=big)
    w.data(0, [4, 1, 3121, 12345, T])   # activité, fabricant Garmin, un produit quelconque
    if foreign:
        w.define(1, 65280, [(0, "uint32"), (1, "uint16")])   # message propre au fabricant
        w.data(1, [7, 8])
        w.define(1, 233, [(2, "uint8")])                     # message absent du profil public
        w.data(1, [1])
    dev_fields = None
    if dev:   # capteur tiers : developer_data_id, field_description, puis un champ dans chaque record
        w.define(2, 207, [(3, "uint8")])
        w.data(2, [0])
        w.define(2, 206, [(0, "uint8"), (1, "uint8"), (2, "uint8")])
        w.data(2, [0, 0, BASE["uint16"][0]])
        dev_fields = [(0, 2, 0)]
    fields = [(0, "sint32"), (1, "sint32"), (78, "uint32"), (5, "uint32"), (7, "uint16")]
    w.define(3, 20, [(253, "uint32")] + fields, big=big, dev=dev_fields)
    if compressed:   # mêmes champs, horodatage porté par l'en-tête du record
        w.define(1, 20, fields, big=big, dev=dev_fields)
    for i, (lat, lon, alt) in enumerate(track()):
        values = [semicircles(lat), semicircles(lon), int((alt + 500) * 5), i * 800, 200]
        if i < no_fix_first:
            values[0] = values[1] = INVALID_SINT32
        extra = struct.pack("<H", 42) if dev else b""
        if compressed and i > 0:
            w.data(1, values, extra, time_offset=T + i)
        else:
            w.data(3, [T + i] + values, extra)
    return w.build(header_size)


def same_track(points, skip: int = 0) -> None:
    want = track()[skip:]
    assert len(points) == len(want)
    for p, (lat, lon, alt) in zip(points, want):
        assert p.lat == pytest.approx(lat, abs=1e-6) and p.lon == pytest.approx(lon, abs=1e-6)
        assert p.ele == pytest.approx(alt, abs=0.2)


@pytest.mark.parametrize("variant", [
    {}, {"compressed": True}, {"big": True}, {"dev": True}, {"foreign": True}, {"header_size": 12},
    {"compressed": True, "big": True, "dev": True, "foreign": True},
], ids=["simple", "temps_compresse", "grand_boutiste", "champs_developpeur", "messages_inconnus",
        "entete_12_octets", "tout_ensemble"])
def test_garmin_like_variants_give_the_same_track(variant):
    data = garmin_fit(**variant)
    assert sniff_format(data) == ".fit"
    same_track(parse_fit(data))


def test_points_without_fix_at_the_start_are_skipped():
    same_track(parse_fit(garmin_fit(no_fix_first=3)), skip=3)


def test_chained_fit_reads_every_segment():
    """Garmin chaîne parfois deux fichiers : les deux segments sont lus (doublons retirés ensuite)."""
    assert len(parse_fit(garmin_fit() + garmin_fit(compressed=True))) == 2 * len(track())


def test_bad_crc_is_a_readable_error():
    data = bytearray(garmin_fit())
    data[-1] ^= 0xFF
    with pytest.raises(CompileError, match="FIT illisible"):
        parse_fit(bytes(data))


def test_openride_session_fit_compiles_back_into_a_route(tmp_path):
    """Aller-retour : le FIT d'une séance OpenRide sur un monde géolocalisé redevient une trace."""
    fit_export = pytest.importorskip("openride_core.fit_export")
    records = [{"ts": 1_790_000_000.0 + i, "lat": lat, "lon": lon, "alt": alt, "distance": 8.0 * i,
                "speed": 8.0, "power": 210, "cadence": 90, "hr": 130}
               for i, (lat, lon, alt) in enumerate(track())]
    path = tmp_path / "seance.fit"
    fit_export.write_fit(records, [], path)
    same_track(parse_fit(path.read_bytes()))
