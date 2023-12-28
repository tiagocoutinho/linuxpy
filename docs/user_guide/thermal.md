# 🌡️ Thermal and cooling

Human friendly interface to linux thermal zone and cooling devices.

Without further ado:

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.thermal import find</span>
  <span data-ty="input" data-ty-prompt=">>>">with find(type="x86_pkg_temp") as tz:</span>
  <span data-ty="input" data-ty-prompt="...">    print(f"X86 temperature: {tz.temperature/1000:6.2f} C")</span>
  <span data-ty>X86 temperature:  63.00 C</span>
</div>
