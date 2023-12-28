# 🎹  MIDI Sequencer

Without further ado:

<div class="termy" data-ty-macos style="font-size: 12px;">
	<span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.midi.device import Sequencer</span>
  <span data-ty="input" data-ty-prompt=">>>">with Sequencer() as seq:</span>
  <span data-ty="input" data-ty-prompt="...">    port = seq.create_port()</span>
  <span data-ty="input" data-ty-prompt="...">    port.connect_from(14, 0)</span>
  <span data-ty="input" data-ty-prompt="...">    for event in seq:</span>
  <span data-ty="input" data-ty-prompt="...">        print(event)</span>
  <span data-ty data-ty-delay="500"> 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0</span>
  <span data-ty data-ty-delay="800"> 14:0   Clock                queue=0, pad=b''</span>
  <span data-ty data-ty-delay="100"> 14:0   System exclusive     F0 61 62 63 F7</span>
  <span data-ty data-ty-delay="800"> 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0</span>
</div>

## System information

```python
$ python
>>> from linuxpy.midi.device import Sequencer
>>> seq = Sequencer("a midi client")
>>> seq.open()

>>> seq.version
1.0.2

>>> seq.client_info
snd_seq_client_info(client=128, type=1, name=b'a midi client', filter=0, multicast_filter=b'', event_filter=b'', num_ports=0, event_lost=0, card=-1, pid=1288570)

>>> seq.running_mode
snd_seq_running_info(client=0, big_endian=0, cpu_mode=0, pad=0)

>>> seq.system_info
snd_seq_system_info(queues=32, clients=192, ports=254, channels=256, cur_clients=3, cur_queues=0)
```

## asyncio

asyncio is a first class citizen to linuxpy.midi:

```python
$ python -m asyncio

>>> from linuxpy.midi.device import Sequencer
>>> with Sequencer() as seq:
...     port = seq.create_port()
...     port.connect_from(14, 0)
...     async for event in seq:
...         print(event)
 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0
 14:0   Clock                queue=0, pad=b''
 14:0   System exclusive     F0 61 62 63 F7
 14:0   Note off             channel=0, note=55, velocity=3, off_velocity=0, duration=0
```

## CLI

A basic CLI is provided that allows listing MIDI clients & ports
and dumping MIDI sequencer events:

List all ports:

<div class="termy" data-ty-macos style="font-size: 12px;">
  <span data-ty="input" data-ty-prompt="$">python -m linuxpy.midi.cli ls</span>
  <span data-ty data-ty-delay="0">Port   Client                   Port                     Type                           Capabilities</span>
  <span data-ty data-ty-delay="0"> 0:0   System                   Timer                    0                              SR, W, R</span>
  <span data-ty data-ty-delay="0"> 0:1   System                   Announce                 0                              SR, R</span>
  <span data-ty data-ty-delay="0">14:0   Midi Through             Midi Through Port-0      PORT, SOFTWARE, MIDI_GENERIC   SW, SR, W, R</span>
</div>


Listen to events on selected port(s):

<div class="termy" data-ty-macos style="font-size: 12px;">
  <span data-ty="input" data-ty-prompt="$">python -m linuxpy.midi.cli listen 0:1 14:0</span>
  <span data-ty data-ty-delay="0">  0:1   Port subscribed      sender=(client=0, port=1), dest=(client=128, port=0)</span>
  <span data-ty data-ty-delay="200">  0:1   Port start           client=128, port=1</span>
  <span data-ty data-ty-delay="1000">  0:1   Port subscribed      sender=(client=14, port=0), dest=(client=128, port=1)</span>
  <span data-ty data-ty-delay="200">  0:1   Client start         client=130, port=0</span>
  <span data-ty data-ty-delay="500">  0:1   Port start           client=130, port=0</span>
  <span data-ty data-ty-delay="100">  0:1   Port subscribed      sender=(client=130, port=0), dest=(client=14, port=0)</span>
  <span data-ty data-ty-delay="700"> 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0</span>
  <span data-ty data-ty-delay="200">  0:1   Port unsubscribed    sender=(client=130, port=0), dest=(client=14, port=0)</span>
  <span data-ty data-ty-delay="0">  0:1   Port exit            client=130, port=0</span>
  <span data-ty data-ty-delay="2000">  0:1   Client exit          client=130, port=0</span>
  <span data-ty data-ty-delay="0">  0:1   Port exit            client=129, port=0</span>
  <span data-ty data-ty-delay="0">  0:1   Client exit          client=129, port=0</span>
  <span data-ty data-ty-delay="400">  0:1   Client start         client=129, port=0</span>
  <span data-ty data-ty-delay="20">  0:1   Port start           client=129, port=0</span>
  <span data-ty data-ty-delay="2000"> 14:0   Note on              channel=0, note=100, velocity=3, off_velocity=0, duration=0</span>
  <span data-ty data-ty-delay="3000"> 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0</span>
  <span data-ty data-ty-delay="1000"> 14:0   Note on              channel=0, note=0, velocity=255, off_velocity=0, duration=0</span>
