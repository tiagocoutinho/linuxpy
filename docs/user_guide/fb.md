# 📺 Frame buffer

Human friendly interface to linux frame buffer.

Without further ado:

<div class="termy" data-ty-macos>
  <span data-ty="input" data-ty-prompt="$">python</span>
  <span data-ty="input" data-ty-prompt=">>>">from linuxpy.fb.device import find</span>
  <span data-ty="input" data-ty-prompt=">>>">with find() as fb:</span>
  <span data-ty="input" data-ty-prompt="...">    print(fb.get_fix_screen_info())</span>
  <span data-ty>
  FixScreenInfo(name='i915drmfb',
                memory_start=0,
                memory_size=33177600,
                type=Type.PACKED_PIXELS: 0,
                type_aux=Text.MDA: 0,
                visual=Visual.TRUECOLOR: 2,
                x_pan_step=1,
                y_pan_step=1,
                y_wrap_step=0,
                line_size=15360,
                mmap_start=0,
                mmap_size=0,
                acceleration=Acceleration.NONE: 0,
                capabilities=Capability: 0)
  </span>
</div>
