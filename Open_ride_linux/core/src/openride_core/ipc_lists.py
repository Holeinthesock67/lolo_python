"""Formatage et découpage des messages IPC routes et workouts (Contrat v1.1, Lot N2).

Construit les réponses aux commandes `list_routes` et `list_workouts`, avec limitation
à 200 éléments au plus, découpage en datagrammes de 60 000 octets au plus et profils
ERG limités à 30 triplets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_ITEMS = 200
MAX_DATAGRAM_BYTES = 60_000
MAX_PROFILE_TRIPLETS = 30


def route_entry_to_dict(entry: Any) -> dict[str, Any]:
    """Convertit un RouteEntry du catalogue vers la structure du contrat routes.schema.json."""
    return {
        "id": entry.id,
        "name": entry.name,
        "status": entry.status,
        "length_m": round(entry.length_m, 1) if entry.length_m is not None else None,
        "route_type": entry.route_type,
        "has_terrain": bool(entry.has_terrain),
        "error": entry.error,
    }


def workout_info_to_dict(w: Any) -> dict[str, Any]:
    """Convertit un WorkoutInfo vers la structure du contrat workouts.schema.json."""
    if w.error is not None:
        return {
            "id": w.id,
            "name": w.name,
            "duration_s": 0.0,
            "block_count": 0,
            "selectable": False,
            "error": w.error,
            "profile": [],
            "profile_truncated": False,
        }

    profile_triplets: list[list[float | None]] = []
    for b in w.profile[:MAX_PROFILE_TRIPLETS]:
        profile_triplets.append([
            round(b.duration_s, 1),
            round(b.start_frac, 4) if b.start_frac is not None else None,
            round(b.end_frac, 4) if b.end_frac is not None else None,
        ])

    return {
        "id": w.id,
        "name": w.name,
        "duration_s": round(w.duration_s, 1),
        "block_count": len(w.profile),
        "selectable": True,
        "error": None,
        "profile": profile_triplets,
        "profile_truncated": len(w.profile) > MAX_PROFILE_TRIPLETS,
    }


def chunk_list_message(
    msg_type: str,
    request_cmd_id: int,
    items: list[dict[str, Any]],
    truncated: bool,
    max_bytes: int = MAX_DATAGRAM_BYTES,
) -> list[dict[str, Any]]:
    """Découpe une liste d'éléments en parties (datagrammes UDP) de max_bytes au plus."""
    single_msg = {
        "type": msg_type,
        "v": 1,
        "request_cmd_id": request_cmd_id,
        "part": 1,
        "parts": 1,
        "truncated": truncated,
        "items": items,
    }
    raw = json.dumps(single_msg, separators=(",", ":")).encode("utf-8")
    if len(raw) <= max_bytes:
        return [single_msg]

    # Découpage en parties
    chunks: list[list[dict[str, Any]]] = []
    current_chunk: list[dict[str, Any]] = []

    header_template = {
        "type": msg_type,
        "v": 1,
        "request_cmd_id": request_cmd_id,
        "part": 999,
        "parts": 999,
        "truncated": truncated,
        "items": [],
    }
    header_bytes = len(json.dumps(header_template, separators=(",", ":")).encode("utf-8")) + 2
    current_bytes = header_bytes

    for item in items:
        item_bytes = len(json.dumps(item, separators=(",", ":")).encode("utf-8")) + 1
        if current_chunk and (current_bytes + item_bytes > max_bytes):
            chunks.append(current_chunk)
            current_chunk = [item]
            current_bytes = header_bytes + item_bytes
        else:
            current_chunk.append(item)
            current_bytes += item_bytes

    if current_chunk:
        chunks.append(current_chunk)

    total_parts = len(chunks) or 1
    out: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, 1):
        out.append({
            "type": msg_type,
            "v": 1,
            "request_cmd_id": request_cmd_id,
            "part": idx,
            "parts": total_parts,
            "truncated": truncated,
            "items": chunk,
        })
    return out


def build_routes_messages(
    request_cmd_id: int,
    routes_root: Path,
    gpx_dir: Path,
    max_items: int = MAX_ITEMS,
    max_bytes: int = MAX_DATAGRAM_BYTES,
) -> list[dict[str, Any]]:
    """Lit le catalogue et produit les messages `routes` (1 à parts parties)."""
    from .catalog import list_routes

    entries = list_routes(routes_root=routes_root, gpx_dir=gpx_dir)
    truncated = len(entries) > max_items
    items = [route_entry_to_dict(e) for e in entries[:max_items]]
    return chunk_list_message("routes", request_cmd_id, items, truncated, max_bytes=max_bytes)


def build_workouts_messages(
    request_cmd_id: int,
    workouts_dir: Path,
    max_items: int = MAX_ITEMS,
    max_bytes: int = MAX_DATAGRAM_BYTES,
) -> list[dict[str, Any]]:
    """Lit les entraînements et produit les messages `workouts` (1 à parts parties)."""
    from .workout import list_workouts

    workouts = list_workouts(workouts_dir)
    truncated = len(workouts) > max_items
    items = [workout_info_to_dict(w) for w in workouts[:max_items]]
    return chunk_list_message("workouts", request_cmd_id, items, truncated, max_bytes=max_bytes)
