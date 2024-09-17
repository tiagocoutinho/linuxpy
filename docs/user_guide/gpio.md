# ⚡ GPIO

Human friendly interface to linux GPIO handling.

Without further ado:

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.gpio import find</span>
  <span data-ty="input" data-ty-prompt=">>>">with find() as gpio:</span>
  <span data-ty="input" data-ty-prompt="...">    with gpio[1, 2, 5:8] as lines:</span>
  <span data-ty="input" data-ty-prompt=">>>">        print(lines[:])</span>
  <span data-ty>{1: 0, 2: 1, 5: 0, 6: 1, 7:0}</span>
</div>
