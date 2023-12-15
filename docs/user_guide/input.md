# Input

Human friendly interface to the Linux Input subsystem.

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

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python -m asyncio</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.input.device import find_gamepad</span>
  <span data-ty="input" data-ty-prompt=">>>">with find_gamepad() as pad:</span>
  <span data-ty="input" data-ty-prompt="...">    async for event in pad:</span>
  <span data-ty="input" data-ty-prompt="...">        print(event)</span>

  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.348099, type=&lt;EventType.SYN: 0>, code=&lt;Synchronization.REPORT: 0>, value=0)</span>
  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.361564, type=&lt;EventType.REL: 2>, code=&lt;Relative.X: 0>, value=-1)</span>
  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.361564, type=&lt;EventType.REL: 2>, code=&lt;Relative.Y: 1>, value=1)</span>
  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.361564, type=&lt;EventType.SYN: 0>, code=&lt;Synchronization.REPORT: 0>, value=0)</span>
  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.371128, type=&lt;EventType.REL: 2>, code=&lt;Relative.X: 0>, value=-1)</span>
  <span data-ty data-ty-delay="200">InputEvent(time=1697520475.371128, type=&lt;EventType.SYN: 0>, code=&lt;Synchronization.REPORT: 0>, value=0)</span>
  <span data-ty data-ty-delay="200">...</span>
</div>


## References

* [Input (Latest)](https://www.kernel.org/doc/html/latest/input/)
* [Input 6.2](https://www.kernel.org/doc/html/v6.2/input/)
