from pathlib import Path
from unittest import mock

from ward import test

from linuxpy import mounts

MOUNTS_SIMPLE = """\
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /run tmpfs rw,nosuid,nodev,noexec,relatime,size=9861912k,mode=755,inode64 0 0
configfs /sys/kernel/config configfs rw,nosuid,nodev,noexec,relatime 0 0"""

MOUNTS_TEMPLATE = """\
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
udev /dev devtmpfs rw,nosuid,relatime,size=49270380k,nr_inodes=12317595,mode=755,inode64 0 0
devpts /dev/pts devpts rw,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
tmpfs /run tmpfs rw,nosuid,nodev,noexec,relatime,size=9861912k,mode=755,inode64 0 0
efivarfs /sys/firmware/efi/efivars efivarfs rw,nosuid,nodev,noexec,relatime 0 0
/dev/mapper/vgmint-root / ext4 rw,relatime,errors=remount-ro 0 0
securityfs /sys/kernel/security securityfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /dev/shm tmpfs rw,nosuid,nodev,inode64 0 0
tmpfs /run/lock tmpfs rw,nosuid,nodev,noexec,relatime,size=5120k,inode64 0 0
cgroup2 /sys/fs/cgroup cgroup2 rw,nosuid,nodev,noexec,relatime,nsdelegate,memory_recursiveprot 0 0
pstore /sys/fs/pstore pstore rw,nosuid,nodev,noexec,relatime 0 0
bpf /sys/fs/bpf bpf rw,nosuid,nodev,noexec,relatime,mode=700 0 0
systemd-1 /proc/sys/fs/binfmt_misc autofs rw,relatime,fd=32,pgrp=1,timeout=0,minproto=5,maxproto=5,direct,pipe_ino=5686 0 0
tracefs /sys/kernel/tracing tracefs rw,nosuid,nodev,noexec,relatime 0 0
mqueue /dev/mqueue mqueue rw,nosuid,nodev,noexec,relatime 0 0
debugfs /sys/kernel/debug debugfs rw,nosuid,nodev,noexec,relatime 0 0
hugetlbfs /dev/hugepages hugetlbfs rw,nosuid,nodev,relatime,pagesize=2M 0 0
fusectl /sys/fs/fuse/connections fusectl rw,nosuid,nodev,noexec,relatime 0 0
configfs /sys/kernel/config configfs rw,nosuid,nodev,noexec,relatime 0 0
/dev/nvme0n1p2 /boot ext4 rw,relatime 0 0
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077,dmask=0077,codepage=437,iocharset=iso8859-1,shortname=mixed,errors=remount-ro 0 0
binfmt_misc /proc/sys/fs/binfmt_misc binfmt_misc rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /run/user/1000 tmpfs rw,nosuid,nodev,relatime,size=9861908k,nr_inodes=2465477,mode=700,uid=1000,gid=1000,inode64 0 0
/home/hsimpson/.Private /home/hsimpson ecryptfs rw,nosuid,nodev,relatime,ecryptfs_fnek_sig=2951f678f7fde33b5,ecryptfs_sig=e65dea35de352238,ecryptfs_cipher=aes,ecryptfs_key_bytes=16,ecryptfs_unlink_sigs 0 0
gvfsd-fuse /run/user/1000/gvfs fuse.gvfsd-fuse rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
portal /run/user/1000/doc fuse.portal rw,nosuid,nodev,relatime,user_id=1000,group_id=1000 0 0
overlay /var/lib/docker/overlay2/bb81f129721b5ae1782280d7c8c9289c5395e359e797270b8f4daecf7a24b0e2/merged overlay rw,relatime,lowerdir=/var/lib/docker/overlay2/l/E3ZZ37L6ATZCOLMPEAD3NQDIFL:/var/lib/docker/overlay2/l/H6MFRIIFVTTFY264I46UCWN66W:/var/lib/docker/overlay2/l/I5X5PVOX4OOMZKKU6WGOHEI3IP:/var/lib/docker/overlay2/l/P22PGWBFMF6RQAWJQO2MAUEY7S:/var/lib/docker/overlay2/l/TIRFWLNRFNVQRSSP32CL535RGO:/var/lib/docker/overlay2/l/6JDCZEAYN6M7C3D4QVVLA6Y5CQ:/var/lib/docker/overlay2/l/XX72NFO4RURTOLDGQEK3F2UYDE:/var/lib/docker/overlay2/l/XYM6SCQMMJMGKUYKYL6OBBFZDR:/var/lib/docker/overlay2/l/KPGLUMQYLYFKU4XXM4MB32BQFS:/var/lib/docker/overlay2/l/2ZAHACDHOU5SHZK3324MJXIZF4:/var/lib/docker/overlay2/l/BFTJ47NO54JEDV7LIWG7PX5E5P:/var/lib/docker/overlay2/l/MGXJYBEJXUQDJY3VBQ3NZLHLIY:/var/lib/docker/overlay2/l/DQCXWSISSPL773IINMH6BP624R:/var/lib/docker/overlay2/l/KAEMNS32GBU2NTQLVOZRRZA45F:/var/lib/docker/overlay2/l/WEESN4RHBA2NVBIHG5G6JFTCMO:/var/lib/docker/overlay2/l/M2OY5PNFD62V3IGAM6A7OV7G45,upperdir=/var/lib/docker/overlay2/bb81f129721b5ae1782280d7c8c9289c5395e359e797270b8f4daecf7a24b0e2/diff,workdir=/var/lib/docker/overlay2/bb81f129721b5ae1782280d7c8c9289c5395e359e797270b8f4daecf7a24b0e2/work,nouserxattr 0 0
overlay /var/lib/docker/overlay2/3818865cdc424d3012743347f2e96845cf2f75fefa12016706b96c82268962a5/merged overlay rw,relatime,lowerdir=/var/lib/docker/overlay2/l/TMK7WQLIIFBPIMRN7UCR74FA5U:/var/lib/docker/overlay2/l/3NVLTB7VJPMDJ4VYC7PCN5Y2NA:/var/lib/docker/overlay2/l/ZY4LH2DDIACBPCG3V6F52AUGK5:/var/lib/docker/overlay2/l/N7TXIVTEQPTLLOSJSLSZ2MS5DS:/var/lib/docker/overlay2/l/B35V7LZZ27L4M7YSTL2ZDKVRCZ:/var/lib/docker/overlay2/l/BZI5LWWPGZURFS3SZPFZM7E7GE:/var/lib/docker/overlay2/l/7F2E56JCOQ6I5OLQ67QKAKYKLV:/var/lib/docker/overlay2/l/K5OS5FDLN72UQ2CUCWOVDCLATI:/var/lib/docker/overlay2/l/QYCBSSBJ7CTC5KVIESYD76AQIH,upperdir=/var/lib/docker/overlay2/3818865cdc424d3012743347f2e96845cf2f75fefa12016706b96c82268962a5/diff,workdir=/var/lib/docker/overlay2/3818865cdc424d3012743347f2e96845cf2f75fefa12016706b96c82268962a5/work,nouserxattr 0 0"""


@test("gen_read")
def _():
    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_SIMPLE):
        result = list(mounts.gen_read())
        assert len(result) == 3
        assert result[0] == mounts.MountInfo("sysfs", "/sys", "sysfs", "rw,nosuid,nodev,noexec,relatime".split(","))

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_TEMPLATE):
        result = list(mounts.gen_read())
        assert len(result) == MOUNTS_TEMPLATE.count("\n") + 1


@test("read_from_cache")
def _():
    mounts.cache.cache_clear()

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_SIMPLE):
        result = list(mounts.cache())
        assert len(result) == 3

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_TEMPLATE):
        result = list(mounts.cache())
        assert len(result) == 3


@test("get_mount_point")
def _() -> None:
    mounts.cache.cache_clear()
    mounts.get_mount_point.cache_clear()

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_SIMPLE):
        assert mounts.get_mount_point("sysfs") == Path("/sys")
        assert mounts.get_mount_point("sysfs", "tmpfs") is None
        assert mounts.get_mount_point("tmpfs", "sysfs") is None


@test("sysfs")
def _():
    mounts.cache.cache_clear()
    mounts.get_mount_point.cache_clear()

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_SIMPLE):
        assert mounts.sysfs() == Path("/sys")


@test("configfs")
def _():
    mounts.cache.cache_clear()
    mounts.get_mount_point.cache_clear()

    with mock.patch("linuxpy.mounts.Path.read_text", return_value=MOUNTS_SIMPLE):
        assert mounts.configfs() == Path("/sys/kernel/config")
