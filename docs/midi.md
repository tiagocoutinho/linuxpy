# MIDI Sequencer

Without further ado:

```bash
$ python

>>> from linuxpy.midi.device import Sequencer, event_stream

>>> seq = Sequencer()
>>> with seq:
        port = seq.create_port()
        port.connect_from(14, 0)
        for event in event_stream(seq):
            print(event)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Clock                queue=0, pad=b''
 14:0   System exclusive     F0 61 62 63 F7
 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0
```

## asyncio

asyncio is a first class citizen to linuxpy.midi:

```bash
$ python -m asyncio

>>> from linuxpy.midi.device import Sequencer, async_event_stream

>>> seq = Sequencer()
>>> with seq:
        port = seq.create_port()
        port.connect_from(14, 0)
        async for event in async_event_stream(seq):
            print(event)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Clock                queue=0, pad=b''
 14:0   System exclusive     F0 61 62 63 F7
 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0
```

## CLI

A basic CLI is provided that allows listing MIDI clients & ports
and dumping MIDI sequencer events:

```bash
$ python -m linuxpy.midi.cli ls
   0:0  System                    Timer                     SUBS_READ|WRITE|READ
   0:1  System                    Announce                  SUBS_READ|READ
  14:0  Midi Through              Midi Through Port-0       SUBS_WRITE|SUBS_READ|WRITE|READ
 128:0  aseqdump                  aseqdump                  SUBS_WRITE|WRITE
```

```bash
$ python -m linuxpy.midi.cli 0:1 14:0
  0:1   Port subscribed      sender=(client=0, port=1), dest=(client=128, port=0)
  0:1   Port start           client=128, port=1
  0:1   Port subscribed      sender=(client=14, port=0), dest=(client=128, port=1)
  0:1   Client start         client=130, port=0
  0:1   Port start           client=130, port=0
  0:1   Port subscribed      sender=(client=130, port=0), dest=(client=14, port=0)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
  0:1   Port unsubscribed    sender=(client=130, port=0), dest=(client=14, port=0)
  0:1   Port exit            client=130, port=0
  0:1   Client exit          client=130, port=0
  0:1   Port exit            client=129, port=0
  0:1   Client exit          client=129, port=0
  0:1   Client start         client=129, port=0
  0:1   Port start           client=129, port=0
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0
 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0
```
