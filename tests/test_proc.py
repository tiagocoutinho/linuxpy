import inspect
import math
from unittest import mock

from ward import test

from linuxpy import proc

CPU_TEMPLATE = """\
processor	: {id}
vendor_id	: GenuineIntel
cpu family	: 6
model		: 165
model name	: Intel(R) Core(TM) i9-10885H CPU @ 2.40GHz
stepping	: 2
microcode	: 0xfc
cpu MHz		: 2999.793
cache size	: 16384 KB
physical id	: 0
siblings	: 16
core id		: 0
cpu cores	: 8
apicid		: 0
initial apicid	: 0
fpu		: yes
fpu_exception	: yes
cpuid level	: 22
wp		: yes
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp lm constant_tsc art arch_perfmon pebs bts rep_good nopl xtopology nonstop_tsc cpuid aperfmperf pni pclmulqdq dtes64 monitor ds_cpl vmx smx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb ssbd ibrs ibpb stibp ibrs_enhanced tpr_shadow flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid mpx rdseed adx smap clflushopt intel_pt xsaveopt xsavec xgetbv1 xsaves dtherm ida arat pln pts hwp hwp_notify hwp_act_window hwp_epp vnmi pku ospke md_clear flush_l1d arch_capabilities
vmx flags	: vnmi preemption_timer posted_intr invvpid ept_x_only ept_ad ept_1gb flexpriority apicv tsc_offset vtpr mtf vapic ept vpid unrestricted_guest vapic_reg vid ple shadow_vmcs pml ept_mode_based_exec
bugs		: spectre_v1 spectre_v2 spec_store_bypass swapgs itlb_multihit srbds mmio_stale_data retbleed eibrs_pbrsb gds bhi
bogomips	: 4800.00
clflush size	: 64
cache_alignment	: 64
address sizes	: 39 bits physical, 48 bits virtual
power management:
"""

MEM_TEMPLATE = """\
MemTotal:       98619100 kB
MemFree:        73660316 kB
MemAvailable:   91063536 kB
Buffers:         1496592 kB
Cached:         17645388 kB
SwapCached:            0 kB
Active:          6880480 kB
Inactive:       14339476 kB
Active(anon):    3863824 kB
Inactive(anon):        0 kB
Active(file):    3016656 kB
Inactive(file): 14339476 kB
Unevictable:     1622076 kB
Mlocked:             240 kB
SwapTotal:       1998844 kB
SwapFree:        1998844 kB
Zswap:                 0 kB
Zswapped:              0 kB
Dirty:                96 kB
Writeback:             0 kB
AnonPages:       3700040 kB
Mapped:          1009560 kB
Shmem:           1785856 kB
KReclaimable:    1037584 kB
Slab:            1547064 kB
SReclaimable:    1037584 kB
SUnreclaim:       509480 kB
KernelStack:       25584 kB
PageTables:        67636 kB
SecPageTables:         0 kB
NFS_Unstable:          0 kB
Bounce:                0 kB
WritebackTmp:          0 kB
CommitLimit:    51308392 kB
Committed_AS:   29492228 kB
VmallocTotal:   34359738367 kB
VmallocUsed:      231708 kB
VmallocChunk:          0 kB
Percpu:            15872 kB
HardwareCorrupted:     0 kB
AnonHugePages:         0 kB
ShmemHugePages:  1605632 kB
ShmemPmdMapped:        0 kB
FileHugePages:         0 kB
FilePmdMapped:         0 kB
Unaccepted:            0 kB
HugePages_Total:       0
HugePages_Free:        0
HugePages_Rsvd:        0
HugePages_Surp:        0
Hugepagesize:       2048 kB
Hugetlb:               0 kB
DirectMap4k:      463584 kB
DirectMap2M:    15011840 kB
DirectMap1G:    84934656 kB"""

MOUNTS_TEMPLATE = """\
vivid 311296 0 - Live 0x0000000000000000
v4l2_tpg 114688 1 vivid, Live 0x0000000000000000
videobuf2_dma_contig 24576 1 vivid, Live 0x0000000000000000
v4l2_dv_timings 36864 1 vivid, Live 0x0000000000000000
uleds 12288 0 - Live 0x0000000000000000
gpio_aggregator 24576 0 - Live 0x0000000000000000
gpio_sim 28672 20 - Live 0x0000000000000000
rfcomm 98304 16 - Live 0x0000000000000000
snd_seq_dummy 12288 0 - Live 0x0000000000000000
snd_hrtimer 12288 1 - Live 0x0000000000000000
snd_seq_midi 24576 0 - Live 0x0000000000000000
snd_seq_midi_event 16384 1 snd_seq_midi, Live 0x0000000000000000
snd_rawmidi 57344 1 snd_seq_midi, Live 0x0000000000000000
snd_seq 114688 9 snd_seq_dummy,snd_seq_midi,snd_seq_midi_event, Live 0x0000000000000000
snd_seq_device 16384 3 snd_seq_midi,snd_rawmidi,snd_seq, Live 0x0000000000000000
xt_conntrack 12288 2 - Live 0x0000000000000000
nft_chain_nat 12288 3 - Live 0x0000000000000000
xt_MASQUERADE 16384 2 - Live 0x0000000000000000
nf_nat 61440 2 nft_chain_nat,xt_MASQUERADE, Live 0x0000000000000000
bridge 421888 0 - Live 0x0000000000000000
stp 12288 1 bridge, Live 0x0000000000000000
llc 16384 2 bridge,stp, Live 0x0000000000000000
nf_conntrack_netlink 57344 0 - Live 0x0000000000000000
nf_conntrack 196608 4 xt_conntrack,xt_MASQUERADE,nf_nat,nf_conntrack_netlink, Live 0x0000000000000000
nf_defrag_ipv6 24576 1 nf_conntrack, Live 0x0000000000000000
nf_defrag_ipv4 12288 1 nf_conntrack, Live 0x0000000000000000
xfrm_user 61440 1 - Live 0x0000000000000000
xfrm_algo 16384 1 xfrm_user, Live 0x0000000000000000
xt_addrtype 12288 2 - Live 0x0000000000000000
nft_compat 20480 6 - Live 0x0000000000000000
nf_tables 372736 124 nft_chain_nat,nft_compat, Live 0x0000000000000000
vboxnetadp 28672 0 - Live 0x0000000000000000 (OE)
vboxnetflt 32768 0 - Live 0x0000000000000000 (OE)
vboxdrv 696320 2 vboxnetadp,vboxnetflt, Live 0x0000000000000000 (OE)
ccm 20480 6 - Live 0x0000000000000000
overlay 212992 0 - Live 0x0000000000000000
qrtr 53248 2 - Live 0x0000000000000000
cmac 12288 3 - Live 0x0000000000000000
algif_hash 12288 1 - Live 0x0000000000000000
algif_skcipher 16384 1 - Live 0x0000000000000000
af_alg 32768 6 algif_hash,algif_skcipher, Live 0x0000000000000000
bnep 32768 2 - Live 0x0000000000000000
binfmt_misc 24576 1 - Live 0x0000000000000000
zfs 6598656 6 - Live 0x0000000000000000 (PO)
spl 180224 1 zfs, Live 0x0000000000000000 (O)
snd_ctl_led 24576 0 - Live 0x0000000000000000
snd_hda_codec_realtek 200704 1 - Live 0x0000000000000000
snd_hda_codec_generic 122880 1 snd_hda_codec_realtek, Live 0x0000000000000000
intel_uncore_frequency 16384 0 - Live 0x0000000000000000
intel_uncore_frequency_common 16384 1 intel_uncore_frequency, Live 0x0000000000000000
snd_sof_pci_intel_cnl 12288 0 - Live 0x0000000000000000
snd_sof_intel_hda_common 217088 1 snd_sof_pci_intel_cnl, Live 0x0000000000000000
soundwire_intel 73728 1 snd_sof_intel_hda_common, Live 0x0000000000000000
snd_sof_intel_hda_mlink 45056 2 snd_sof_intel_hda_common,soundwire_intel, Live 0x0000000000000000
soundwire_cadence 40960 1 soundwire_intel, Live 0x0000000000000000
snd_sof_intel_hda 24576 1 snd_sof_intel_hda_common, Live 0x0000000000000000
snd_sof_pci 24576 2 snd_sof_pci_intel_cnl,snd_sof_intel_hda_common, Live 0x0000000000000000
snd_sof_xtensa_dsp 12288 1 snd_sof_intel_hda_common, Live 0x0000000000000000
snd_sof 380928 3 snd_sof_intel_hda_common,snd_sof_intel_hda,snd_sof_pci, Live 0x0000000000000000
snd_sof_utils 16384 1 snd_sof, Live 0x0000000000000000
snd_soc_hdac_hda 24576 1 snd_sof_intel_hda_common, Live 0x0000000000000000
intel_tcc_cooling 12288 0 - Live 0x0000000000000000
snd_hda_ext_core 32768 4 snd_sof_intel_hda_common,snd_sof_intel_hda_mlink,snd_sof_intel_hda,snd_soc_hdac_hda, Live 0x0000000000000000
x86_pkg_temp_thermal 20480 0 - Live 0x0000000000000000
snd_soc_acpi_intel_match 98304 2 snd_sof_pci_intel_cnl,snd_sof_intel_hda_common, Live 0x0000000000000000
intel_powerclamp 24576 0 - Live 0x0000000000000000
snd_soc_acpi 16384 2 snd_sof_intel_hda_common,snd_soc_acpi_intel_match, Live 0x0000000000000000
coretemp 24576 0 - Live 0x0000000000000000
soundwire_generic_allocation 12288 1 soundwire_intel, Live 0x0000000000000000
soundwire_bus 110592 3 soundwire_intel,soundwire_cadence,soundwire_generic_allocation, Live 0x0000000000000000
kvm_intel 487424 0 - Live 0x0000000000000000
snd_soc_core 438272 4 snd_sof_intel_hda_common,soundwire_intel,snd_sof,snd_soc_hdac_hda, Live 0x0000000000000000
snd_compress 28672 1 snd_soc_core, Live 0x0000000000000000
cmdlinepart 12288 0 - Live 0x0000000000000000
spi_nor 163840 0 - Live 0x0000000000000000
iwlmvm 864256 0 - Live 0x0000000000000000
ac97_bus 12288 1 snd_soc_core, Live 0x0000000000000000
mtd 98304 3 cmdlinepart,spi_nor, Live 0x0000000000000000
snd_hda_codec_hdmi 94208 2 - Live 0x0000000000000000
nls_iso8859_1 12288 1 - Live 0x0000000000000000
mei_hdcp 28672 0 - Live 0x0000000000000000
mei_pxp 16384 0 - Live 0x0000000000000000
nouveau 3096576 5 - Live 0x0000000000000000
ucsi_ccg 24576 0 - Live 0x0000000000000000
ee1004 16384 0 - Live 0x0000000000000000
i915 4272128 39 - Live 0x0000000000000000
snd_pcm_dmaengine 16384 1 snd_soc_core, Live 0x0000000000000000
intel_rapl_msr 20480 0 - Live 0x0000000000000000
kvm 1404928 1 kvm_intel, Live 0x0000000000000000
mac80211 1720320 1 iwlmvm, Live 0x0000000000000000
tps6598x 90112 0 - Live 0x0000000000000000
btusb 77824 0 - Live 0x0000000000000000
mxm_wmi 12288 1 nouveau, Live 0x0000000000000000
btrtl 32768 1 btusb, Live 0x0000000000000000
irqbypass 12288 1 kvm, Live 0x0000000000000000
uvcvideo 139264 0 - Live 0x0000000000000000
drm_gpuvm 45056 1 nouveau, Live 0x0000000000000000
snd_hda_intel 61440 2 - Live 0x0000000000000000
drm_exec 12288 2 nouveau,drm_gpuvm, Live 0x0000000000000000
libarc4 12288 1 mac80211, Live 0x0000000000000000
btintel 57344 1 btusb, Live 0x0000000000000000
videobuf2_vmalloc 20480 2 vivid,uvcvideo, Live 0x0000000000000000
snd_intel_dspcfg 36864 3 snd_sof_intel_hda_common,snd_sof,snd_hda_intel, Live 0x0000000000000000
btbcm 24576 1 btusb, Live 0x0000000000000000
gpu_sched 61440 1 nouveau, Live 0x0000000000000000
btmtk 12288 1 btusb, Live 0x0000000000000000
drm_ttm_helper 12288 1 nouveau, Live 0x0000000000000000
drm_buddy 20480 1 i915, Live 0x0000000000000000
uvc 12288 1 uvcvideo, Live 0x0000000000000000
snd_intel_sdw_acpi 16384 2 snd_sof_intel_hda_common,snd_intel_dspcfg, Live 0x0000000000000000
rapl 20480 0 - Live 0x0000000000000000
videobuf2_memops 16384 2 videobuf2_dma_contig,videobuf2_vmalloc, Live 0x0000000000000000
videobuf2_v4l2 36864 2 vivid,uvcvideo, Live 0x0000000000000000
snd_hda_codec 204800 6 snd_hda_codec_realtek,snd_hda_codec_generic,snd_sof_intel_hda,snd_soc_hdac_hda,snd_hda_codec_hdmi,snd_hda_intel, Live 0x0000000000000000
ttm 110592 3 nouveau,i915,drm_ttm_helper, Live 0x0000000000000000
bluetooth 1028096 44 rfcomm,bnep,btusb,btrtl,btintel,btbcm,btmtk, Live 0x0000000000000000
videodev 352256 3 vivid,uvcvideo,videobuf2_v4l2, Live 0x0000000000000000
snd_hda_core 139264 9 snd_hda_codec_realtek,snd_hda_codec_generic,snd_sof_intel_hda_common,snd_sof_intel_hda,snd_soc_hdac_hda,snd_hda_ext_core,snd_hda_codec_hdmi,snd_hda_intel,snd_hda_codec, Live 0x0000000000000000
iwlwifi 598016 1 iwlmvm, Live 0x0000000000000000
snd_hwdep 20480 1 snd_hda_codec, Live 0x0000000000000000
processor_thermal_device_pci_legacy 12288 0 - Live 0x0000000000000000
processor_thermal_device 20480 1 processor_thermal_device_pci_legacy, Live 0x0000000000000000
videobuf2_common 81920 6 vivid,videobuf2_dma_contig,uvcvideo,videobuf2_vmalloc,videobuf2_memops,videobuf2_v4l2, Live 0x0000000000000000
processor_thermal_wt_hint 16384 1 processor_thermal_device, Live 0x0000000000000000
think_lmi 45056 0 - Live 0x0000000000000000
processor_thermal_rfim 32768 1 processor_thermal_device, Live 0x0000000000000000
spi_intel_pci 12288 0 - Live 0x0000000000000000
ecdh_generic 16384 2 bluetooth, Live 0x0000000000000000
intel_cstate 24576 0 - Live 0x0000000000000000
drm_display_helper 237568 2 nouveau,i915, Live 0x0000000000000000
processor_thermal_rapl 16384 1 processor_thermal_device, Live 0x0000000000000000
firmware_attributes_class 12288 1 think_lmi, Live 0x0000000000000000
wmi_bmof 12288 0 - Live 0x0000000000000000
intel_wmi_thunderbolt 16384 0 - Live 0x0000000000000000
mc 81920 5 vivid,uvcvideo,videobuf2_v4l2,videodev,videobuf2_common, Live 0x0000000000000000
ecc 45056 1 ecdh_generic, Live 0x0000000000000000
snd_pcm 192512 11 snd_sof_intel_hda_common,soundwire_intel,snd_sof,snd_sof_utils,snd_soc_core,snd_compress,snd_hda_codec_hdmi,snd_pcm_dmaengine,snd_hda_intel,snd_hda_codec,snd_hda_core, Live 0x0000000000000000
spi_intel 32768 1 spi_intel_pci, Live 0x0000000000000000
mei_me 53248 2 - Live 0x0000000000000000
intel_rapl_common 40960 2 intel_rapl_msr,processor_thermal_rapl, Live 0x0000000000000000
cfg80211 1323008 3 iwlmvm,mac80211,iwlwifi, Live 0x0000000000000000
cec 94208 3 vivid,i915,drm_display_helper, Live 0x0000000000000000
i2c_i801 36864 0 - Live 0x0000000000000000
processor_thermal_wt_req 12288 1 processor_thermal_device, Live 0x0000000000000000
i2c_nvidia_gpu 12288 0 - Live 0x0000000000000000
processor_thermal_power_floor 12288 1 processor_thermal_device, Live 0x0000000000000000
i2c_smbus 16384 1 i2c_i801, Live 0x0000000000000000
mei 167936 5 mei_hdcp,mei_pxp,mei_me, Live 0x0000000000000000
rc_core 73728 3 cec, Live 0x0000000000000000
snd_timer 49152 3 snd_hrtimer,snd_seq,snd_pcm, Live 0x0000000000000000
i2c_ccgx_ucsi 12288 1 i2c_nvidia_gpu, Live 0x0000000000000000
processor_thermal_mbox 12288 4 processor_thermal_wt_hint,processor_thermal_rfim,processor_thermal_wt_req,processor_thermal_power_floor, Live 0x0000000000000000
i2c_algo_bit 16384 2 nouveau,i915, Live 0x0000000000000000
intel_pch_thermal 20480 0 - Live 0x0000000000000000
intel_soc_dts_iosf 20480 1 processor_thermal_device_pci_legacy, Live 0x0000000000000000
serial_multi_instantiate 16384 0 - Live 0x0000000000000000
thinkpad_acpi 163840 0 - Live 0x0000000000000000
int3403_thermal 16384 0 - Live 0x0000000000000000
nvram 16384 1 thinkpad_acpi, Live 0x0000000000000000
int340x_thermal_zone 16384 2 processor_thermal_device,int3403_thermal, Live 0x0000000000000000
intel_pmc_core 118784 0 - Live 0x0000000000000000
intel_vsec 20480 1 intel_pmc_core, Live 0x0000000000000000
int3400_thermal 24576 0 - Live 0x0000000000000000
pmt_telemetry 16384 1 intel_pmc_core, Live 0x0000000000000000
acpi_thermal_rel 20480 1 int3400_thermal, Live 0x0000000000000000
pmt_class 12288 1 pmt_telemetry, Live 0x0000000000000000
acpi_pad 184320 0 - Live 0x0000000000000000
joydev 32768 0 - Live 0x0000000000000000
input_leds 12288 0 - Live 0x0000000000000000
mac_hid 12288 0 - Live 0x0000000000000000
serio_raw 20480 0 - Live 0x0000000000000000
sch_fq_codel 24576 2 - Live 0x0000000000000000
msr 12288 0 - Live 0x0000000000000000
parport_pc 53248 0 - Live 0x0000000000000000
ppdev 24576 0 - Live 0x0000000000000000
lp 28672 0 - Live 0x0000000000000000
parport 73728 3 parport_pc,ppdev,lp, Live 0x0000000000000000
efi_pstore 12288 0 - Live 0x0000000000000000
nfnetlink 20480 5 nf_conntrack_netlink,nft_compat,nf_tables, Live 0x0000000000000000
dmi_sysfs 24576 0 - Live 0x0000000000000000
ip_tables 32768 0 - Live 0x0000000000000000
x_tables 65536 5 xt_conntrack,xt_MASQUERADE,xt_addrtype,nft_compat,ip_tables, Live 0x0000000000000000
autofs4 57344 2 - Live 0x0000000000000000
btrfs 2015232 0 - Live 0x0000000000000000
blake2b_generic 24576 0 - Live 0x0000000000000000
dm_crypt 65536 1 - Live 0x0000000000000000
mmc_block 65536 0 - Live 0x0000000000000000
raid10 73728 0 - Live 0x0000000000000000
raid456 192512 0 - Live 0x0000000000000000
async_raid6_recov 20480 1 raid456, Live 0x0000000000000000
async_memcpy 16384 2 raid456,async_raid6_recov, Live 0x0000000000000000
async_pq 20480 2 raid456,async_raid6_recov, Live 0x0000000000000000
async_xor 16384 3 raid456,async_raid6_recov,async_pq, Live 0x0000000000000000
async_tx 16384 5 raid456,async_raid6_recov,async_memcpy,async_pq,async_xor, Live 0x0000000000000000
xor 20480 2 btrfs,async_xor, Live 0x0000000000000000
raid6_pq 126976 4 btrfs,raid456,async_raid6_recov,async_pq, Live 0x0000000000000000
libcrc32c 12288 5 nf_nat,nf_conntrack,nf_tables,btrfs,raid456, Live 0x0000000000000000
raid1 57344 0 - Live 0x0000000000000000
raid0 24576 0 - Live 0x0000000000000000
dm_mirror 24576 0 - Live 0x0000000000000000
dm_region_hash 24576 1 dm_mirror, Live 0x0000000000000000
dm_log 20480 2 dm_mirror,dm_region_hash, Live 0x0000000000000000
hid_generic 12288 0 - Live 0x0000000000000000
usbhid 77824 0 - Live 0x0000000000000000
hid 180224 2 hid_generic,usbhid, Live 0x0000000000000000
crct10dif_pclmul 12288 1 - Live 0x0000000000000000
crc32_pclmul 12288 0 - Live 0x0000000000000000
polyval_clmulni 12288 0 - Live 0x0000000000000000
polyval_generic 12288 1 polyval_clmulni, Live 0x0000000000000000
ghash_clmulni_intel 16384 0 - Live 0x0000000000000000
rtsx_pci_sdmmc 36864 0 - Live 0x0000000000000000
nvme 61440 3 - Live 0x0000000000000000
sha256_ssse3 32768 0 - Live 0x0000000000000000
sha1_ssse3 32768 0 - Live 0x0000000000000000
thunderbolt 516096 0 - Live 0x0000000000000000
psmouse 217088 0 - Live 0x0000000000000000
nvme_core 208896 4 nvme, Live 0x0000000000000000
e1000e 356352 0 - Live 0x0000000000000000
rtsx_pci 143360 1 rtsx_pci_sdmmc, Live 0x0000000000000000
ucsi_acpi 12288 0 - Live 0x0000000000000000
snd 143360 22 snd_rawmidi,snd_seq,snd_seq_device,snd_ctl_led,snd_hda_codec_realtek,snd_hda_codec_generic,snd_sof,snd_soc_core,snd_compress,snd_hda_codec_hdmi,snd_hda_intel,snd_hda_codec,snd_hwdep,snd_pcm,snd_timer,thinkpad_acpi, Live 0x0000000000000000
nvme_auth 28672 1 nvme_core, Live 0x0000000000000000
typec_ucsi 61440 2 ucsi_ccg,ucsi_acpi, Live 0x0000000000000000
intel_lpss_pci 24576 0 - Live 0x0000000000000000
intel_lpss 12288 1 intel_lpss_pci, Live 0x0000000000000000
xhci_pci 24576 0 - Live 0x0000000000000000
idma64 20480 0 - Live 0x0000000000000000
typec 106496 2 tps6598x,typec_ucsi, Live 0x0000000000000000
soundcore 16384 2 snd_ctl_led,snd, Live 0x0000000000000000
xhci_pci_renesas 20480 1 xhci_pci, Live 0x0000000000000000
video 73728 3 nouveau,i915,thinkpad_acpi, Live 0x0000000000000000
ledtrig_audio 12288 2 snd_ctl_led,thinkpad_acpi, Live 0x0000000000000000
platform_profile 12288 1 thinkpad_acpi, Live 0x0000000000000000
wmi 28672 6 nouveau,mxm_wmi,think_lmi,wmi_bmof,intel_wmi_thunderbolt,video, Live 0x0000000000000000
pinctrl_cannonlake 36864 1 - Live 0x0000000000000000
aesni_intel 356352 56439 - Live 0x0000000000000000
crypto_simd 16384 1 aesni_intel, Live 0x0000000000000000
cryptd 24576 28218 ghash_clmulni_intel,crypto_simd, Live 0x0000000000000000"""


@test("iter_cpu_info")
def _():
    assert inspect.isgeneratorfunction(proc.iter_cpu_info)
    assert inspect.isgenerator(proc.iter_cpu_info())

    text = "\n".join(CPU_TEMPLATE.format(id=i) for i in range(8))

    with mock.patch("linuxpy.proc.Path.read_text", return_value=text):
        result = list(proc.iter_cpu_info())
        assert len(result) == 8
        assert result[0]["processor"] == 0
        assert math.isclose(result[0]["cpu MHz"], 2999.793)
        assert len(result[0]["bugs"]) == 11


@test("iter_mem_info")
def _():
    assert inspect.isgeneratorfunction(proc.iter_mem_info)
    assert inspect.isgenerator(proc.iter_mem_info())

    with mock.patch("linuxpy.proc.Path.read_text", return_value=MEM_TEMPLATE):
        result = dict(proc.iter_mem_info())
        assert result["MemTotal"] == 100985958400
        assert result["HugePages_Rsvd"] == 0


@test("iter_modules")
def _():
    assert inspect.isgeneratorfunction(proc.iter_modules)
    assert inspect.isgenerator(proc.iter_modules())

    with mock.patch("linuxpy.proc.Path.read_text", return_value=MOUNTS_TEMPLATE):
        result = list(proc.iter_modules())
        assert len(result) == MOUNTS_TEMPLATE.count("\n") + 1
