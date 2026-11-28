"""Lecture d'un seul fichier dans une archive `.zip` distante, par requêtes HTTP partielles (`Range`).

FABDEM (lot RL1) n'est livré qu'en archives de 10° × 10° de plusieurs centaines de mégaoctets ; une séance n'a
besoin que d'une ou deux tuiles d'un degré. On lit donc la fin de l'archive (répertoire central, ZIP64 compris),
puis seulement l'en-tête local et les données compressées du fichier voulu.

- Serveur sans `Range` (réponse 200 entière) : `RangeUnsupported`, sans rien télécharger de plus que le début de la
  réponse ; l'appelant se rabat sur une autre source.
- 404 : `NotFoundError` (archive absente : la mer, ou hors de la couverture).
- Contenu vérifié : signature de l'en-tête local, taille et CRC32 du fichier décompressé.
"""

from __future__ import annotations

import http.client
import os
import struct
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

from .cache import NotFoundError
from .errors import CompileError

TAIL_BYTES = 1 << 16          # fin d'archive lue d'un coup : fin du répertoire central et commentaire au plus
CHUNK = 1 << 20
EOCD_SIG = b"PK\x05\x06"
ZIP64_LOCATOR_SIG = b"PK\x06\x07"
ZIP64_EOCD_SIG = b"PK\x06\x06"
CENTRAL_SIG = b"PK\x01\x02"
LOCAL_SIG = b"PK\x03\x04"


class RangeUnsupported(CompileError):
    """Le serveur ignore les requêtes partielles."""


@dataclass(frozen=True)
class ZipMember:
    name: str
    method: int               # 0 : stocké, 8 : deflate
    crc32: int
    comp_size: int
    size: int
    local_offset: int


def _range(url: str, start: int, end: int | None, timeout_s: float) -> tuple[bytes, int | None]:
    """Octets [start, end] (end inclus ; start < 0 : les -start derniers). Renvoie (octets, taille totale)."""
    spec = f"bytes={start}-" if end is None and start >= 0 else (f"bytes={start}" if start < 0 else
                                                                  f"bytes={start}-{end}")
    req = urllib.request.Request(url, headers={"Range": spec})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status != 206:
                raise RangeUnsupported(f"le serveur ignore les requêtes partielles ({resp.status}) : {url}")
            total = None
            cr = resp.headers.get("Content-Range", "")
            if "/" in cr and cr.rsplit("/", 1)[1].strip().isdigit():
                total = int(cr.rsplit("/", 1)[1])
            data = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 416) and start < 0:
            raise NotFoundError(f"archive introuvable sur le serveur ({exc.code}) : {url}") from exc
        if exc.code == 404:
            raise NotFoundError(f"archive introuvable sur le serveur (404) : {url}") from exc
        raise
    want = (-start if start < 0 else (end - start + 1 if end is not None else None))
    if want is not None and len(data) != want and not (start < 0 and total is not None and len(data) == total):
        raise http.client.IncompleteRead(data, max((want or 0) - len(data), 0))
    return data, total


def list_members(url: str, timeout_s: float = 60.0) -> dict[str, ZipMember]:
    """Répertoire central de l'archive distante : {nom de base : membre}."""
    tail, total = _range(url, -TAIL_BYTES, None, timeout_s)
    if total is None:
        raise CompileError(f"taille de l'archive inconnue (Content-Range absent) : {url}")
    base = total - len(tail)
    at = tail.rfind(EOCD_SIG)
    if at < 0 or len(tail) - at < 22:
        raise CompileError(f"fin d'archive zip introuvable : {url}")
    (_, _, _, _, count, cd_size, cd_off, _) = struct.unpack("<4sHHHHIIH", tail[at:at + 22])
    if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF or count == 0xFFFF:
        loc = at - 20
        if loc < 0 or tail[loc:loc + 4] != ZIP64_LOCATOR_SIG:
            raise CompileError(f"archive ZIP64 sans localisateur : {url}")
        (_, _, z64_off, _) = struct.unpack("<4sIQI", tail[loc:loc + 20])
        rel = z64_off - base
        rec = tail[rel:rel + 56] if rel >= 0 else _range(url, z64_off, z64_off + 55, timeout_s)[0]
        if rec[:4] != ZIP64_EOCD_SIG:
            raise CompileError(f"fin d'archive ZIP64 illisible : {url}")
        (_, _, _, _, _, _, _, count, cd_size, cd_off) = struct.unpack("<4sQHHIIQQQQ", rec[:56])
    rel = cd_off - base
    cd = (tail[rel:rel + cd_size] if rel >= 0 and rel + cd_size <= len(tail)
          else _range(url, cd_off, cd_off + cd_size - 1, timeout_s)[0])
    out: dict[str, ZipMember] = {}
    p = 0
    while p + 46 <= len(cd) and cd[p:p + 4] == CENTRAL_SIG:
        (_, _, _, _, method, _, _, crc, csize, usize, nlen, xlen, clen, _, _, _, loff) = \
            struct.unpack("<4sHHHHHHIIIHHHHHII", cd[p:p + 46])
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
        if 0xFFFFFFFF in (csize, usize, loff):
            vals = _zip64_extra(extra)
            if usize == 0xFFFFFFFF:
                usize = vals.pop(0)
            if csize == 0xFFFFFFFF:
                csize = vals.pop(0)
            if loff == 0xFFFFFFFF:
                loff = vals.pop(0)
        out[name.rsplit("/", 1)[-1]] = ZipMember(name, method, crc, csize, usize, loff)
        p += 46 + nlen + xlen + clen
    if len(out) != count:
        raise CompileError(f"répertoire de l'archive incomplet ({len(out)} sur {count}) : {url}")
    return out


def _zip64_extra(extra: bytes) -> list[int]:
    p = 0
    while p + 4 <= len(extra):
        tag, size = struct.unpack("<HH", extra[p:p + 4])
        if tag == 0x0001:
            body = extra[p + 4:p + 4 + size]
            return list(struct.unpack(f"<{len(body) // 8}Q", body[:len(body) // 8 * 8]))
        p += 4 + size
    raise CompileError("champ ZIP64 attendu mais absent")


def fetch_member(url: str, member: ZipMember, dest: Path, timeout_s: float = 60.0) -> int:
    """Écrit le fichier `member` de l'archive dans `dest` (écriture sûre). Renvoie les octets lus sur le réseau."""
    head, _ = _range(url, member.local_offset, member.local_offset + 29, timeout_s)
    if head[:4] != LOCAL_SIG:
        raise CompileError(f"en-tête local de {member.name} illisible : {url}")
    nlen, xlen = struct.unpack("<HH", head[26:30])
    start = member.local_offset + 30 + nlen + xlen
    if member.method not in (0, 8):
        raise CompileError(f"{member.name} : compression {member.method} non lue (0 ou 8 attendu)")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
    crc = 0
    size = 0
    try:
        req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{start + member.comp_size - 1}"})
        dec = zlib.decompressobj(-15) if member.method == 8 else None
        got = 0
        with urllib.request.urlopen(req, timeout=timeout_s) as resp, open(tmp, "wb") as out:
            if resp.status != 206:
                raise RangeUnsupported(f"le serveur ignore les requêtes partielles ({resp.status}) : {url}")
            while True:
                block = resp.read(CHUNK)
                if not block:
                    break
                got += len(block)
                data = dec.decompress(block) if dec is not None else block
                crc = zlib.crc32(data, crc)
                size += len(data)
                out.write(data)
            if dec is not None:
                data = dec.flush()
                crc = zlib.crc32(data, crc)
                size += len(data)
                out.write(data)
        if got != member.comp_size:
            raise http.client.IncompleteRead(b"", max(member.comp_size - got, 0))
        if size != member.size or (crc & 0xFFFFFFFF) != member.crc32:
            raise CompileError(f"{member.name} : contenu faux après décompression (taille ou CRC32)")
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return got
