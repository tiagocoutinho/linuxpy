import uuid

from ward import test

from linuxpy.midi.device import SEQUENCER_PATH, Sequencer, iter_read_clients
from linuxpy.midi.raw import snd_seq_client_info


@test("read_clients")
def _():
    with SEQUENCER_PATH.open("rb") as seq:
        clients = list(iter_read_clients(seq))
        assert clients
        assert all(isinstance(client, snd_seq_client_info) for client in clients)

    name = uuid.uuid4().hex
    with Sequencer(name=name) as seq:
        clients = list(iter_read_clients(seq))
        assert name in {client.name.decode() for client in clients}


@test("test open/close sequencer")
def _():
    dev = Sequencer()
    assert dev.filename == SEQUENCER_PATH
    assert dev.closed
    # closing closed has no effect
    dev.close()
    assert dev.closed

    # open does open it
    dev.open()
    assert not dev.closed
    assert dev.client_id >= 0
    assert dev.name == "linuxpy client"

    # opening already opened has no effect
    dev.open()
    assert not dev.closed

    dev.close()
    assert dev.closed

    # Context manager works
    with dev:
        assert not dev.closed
    assert dev.closed

    # Reentrant context manager works
    with dev:
        assert not dev.closed
        with dev:
            assert not dev.closed
        assert not dev.closed
    assert dev.closed
