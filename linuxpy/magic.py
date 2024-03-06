#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# This file has been generated by linuxpy.codegen.magic
# Date: 2024-03-06 10:59:58.788230
# System: Linux
# Release: 6.5.0-21-generic
# Version: #21~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Feb  9 13:32:52 UTC 2

import enum


class Magic(enum.IntEnum):
    ADFS_SUPER = 0xADF5
    AFFS_SUPER = 0xADFF
    AFS_SUPER = 0x5346414F
    AUTOFS_SUPER = 0x187
    CODA_SUPER = 0x73757245
    CRAMFS = 0x28CD3D45  # some random number
    CRAMFS_WEND = 0x453DCD28  # magic number with the wrong endianess
    DEBUGFS = 0x64626720
    SECURITYFS = 0x73636673
    SELINUX = 0xF97CFF8C
    SMACK = 0x43415D53  # "SMAC"
    RAMFS = 0x858458F6  # some random number
    TMPFS = 0x1021994
    HUGETLBFS = 0x958458F6  # some random number
    SQUASHFS = 0x73717368
    ECRYPTFS_SUPER = 0xF15F
    EFS_SUPER = 0x414A53
    EROFS_SUPER_V1 = 0xE0F5E1E2
    EXT2_SUPER = 0xEF53
    EXT3_SUPER = 0xEF53
    XENFS_SUPER = 0xABBA1974
    EXT4_SUPER = 0xEF53
    BTRFS_SUPER = 0x9123683E
    NILFS_SUPER = 0x3434
    F2FS_SUPER = 0xF2F52010
    HPFS_SUPER = 0xF995E849
    ISOFS_SUPER = 0x9660
    JFFS2_SUPER = 0x72B6
    XFS_SUPER = 0x58465342  # "XFSB"
    PSTOREFS = 0x6165676C
    EFIVARFS = 0xDE5E81E4
    HOSTFS_SUPER = 0xC0FFEE
    OVERLAYFS_SUPER = 0x794C7630
    MINIX_SUPER = 0x137F  # minix v1 fs, 14cchar names
    MINIX_SUPER2 = 0x138F  # minix v1 fs, 30cchar names
    MINIX2_SUPER = 0x2468  # minix v2 fs, 14cchar names
    MINIX2_SUPER2 = 0x2478  # minix v2 fs, 30cchar names
    MINIX3_SUPER = 0x4D5A  # minix v3 fs, 60cchar names
    MSDOS_SUPER = 0x4D44  # MD
    NCP_SUPER = 0x564C  # Guess, what 0x564c is :-)
    NFS_SUPER = 0x6969
    OCFS2_SUPER = 0x7461636F
    OPENPROM_SUPER = 0x9FA1
    QNX4_SUPER = 0x002F  # qnx4 fs detection
    QNX6_SUPER = 0x68191122  # qnx6 fs detection
    AFS_FS = 0x6B414653
    REISERFS_SUPER = 0x52654973  # used by gcc
    SMB_SUPER = 0x517B
    CGROUP_SUPER = 0x27E0EB
    CGROUP2_SUPER = 0x63677270
    RDTGROUP_SUPER = 0x7655821
    STACK_END = 0x57AC6E9D
    TRACEFS = 0x74726163
    V9FS = 0x1021997
    BDEVFS = 0x62646576
    DAXFS = 0x64646178
    BINFMTFS = 0x42494E4D
    DEVPTS_SUPER = 0x1CD1
    BINDERFS_SUPER = 0x6C6F6F70
    FUTEXFS_SUPER = 0xBAD1DEA
    PIPEFS = 0x50495045
    PROC_SUPER = 0x9FA0
    SOCKFS = 0x534F434B
    SYSFS = 0x62656572
    USBDEVICE_SUPER = 0x9FA2
    MTD_INODE_FS = 0x11307854
    ANON_INODE_FS = 0x9041934
    BTRFS_TEST = 0x73727279
    NSFS = 0x6E736673
    BPF_FS = 0xCAFE4A11
    AAFS = 0x5A3C69F0
    ZONEFS = 0x5A4F4653
    UDF_SUPER = 0x15013346
    BALLOON_KVM = 0x13661366
    ZSMALLOC = 0x58295829
    DMA_BUF = 0x444D4142  # "DMAB"
    DEVMEM = 0x454D444D  # "DMEM"
    Z3FOLD = 0x33
    PPC_CMM = 0xC7571590
    SECRETMEM = 0x5345434D  # "SECM"
    SHIFTFS = 0x6A656A62
