modprobe -r uleds gpio-sim vivid
modprobe -a uleds gpio-sim
modprobe vivid n_devs=1 node_types=0xe1d3d vid_cap_nr=190 vid_out_nr=191 meta_cap_nr=192 meta_out_nr=193
python scripts/setup-gpio-sim.py
