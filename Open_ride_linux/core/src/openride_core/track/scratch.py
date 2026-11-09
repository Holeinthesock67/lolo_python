"""Scratch (lot VD6) : 10 à 60 tours, le premier à l'arrivée gagne ; un tour pris classe devant."""

from __future__ import annotations

from .mass import MassRace


class Scratch(MassRace):
    event_id = "scratch"
