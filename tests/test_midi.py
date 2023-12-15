#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

import os
import uuid
from functools import cache

from ward import raises, skip, test

from linuxpy.midi.device import (
    INPUT_OUTPUT,
    QUEUE_DIRECT,
    SEQUENCER_PATH,
    EventType,
    MidiError,
    Sequencer,
    iter_read_clients,
    read_port_info,
    to_address,
    to_event_type,
)
from linuxpy.midi.raw import ClientNumber, PortType, snd_seq_addr, snd_seq_client_info


def assert_address(addr, client, port):
    assert addr.client == client
    assert addr.port == port


for addr in ((4, 6), snd_seq_addr(4, 6)):

    @test("to_address")
    def _(addr=addr):
        address = to_address(addr)
        assert address.client == 4
        assert address.port == 6


for noteon in ("noteon", "note_on", "note on", EventType.NOTEON, 6):

    @test("to_event_type")
    def _(noteon=noteon):
        assert to_event_type(noteon) == EventType.NOTEON


@cache
def is_sequencer_available():
    return os.access(SEQUENCER_PATH, os.O_RDWR)


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
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


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
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


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("system info")
def _():
    with Sequencer() as seq:
        system_info = seq.system_info
        assert system_info.queues > 0
        assert system_info.clients > 0
        assert system_info.ports > 0
        assert system_info.channels > 0
        assert system_info.cur_clients > 0
        assert system_info.cur_queues >= 0


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("running mode")
def _():
    with Sequencer() as seq:
        running_mode = seq.running_mode
        assert running_mode.client == ClientNumber.SYSTEM


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("client info")
def _():
    with Sequencer() as seq:
        client_info = seq.client_info
        assert client_info.client == seq.client_id


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("port info")
def _():
    with Sequencer() as seq:
        port = seq.create_port()
        port_info = read_port_info(seq, seq.client_id, int(port))
        assert_address(port_info.addr, port.client_id, port.port_id)


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("create port")
def _():
    with Sequencer() as remote, Sequencer() as local:
        ports_before = local.ports
        port = remote.create_port()
        ports_after = local.ports
        assert len(ports_after) == len(ports_before) + 1
        assert port.type == PortType.MIDI_GENERIC | PortType.APPLICATION
        assert INPUT_OUTPUT in port.capability
        assert port.address.client == remote.client_id
        assert "LocalPort" in repr(port)
        assert "linuxpy port" in str(port)


def assert_noteon_event(event, source_port, target_port):
    assert event.type == EventType.NOTEON
    assert event.client_id == event.event.source.client
    assert event.port_id == event.event.source.port
    assert event.source_client_id == source_port.client_id
    assert event.source_port_id == source_port.port_id
    assert event.dest_client_id == target_port.client_id
    assert event.dest_port_id == target_port.port_id
    assert event.source.client == source_port.client_id
    assert event.source.port == source_port.port_id
    assert event.dest.client == target_port.client_id
    assert event.dest.port == target_port.port_id

    assert event.queue == QUEUE_DIRECT
    assert not event.is_variable_length_type
    assert event.note.velocity == 44
    assert event.note.channel == 0
    assert f"{event.client_id}:{event.port_id}" in str(event)
    assert "<Event type=NOTEON>" == repr(event)


def assert_sysex_event(event, source_port, target_port):
    assert event.type == EventType.SYSEX
    assert event.client_id == event.event.source.client
    assert event.port_id == event.event.source.port
    assert event.source_client_id == source_port.client_id
    assert event.source_port_id == source_port.port_id
    assert event.dest_client_id == target_port.client_id
    assert event.dest_port_id == target_port.port_id
    assert event.source.client == source_port.client_id
    assert event.source.port == source_port.port_id
    assert event.dest.client == target_port.client_id
    assert event.dest.port == target_port.port_id

    assert event.queue == QUEUE_DIRECT
    assert event.is_variable_length_type
    assert event.data == b"123"
    assert event.raw_data == b"\xf0123\xf7"
    assert f"{event.client_id}:{event.port_id}" in str(event)
    assert "<Event type=SYSEX>" == repr(event)


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("delete port")
def _():
    with Sequencer() as seq:

        def port_uids():
            return {(p.client_id, p.port_id) for p in seq.ports}

        port = seq.create_port()
        uid = (port.client_id, port.port_id)
        assert uid in port_uids()
        port.delete()
        assert uid not in port_uids()

        port = seq.create_port()
        uid = (port.client_id, port.port_id)
        assert uid in port_uids()
        seq.delete_port(int(port))
        assert uid not in port_uids()

        port = seq.create_port()
        uid = (port.client_id, port.port_id)
        assert uid in port_uids()
        seq.delete_port(port)
        assert uid not in port_uids()

        with Sequencer() as remote:
            port = remote.create_port()
            with raises(MidiError):
                seq.delete_port(port)


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("(dis)connect_from/to")
def _():
    with Sequencer() as remote, Sequencer() as local:
        remote_port = remote.create_port()
        local_port = local.create_port()

        uid = remote_port.client_id, remote_port.port_id, local_port.client_id, local_port.port_id
        local_port.connect_from(remote_port.address)
        assert uid in local.subscriptions
        local_port.disconnect_from(remote_port.address)
        assert uid not in local.subscriptions

        uid = local_port.client_id, local_port.port_id, remote_port.client_id, remote_port.port_id
        local_port.connect_to(remote_port.address)
        assert uid in local.subscriptions
        local_port.disconnect_to(remote_port.address)
        assert uid not in local.subscriptions


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("(dis)connect_from/to and delete error on non local")
def _():
    with Sequencer() as remote, Sequencer() as local:
        remote_port = remote.create_port()

        for port in local.ports:
            if port.client_id == remote_port.client_id and port.port_id == remote_port.port_id:
                break

        with raises(MidiError) as error:
            port.connect_from((0, 1))
        assert "Can only connect local port" == error.raised.args[0]

        with raises(MidiError) as error:
            port.connect_to((0, 1))
        assert "Can only connect local port" == error.raised.args[0]

        with raises(MidiError) as error:
            port.disconnect_from((0, 1))
        assert "Can only disconnect local port" == error.raised.args[0]

        with raises(MidiError) as error:
            port.disconnect_to((0, 1))
        assert "Can only disconnect local port" == error.raised.args[0]

        with raises(MidiError) as error:
            port.delete()
        assert "Can only delete local port" == error.raised.args[0]


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("connect_from events")
def _():
    with Sequencer() as remote, Sequencer() as local:
        remote_port = remote.create_port()
        local_port = local.create_port()

        local_port.connect_from(remote_port.address)

        remote_port.send("note on", velocity=44)

        # Use a for loop with a break to make sure the Sequencer.__iter__ is closed
        # using something like next(iter(seq)) wouldn't make the tests fail but if
        # Sequencer.__iter__ needs a cleanup it would only get called when the seq
        # object gets garbage collectecd
        for event in local:
            assert_noteon_event(event, remote_port, local_port)
            break

        remote_port.send("sysex", data=b"123")

        for event in local:
            assert_sysex_event(event, remote_port, local_port)
            break


@skip(when=not is_sequencer_available(), reason="MIDI sequencer is not prepared")
@test("async connect_from events")
async def _():
    with Sequencer() as remote, Sequencer() as local:
        remote_port = remote.create_port()
        local_port = local.create_port()

        local_port.connect_from(remote_port.address)

        remote_port.send("note on", velocity=44)

        # Use a for loop with a break to make sure the Sequencer.__aiter__ is closed
        # using something like next(iter(seq)) wouldn't make the tests fail but if
        # Sequencer.__aiter__ needs a cleanup it would only get called when the seq
        # object gets garbage collectecd
        async for event in local:
            assert_noteon_event(event, remote_port, local_port)
            break
