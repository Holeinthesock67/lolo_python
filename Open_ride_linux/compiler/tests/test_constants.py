"""Les constantes recopiées d'openride-core restent identiques aux originales."""

from openride_compiler import constants as C


def test_constants_match_core():
    from openride_core import config, demo_world, route

    assert C.FORMAT_NAME == route.FORMAT_NAME
    assert C.ROUTE_FIELDS == route.ROUTE_FIELDS
    assert C.SUPPORTED_MAJOR == route.SUPPORTED_MAJOR
    assert C.DS_M == demo_world.DS_M
    assert C.ROUTES_DIR == config.ROUTES_DIR
