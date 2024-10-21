# ⚡ GPIO

Human friendly interface to linux GPIO handling.

Without further ado:

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.gpio import find</span>
  <span data-ty="input" data-ty-prompt=">>>">with find() as gpio:</span>
  <span data-ty="input" data-ty-prompt="...">    with gpio.request([1, 2, 8]) as lines:</span>
  <span data-ty="input" data-ty-prompt=">>>">        print(lines[:])</span>
  <span data-ty>{1: 0, 2: 1, 8:0}</span>
</div>

## Basics

The GPIO interface consists of a Device class representing a single gpiochip.

The Device works as a context manager but you can also manually handle open/close.

Example:

```python
from linuxpy.gpio import Device

with Device.from_id(0) as gpio:
    info = gpio.get_info()
    print(info.name, info.label, len(info.lines))
    l0 = info.lines[0]
    print(f"L0: {l0.name!r} {l0.flags.name}")

# output should look somethig like:
# gpiochip0 INT3450:00 32
# L0: '' INPUT
```

The example above also shows how to obtain information about the gpio device
including up to date information about line usage.

linuxpy provides a `find` helper that makes it easier on single chip systems
to work without knowing the chip number. So the example above can be written
using `find`:

```python
from linuxpy.gpio import find

with find() as gpio:
    info = gpio.get_info()
    print(info.name, info.label, len(info.lines))
    l0 = info.lines[0]
    print(f"L0: {l0.name!r} {l0.flags.name}")
```

## Working with lines: Request

Lines need to be requested before working with them.
A request for line(s) reserves it at the OS level for exclusive access by the
requestor.

The API uses a context manager and it looks like this:

```python
with find() as gpio:
    with gpio.request([5, 12]) as lines:
        ...
```

The request is only sent to the OS at the entry of the context manager.

The above example uses lines 5 and 12 in INPUT mode which is the default.

Linuxpy transparently handles requests with more than 64 lines.

The request argument is intented to supports all possible configurations needed.
It can have different forms:

### line number

A single line is reserved with the default configuration (see below for defaults).

Example:

```python
with find() as gpio:
    with gpio.request(5) as lines:
        ...
```

### list of line numbers or line configurations

Example:

```python
with find() as gpio:
    with gpio.request([5, {"line": 6, "direction": "output"}) as lines:
        ...
```

Reserves line 5 with default configuration and line 6 as output.

### dictionary

With keys:
* *name*: the reservation name
* *lines*: the lines to be reserved. Can be
    * a line number
    * list of line numbers or line configs
    * a dict where key is line number and value a line config with "line" ommited

Example:

```python

config = {
    "name": "myself",
    "lines": [5, {"line": 6, "direction": "output"}],
}

# the same above with line config map:

config = {
    "name": "myself",
    "lines": {
        5: {},
        6: {"direction": "output"},
    }
}

with find() as gpio:
    with gpio.request(config) as lines:
        ...
```

### helpers

A line configuration helper is provided:

```python
CLine(nb, direction, bias, drive, edge, clock, debounce) -> dict
```

Example:
```python
from linuxpy.gpio.device import CLine

config = {
    "name": "myself",
    "lines": [CLine(5), CLine(6, "output")]
}

with find() as gpio:
    with gpio.request(config) as lines:
        ...
```

Selecting input / output lines is a common pattern. Linuxpy provides

* `ClineIn(n, **options)` <=> `{"line":n, "direction": "input", **options)`
* `ClineOut(n, **options)` <=> `{"line":n, "direction": "output", **options)`

### Line details

Here are the line configuration options with their restrictions and defaults:

* *direction*:
    * possible values: `input`, `output`
    * default: **input**
* *active*:
    * possible values: `high`, `low`
    * default: **high**
* *bias*:
    * possbile values: `pull-up`, `pull-down`, `none`
    * default: **none**
* *clock*:
    * possbile values: `realtime`, `hte`, `monotonic`
    * default: **monotonic**
* *edge*:
    * possbile values: `rising`, `falling`, `both`, `none`
    * default: **none**
    * restrictions: only valid for INPUT lines
* *drive*:
    * possbile values: `drain`, `source`, `push-pull`.
    * default: **push-pull**
    * restrictions: only valid for OUTPUT lines
* *debounce*:
    * possible values: number (int or float) > 0. Debounce in seconds with micro-second precision
    * default: use the current debouce
    * restrictions: only valid for OUTPUT lines


### Writting

In the following examples we will use the `CLineOut` helper which is short for
`CLine(direction="output")`.

To change OUTPUT line(s) value(s) simply invoke the `set_values` method on
the request object:

```python
with find() as gpio:
    with device.request([CLineOut(5), CLineOut(7)]) as lines:
        lines.set_values({5: 1})
```

The example above reserves lines 5 and 7 for **output** by a client (aka
consumer) called *my sweet app*. It then sets line 5 to 1.
As you can see, it is possible to write only the lines you're interested.



A helper is provided for 'dict like' access. So the example above can also be
written as:

```python
with find() as gpio:
    with device.request([CLineOut(5), CLineOut(7)]) as lines:
        lines[5] = 1
```

The dict like API also supports setting multiple lines.

Here are some examples using the CLineOut helper:

```python
with find() as gpio:
    with device.request([CLineOut(i) for i in range(16)]) as lines:
        # write line 5
        lines[5] = 1
        # set lines 7, 5, to 0 and 1 respectively
        lines[7, 5] = 0, 1
        # set all lines to 0
        lines[:] = 0
        # set lines 3, 10 to 0 and lines 12 to 1, 13 to 0 and 14 to 1
        lines[3, 10, 12:15] = (0, 0, 1, 0, 1)
```

### Reading

Reading line values is very similar to writting:

```python
with find() as gpio:
    with device.request([CLineIn(6), CLineIn(12]) as lines:
        values = lines.get_values([6, 12])

        # values will be something like {6: 0, 12: 1}
```

In the above example with

The "dict like" API is also supported for reading so the above example could be
written as:

```python
with find() as gpio:
    with device.request([CLineIn(6), CLineIn(12]) as lines:
        values = lines[6, 12]

```

A more complex reads also works:

```python

with find() as gpio:
    with device.request([CLineIn(i) for i in range(16)]) as lines:
        # read lines 7, 5
        values = lines[7, 5]
        # read all lines
        values = lines[:]
        # read lines 3, 6, 10, 12, 14
        values = lines[3, 6, 10:16:2]
```


## Edge detection events

The request object can be used as an infinite iterator to watch for line events:

```python

with find() as gpio:
    with device.request([1, 4]) as lines:
        for event in lines:
            print(f"{event.type.name} #{event.sequence} detected for line {event.line}")
```

Reading one event is easy:

```python

event = next(iter(lines))

```

Async API is also supported:

```python
import asyncio


async def main():
    with find() as gpio:
        with device.request([1, 4]) as lines:
            async for event in lines:
                print(f"{event.type.name} #{event.sequence} detected for line {event.line}")


asyncio.run(main())
```
