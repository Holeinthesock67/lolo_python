"""Émission IPC de la minute (essai du 22 novembre : gels de 9 à 10 s du monde ouvert, trames state absentes
côté engine alors que le core tournait normalement) : trames envoyées, taille max, erreurs d'envoi comptées
par cause et journalisées (elles n'étaient écrites qu'en débogage)."""

import errno
import logging

from openride_core.ipc_server import IpcServer


class _Sock:
    def __init__(self, fail: OSError | None = None) -> None:
        self.fail = fail
        self.sent: list[bytes] = []

    def sendto(self, payload: bytes, addr) -> None:
        if self.fail is not None:
            raise self.fail
        self.sent.append(payload)

    def close(self) -> None:
        pass


def _server(sock: _Sock) -> IpcServer:
    srv = IpcServer()
    srv._tx_sock = sock
    return srv


def test_compte_les_trames_et_la_taille_max():
    srv = _server(_Sock())
    srv.send_raw({"type": "state", "seq": 1, "s": 1.0})
    srv.send_raw({"type": "state", "seq": 2, "s": 2.0, "pad": "x" * 100})
    srv.send_raw({"type": "error", "code": "busy"})
    assert srv.tx_state == 2 and srv.tx_other == 1
    assert srv.tx_state_max > 100
    line = srv.tx_line()
    assert line.startswith("IPC émis : state 2 (max ")
    assert line.endswith("erreurs d'envoi : aucune")
    assert srv.tx_state == 0 and srv.tx_state_max == 0, "compteurs remis à zéro après la ligne"


def test_erreur_d_envoi_comptee_par_cause_et_journalisee(caplog):
    srv = _server(_Sock(BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")))
    with caplog.at_level(logging.WARNING, logger="ipc_server"):
        for i in range(3):
            srv.send_raw({"type": "state", "seq": i})
    assert srv.tx_errors == {"EAGAIN": 3}
    assert srv.tx_state == 0, "une trame refusée n'est pas comptée comme envoyée"
    warnings = [r for r in caplog.records if "Envoi UDP refusé" in r.getMessage()]
    assert len(warnings) == 1, "un seul avertissement par période"
    assert "EAGAIN" in warnings[0].getMessage()
    assert "erreurs d'envoi : EAGAIN 3" in srv.tx_line()
    assert srv.tx_errors == {}
