# Input

API not documented yet. Just this example:

```python
import time
from linuxpy.input.device import find_gamepads

pad = next(find_gamepads())
abs = pad.absolute

with pad:
    while True:
	    print(f"X:{abs.x:>3} | Y:{abs.y:>3} | RX:{abs.rx:>3} | RY:{abs.ry:>3}", end="\r", flush=True)
	    time.sleep(0.1)
```

## asyncio

<!-- termynal -->

```console
$ python -m asyncio

>>> from linuxpy.input.device import find_gamepads
>>> with next(find_gamepads()) as pad:
...     async for event in pad:
...         print(event)
InputEvent(time=1697520475.348099, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.361564, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.361564, type=<EventType.REL: 2>, code=<Relative.Y: 1>, value=1)
InputEvent(time=1697520475.361564, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.371128, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.371128, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.384468, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.384468, type=<EventType.REL: 2>, code=<Relative.Y: 1>, value=1)
InputEvent(time=1697520475.384468, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.398041, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-2)
InputEvent(time=1697520475.398041, type=<EventType.REL: 2>, code=<Relative.Y: 1>, value=1)
InputEvent(time=1697520475.398041, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
InputEvent(time=1697520475.424895, type=<EventType.REL: 2>, code=<Relative.X: 0>, value=-1)
InputEvent(time=1697520475.424895, type=<EventType.SYN: 0>, code=<Synchronization.REPORT: 0>, value=0)
...
```

## References

* [Input (Latest)](https://www.kernel.org/doc/html/latest/input/)
* [Input 6.2](https://www.kernel.org/doc/html/v6.2/input/)
