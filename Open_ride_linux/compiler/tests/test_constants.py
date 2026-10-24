"""Les constantes recopiées d'openride-core restent identiques aux originales."""

from conftest import require_core
from openride_compiler import constants as C


def test_constants_match_core():
    config, demo_world, route = (require_core(f"openride_core.{m}") for m in ("config", "demo_world", "route"))

    assert C.FORMAT_NAME == route.FORMAT_NAME
    assert C.ROUTE_FIELDS == route.ROUTE_FIELDS
    assert C.SUPPORTED_MAJOR == route.SUPPORTED_MAJOR
    assert C.DS_M == demo_world.DS_M
    assert C.ROUTES_DIR == config.ROUTES_DIR


def test_core_present_in_ci():
    """Lot M9 (constat S2) : en CI, les tests qui lisent le core ne peuvent pas être sautés."""
    import importlib.util
    import os

    if os.environ.get("CI"):
        assert importlib.util.find_spec("openride_core") is not None, \
            "CI : openride-core doit être installé avec le compilateur (pip install -e core)"
