# 💡 Led

Human friendly interface to linux led handling.

Without further ado:

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.led import find</span>
  <span data-ty="input" data-ty-prompt=">>>">caps_lock = find(function="capslock")</span>
  <span data-ty="input" data-ty-prompt=">>>">print(caps_lock.max_brightness)</span>
  <span data-ty>1</span>
  <span data-ty="input" data-ty-prompt=">>>">print(caps_lock.brightness)</span>
  <span data-ty>0</span>
  <span data-ty="input" data-ty-prompt=">>>">caps_lock.brightness = 1</span>
  <span data-ty="input" data-ty-prompt=">>>">print(caps_lock.brightness)</span>
  <span data-ty>1</span>
</div>
