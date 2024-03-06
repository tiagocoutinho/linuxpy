#
# This file is part of the linuxpy project
#
# Copyright (c) 2023 Tiago Coutinho
# Distributed under the GPLv3 license. See LICENSE for more info.

# This file has been generated by linuxpy.codegen.input
# Date: 2024-03-06 10:59:58.907371
# System: Linux
# Release: 6.5.0-21-generic
# Version: #21~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Feb  9 13:32:52 UTC 2

import enum

from linuxpy.ioctl import IO as _IO, IOR as _IOR, IOW as _IOW, IOWR as _IOWR
from linuxpy.ctypes import u8, u16, i16, i64, cuint, cint, cchar, ccharp
from linuxpy.ctypes import Struct, Union, POINTER, timeval


class Property(enum.IntEnum):
    POINTER = 0x00  # needs a pointer
    DIRECT = 0x01  # direct input devices
    BUTTONPAD = 0x02  # has button(s) under pad
    SEMI_MT = 0x03  # touch rectangle only
    TOPBUTTONPAD = 0x04  # softbuttons at top of pad
    POINTING_STICK = 0x05  # is a pointing stick
    ACCELEROMETER = 0x06  # has accelerometer
    MAX = 0x1F
    CNT = MAX + 1


class EventType(enum.IntEnum):
    SYN = 0x0
    KEY = 0x1
    REL = 0x2
    ABS = 0x3
    MSC = 0x4
    SW = 0x5
    LED = 0x11
    SND = 0x12
    REP = 0x14
    FF = 0x15
    PWR = 0x16
    FF_STATUS = 0x17
    MAX = 0x1F
    CNT = MAX + 1


class Key(enum.IntEnum):
    KEY_RESERVED = 0x0
    KEY_ESC = 0x1
    KEY_1 = 0x2
    KEY_2 = 0x3
    KEY_3 = 0x4
    KEY_4 = 0x5
    KEY_5 = 0x6
    KEY_6 = 0x7
    KEY_7 = 0x8
    KEY_8 = 0x9
    KEY_9 = 0xA
    KEY_0 = 0xB
    KEY_MINUS = 0xC
    KEY_EQUAL = 0xD
    KEY_BACKSPACE = 0xE
    KEY_TAB = 0xF
    KEY_Q = 0x10
    KEY_W = 0x11
    KEY_E = 0x12
    KEY_R = 0x13
    KEY_T = 0x14
    KEY_Y = 0x15
    KEY_U = 0x16
    KEY_I = 0x17
    KEY_O = 0x18
    KEY_P = 0x19
    KEY_LEFTBRACE = 0x1A
    KEY_RIGHTBRACE = 0x1B
    KEY_ENTER = 0x1C
    KEY_LEFTCTRL = 0x1D
    KEY_A = 0x1E
    KEY_S = 0x1F
    KEY_D = 0x20
    KEY_F = 0x21
    KEY_G = 0x22
    KEY_H = 0x23
    KEY_J = 0x24
    KEY_K = 0x25
    KEY_L = 0x26
    KEY_SEMICOLON = 0x27
    KEY_APOSTROPHE = 0x28
    KEY_GRAVE = 0x29
    KEY_LEFTSHIFT = 0x2A
    KEY_BACKSLASH = 0x2B
    KEY_Z = 0x2C
    KEY_X = 0x2D
    KEY_C = 0x2E
    KEY_V = 0x2F
    KEY_B = 0x30
    KEY_N = 0x31
    KEY_M = 0x32
    KEY_COMMA = 0x33
    KEY_DOT = 0x34
    KEY_SLASH = 0x35
    KEY_RIGHTSHIFT = 0x36
    KEY_KPASTERISK = 0x37
    KEY_LEFTALT = 0x38
    KEY_SPACE = 0x39
    KEY_CAPSLOCK = 0x3A
    KEY_F1 = 0x3B
    KEY_F2 = 0x3C
    KEY_F3 = 0x3D
    KEY_F4 = 0x3E
    KEY_F5 = 0x3F
    KEY_F6 = 0x40
    KEY_F7 = 0x41
    KEY_F8 = 0x42
    KEY_F9 = 0x43
    KEY_F10 = 0x44
    KEY_NUMLOCK = 0x45
    KEY_SCROLLLOCK = 0x46
    KEY_KP7 = 0x47
    KEY_KP8 = 0x48
    KEY_KP9 = 0x49
    KEY_KPMINUS = 0x4A
    KEY_KP4 = 0x4B
    KEY_KP5 = 0x4C
    KEY_KP6 = 0x4D
    KEY_KPPLUS = 0x4E
    KEY_KP1 = 0x4F
    KEY_KP2 = 0x50
    KEY_KP3 = 0x51
    KEY_KP0 = 0x52
    KEY_KPDOT = 0x53
    KEY_ZENKAKUHANKAKU = 0x55
    KEY_102ND = 0x56
    KEY_F11 = 0x57
    KEY_F12 = 0x58
    KEY_RO = 0x59
    KEY_KATAKANA = 0x5A
    KEY_HIRAGANA = 0x5B
    KEY_HENKAN = 0x5C
    KEY_KATAKANAHIRAGANA = 0x5D
    KEY_MUHENKAN = 0x5E
    KEY_KPJPCOMMA = 0x5F
    KEY_KPENTER = 0x60
    KEY_RIGHTCTRL = 0x61
    KEY_KPSLASH = 0x62
    KEY_SYSRQ = 0x63
    KEY_RIGHTALT = 0x64
    KEY_LINEFEED = 0x65
    KEY_HOME = 0x66
    KEY_UP = 0x67
    KEY_PAGEUP = 0x68
    KEY_LEFT = 0x69
    KEY_RIGHT = 0x6A
    KEY_END = 0x6B
    KEY_DOWN = 0x6C
    KEY_PAGEDOWN = 0x6D
    KEY_INSERT = 0x6E
    KEY_DELETE = 0x6F
    KEY_MACRO = 0x70
    KEY_MUTE = 0x71
    KEY_VOLUMEDOWN = 0x72
    KEY_VOLUMEUP = 0x73
    KEY_POWER = 116  # SC System Power Down
    KEY_KPEQUAL = 0x75
    KEY_KPPLUSMINUS = 0x76
    KEY_PAUSE = 0x77
    KEY_SCALE = 120  # AL Compiz Scale (Expose)
    KEY_KPCOMMA = 0x79
    KEY_HANGEUL = 0x7A
    KEY_HANGUEL = KEY_HANGEUL
    KEY_HANJA = 0x7B
    KEY_YEN = 0x7C
    KEY_LEFTMETA = 0x7D
    KEY_RIGHTMETA = 0x7E
    KEY_COMPOSE = 0x7F
    KEY_STOP = 128  # AC Stop
    KEY_AGAIN = 0x81
    KEY_PROPS = 130  # AC Properties
    KEY_UNDO = 131  # AC Undo
    KEY_FRONT = 0x84
    KEY_COPY = 133  # AC Copy
    KEY_OPEN = 134  # AC Open
    KEY_PASTE = 135  # AC Paste
    KEY_FIND = 136  # AC Search
    KEY_CUT = 137  # AC Cut
    KEY_HELP = 138  # AL Integrated Help Center
    KEY_MENU = 139  # Menu (show menu)
    KEY_CALC = 140  # AL Calculator
    KEY_SETUP = 0x8D
    KEY_SLEEP = 142  # SC System Sleep
    KEY_WAKEUP = 143  # System Wake Up
    KEY_FILE = 144  # AL Local Machine Browser
    KEY_SENDFILE = 0x91
    KEY_DELETEFILE = 0x92
    KEY_XFER = 0x93
    KEY_PROG1 = 0x94
    KEY_PROG2 = 0x95
    KEY_WWW = 150  # AL Internet Browser
    KEY_MSDOS = 0x97
    KEY_COFFEE = 152  # AL Terminal Lock/Screensaver
    KEY_SCREENLOCK = KEY_COFFEE
    KEY_ROTATE_DISPLAY = 153  # Display orientation for e.g. tablets
    KEY_DIRECTION = KEY_ROTATE_DISPLAY
    KEY_CYCLEWINDOWS = 0x9A
    KEY_MAIL = 0x9B
    KEY_BOOKMARKS = 156  # AC Bookmarks
    KEY_COMPUTER = 0x9D
    KEY_BACK = 158  # AC Back
    KEY_FORWARD = 159  # AC Forward
    KEY_CLOSECD = 0xA0
    KEY_EJECTCD = 0xA1
    KEY_EJECTCLOSECD = 0xA2
    KEY_NEXTSONG = 0xA3
    KEY_PLAYPAUSE = 0xA4
    KEY_PREVIOUSSONG = 0xA5
    KEY_STOPCD = 0xA6
    KEY_RECORD = 0xA7
    KEY_REWIND = 0xA8
    KEY_PHONE = 169  # Media Select Telephone
    KEY_ISO = 0xAA
    KEY_CONFIG = 171  # AL Consumer Control Configuration
    KEY_HOMEPAGE = 172  # AC Home
    KEY_REFRESH = 173  # AC Refresh
    KEY_EXIT = 174  # AC Exit
    KEY_MOVE = 0xAF
    KEY_EDIT = 0xB0
    KEY_SCROLLUP = 0xB1
    KEY_SCROLLDOWN = 0xB2
    KEY_KPLEFTPAREN = 0xB3
    KEY_KPRIGHTPAREN = 0xB4
    KEY_NEW = 181  # AC New
    KEY_REDO = 182  # AC Redo/Repeat
    KEY_F13 = 0xB7
    KEY_F14 = 0xB8
    KEY_F15 = 0xB9
    KEY_F16 = 0xBA
    KEY_F17 = 0xBB
    KEY_F18 = 0xBC
    KEY_F19 = 0xBD
    KEY_F20 = 0xBE
    KEY_F21 = 0xBF
    KEY_F22 = 0xC0
    KEY_F23 = 0xC1
    KEY_F24 = 0xC2
    KEY_PLAYCD = 0xC8
    KEY_PAUSECD = 0xC9
    KEY_PROG3 = 0xCA
    KEY_PROG4 = 0xCB
    KEY_ALL_APPLICATIONS = 204  # AC Desktop Show All Applications
    KEY_DASHBOARD = KEY_ALL_APPLICATIONS
    KEY_SUSPEND = 0xCD
    KEY_CLOSE = 206  # AC Close
    KEY_PLAY = 0xCF
    KEY_FASTFORWARD = 0xD0
    KEY_BASSBOOST = 0xD1
    KEY_PRINT = 210  # AC Print
    KEY_HP = 0xD3
    KEY_CAMERA = 0xD4
    KEY_SOUND = 0xD5
    KEY_QUESTION = 0xD6
    KEY_EMAIL = 0xD7
    KEY_CHAT = 0xD8
    KEY_SEARCH = 0xD9
    KEY_CONNECT = 0xDA
    KEY_FINANCE = 219  # AL Checkbook/Finance
    KEY_SPORT = 0xDC
    KEY_SHOP = 0xDD
    KEY_ALTERASE = 0xDE
    KEY_CANCEL = 223  # AC Cancel
    KEY_BRIGHTNESSDOWN = 0xE0
    KEY_BRIGHTNESSUP = 0xE1
    KEY_MEDIA = 0xE2
    KEY_SWITCHVIDEOMODE = 227  # Cycle between available video
    KEY_KBDILLUMTOGGLE = 0xE4
    KEY_KBDILLUMDOWN = 0xE5
    KEY_KBDILLUMUP = 0xE6
    KEY_SEND = 231  # AC Send
    KEY_REPLY = 232  # AC Reply
    KEY_FORWARDMAIL = 233  # AC Forward Msg
    KEY_SAVE = 234  # AC Save
    KEY_DOCUMENTS = 0xEB
    KEY_BATTERY = 0xEC
    KEY_BLUETOOTH = 0xED
    KEY_WLAN = 0xEE
    KEY_UWB = 0xEF
    KEY_UNKNOWN = 0xF0
    KEY_VIDEO_NEXT = 241  # drive next video source
    KEY_VIDEO_PREV = 242  # drive previous video source
    KEY_BRIGHTNESS_CYCLE = 243  # brightness up, after max is min
    KEY_BRIGHTNESS_AUTO = 244  # Set Auto Brightness: manual
    KEY_BRIGHTNESS_ZERO = KEY_BRIGHTNESS_AUTO
    KEY_DISPLAY_OFF = 245  # display device to off state
    KEY_WWAN = 246  # Wireless WAN (LTE, UMTS, GSM, etc.)
    KEY_WIMAX = KEY_WWAN
    KEY_RFKILL = 247  # Key that controls all radios
    KEY_MICMUTE = 248  # Mute / unmute the microphone
    BTN_MISC = 0x100
    BTN_0 = 0x100
    BTN_1 = 0x101
    BTN_2 = 0x102
    BTN_3 = 0x103
    BTN_4 = 0x104
    BTN_5 = 0x105
    BTN_6 = 0x106
    BTN_7 = 0x107
    BTN_8 = 0x108
    BTN_9 = 0x109
    BTN_MOUSE = 0x110
    BTN_LEFT = 0x110
    BTN_RIGHT = 0x111
    BTN_MIDDLE = 0x112
    BTN_SIDE = 0x113
    BTN_EXTRA = 0x114
    BTN_FORWARD = 0x115
    BTN_BACK = 0x116
    BTN_TASK = 0x117
    BTN_JOYSTICK = 0x120
    BTN_TRIGGER = 0x120
    BTN_THUMB = 0x121
    BTN_THUMB2 = 0x122
    BTN_TOP = 0x123
    BTN_TOP2 = 0x124
    BTN_PINKIE = 0x125
    BTN_BASE = 0x126
    BTN_BASE2 = 0x127
    BTN_BASE3 = 0x128
    BTN_BASE4 = 0x129
    BTN_BASE5 = 0x12A
    BTN_BASE6 = 0x12B
    BTN_DEAD = 0x12F
    BTN_GAMEPAD = 0x130
    BTN_SOUTH = 0x130
    BTN_A = BTN_SOUTH
    BTN_EAST = 0x131
    BTN_B = BTN_EAST
    BTN_C = 0x132
    BTN_NORTH = 0x133
    BTN_X = BTN_NORTH
    BTN_WEST = 0x134
    BTN_Y = BTN_WEST
    BTN_Z = 0x135
    BTN_TL = 0x136
    BTN_TR = 0x137
    BTN_TL2 = 0x138
    BTN_TR2 = 0x139
    BTN_SELECT = 0x13A
    BTN_START = 0x13B
    BTN_MODE = 0x13C
    BTN_THUMBL = 0x13D
    BTN_THUMBR = 0x13E
    BTN_DIGI = 0x140
    BTN_TOOL_PEN = 0x140
    BTN_TOOL_RUBBER = 0x141
    BTN_TOOL_BRUSH = 0x142
    BTN_TOOL_PENCIL = 0x143
    BTN_TOOL_AIRBRUSH = 0x144
    BTN_TOOL_FINGER = 0x145
    BTN_TOOL_MOUSE = 0x146
    BTN_TOOL_LENS = 0x147
    BTN_TOOL_QUINTTAP = 0x148  # Five fingers on trackpad
    BTN_STYLUS3 = 0x149
    BTN_TOUCH = 0x14A
    BTN_STYLUS = 0x14B
    BTN_STYLUS2 = 0x14C
    BTN_TOOL_DOUBLETAP = 0x14D
    BTN_TOOL_TRIPLETAP = 0x14E
    BTN_TOOL_QUADTAP = 0x14F  # Four fingers on trackpad
    BTN_WHEEL = 0x150
    BTN_GEAR_DOWN = 0x150
    BTN_GEAR_UP = 0x151
    KEY_OK = 0x160
    KEY_SELECT = 0x161
    KEY_GOTO = 0x162
    KEY_CLEAR = 0x163
    KEY_POWER2 = 0x164
    KEY_OPTION = 0x165
    KEY_INFO = 0x166  # AL OEM Features/Tips/Tutorial
    KEY_TIME = 0x167
    KEY_VENDOR = 0x168
    KEY_ARCHIVE = 0x169
    KEY_PROGRAM = 0x16A  # Media Select Program Guide
    KEY_CHANNEL = 0x16B
    KEY_FAVORITES = 0x16C
    KEY_EPG = 0x16D
    KEY_PVR = 0x16E  # Media Select Home
    KEY_MHP = 0x16F
    KEY_LANGUAGE = 0x170
    KEY_TITLE = 0x171
    KEY_SUBTITLE = 0x172
    KEY_ANGLE = 0x173
    KEY_FULL_SCREEN = 0x174  # AC View Toggle
    KEY_ZOOM = KEY_FULL_SCREEN
    KEY_MODE = 0x175
    KEY_KEYBOARD = 0x176
    KEY_ASPECT_RATIO = 0x177  # HUTRR37: Aspect
    KEY_SCREEN = KEY_ASPECT_RATIO
    KEY_PC = 0x178  # Media Select Computer
    KEY_TV = 0x179  # Media Select TV
    KEY_TV2 = 0x17A  # Media Select Cable
    KEY_VCR = 0x17B  # Media Select VCR
    KEY_VCR2 = 0x17C  # VCR Plus
    KEY_SAT = 0x17D  # Media Select Satellite
    KEY_SAT2 = 0x17E
    KEY_CD = 0x17F  # Media Select CD
    KEY_TAPE = 0x180  # Media Select Tape
    KEY_RADIO = 0x181
    KEY_TUNER = 0x182  # Media Select Tuner
    KEY_PLAYER = 0x183
    KEY_TEXT = 0x184
    KEY_DVD = 0x185  # Media Select DVD
    KEY_AUX = 0x186
    KEY_MP3 = 0x187
    KEY_AUDIO = 0x188  # AL Audio Browser
    KEY_VIDEO = 0x189  # AL Movie Browser
    KEY_DIRECTORY = 0x18A
    KEY_LIST = 0x18B
    KEY_MEMO = 0x18C  # Media Select Messages
    KEY_CALENDAR = 0x18D
    KEY_RED = 0x18E
    KEY_GREEN = 0x18F
    KEY_YELLOW = 0x190
    KEY_BLUE = 0x191
    KEY_CHANNELUP = 0x192  # Channel Increment
    KEY_CHANNELDOWN = 0x193  # Channel Decrement
    KEY_FIRST = 0x194
    KEY_LAST = 0x195  # Recall Last
    KEY_AB = 0x196
    KEY_NEXT = 0x197
    KEY_RESTART = 0x198
    KEY_SLOW = 0x199
    KEY_SHUFFLE = 0x19A
    KEY_BREAK = 0x19B
    KEY_PREVIOUS = 0x19C
    KEY_DIGITS = 0x19D
    KEY_TEEN = 0x19E
    KEY_TWEN = 0x19F
    KEY_VIDEOPHONE = 0x1A0  # Media Select Video Phone
    KEY_GAMES = 0x1A1  # Media Select Games
    KEY_ZOOMIN = 0x1A2  # AC Zoom In
    KEY_ZOOMOUT = 0x1A3  # AC Zoom Out
    KEY_ZOOMRESET = 0x1A4  # AC Zoom
    KEY_WORDPROCESSOR = 0x1A5  # AL Word Processor
    KEY_EDITOR = 0x1A6  # AL Text Editor
    KEY_SPREADSHEET = 0x1A7  # AL Spreadsheet
    KEY_GRAPHICSEDITOR = 0x1A8  # AL Graphics Editor
    KEY_PRESENTATION = 0x1A9  # AL Presentation App
    KEY_DATABASE = 0x1AA  # AL Database App
    KEY_NEWS = 0x1AB  # AL Newsreader
    KEY_VOICEMAIL = 0x1AC  # AL Voicemail
    KEY_ADDRESSBOOK = 0x1AD  # AL Contacts/Address Book
    KEY_MESSENGER = 0x1AE  # AL Instant Messaging
    KEY_DISPLAYTOGGLE = 0x1AF  # Turn display (LCD) on and off
    KEY_BRIGHTNESS_TOGGLE = KEY_DISPLAYTOGGLE
    KEY_SPELLCHECK = 0x1B0  # AL Spell Check
    KEY_LOGOFF = 0x1B1  # AL Logoff
    KEY_DOLLAR = 0x1B2
    KEY_EURO = 0x1B3
    KEY_FRAMEBACK = 0x1B4  # Consumer - transport controls
    KEY_FRAMEFORWARD = 0x1B5
    KEY_CONTEXT_MENU = 0x1B6  # GenDesc - system context menu
    KEY_MEDIA_REPEAT = 0x1B7  # Consumer - transport control
    KEY_10CHANNELSUP = 0x1B8  # 10 channels up (10+)
    KEY_10CHANNELSDOWN = 0x1B9  # 10 channels down (10-)
    KEY_IMAGES = 0x1BA  # AL Image Browser
    KEY_NOTIFICATION_CENTER = 0x1BC  # Show/hide the notification center
    KEY_PICKUP_PHONE = 0x1BD  # Answer incoming call
    KEY_HANGUP_PHONE = 0x1BE  # Decline incoming call
    KEY_DEL_EOL = 0x1C0
    KEY_DEL_EOS = 0x1C1
    KEY_INS_LINE = 0x1C2
    KEY_DEL_LINE = 0x1C3
    KEY_FN = 0x1D0
    KEY_FN_ESC = 0x1D1
    KEY_FN_F1 = 0x1D2
    KEY_FN_F2 = 0x1D3
    KEY_FN_F3 = 0x1D4
    KEY_FN_F4 = 0x1D5
    KEY_FN_F5 = 0x1D6
    KEY_FN_F6 = 0x1D7
    KEY_FN_F7 = 0x1D8
    KEY_FN_F8 = 0x1D9
    KEY_FN_F9 = 0x1DA
    KEY_FN_F10 = 0x1DB
    KEY_FN_F11 = 0x1DC
    KEY_FN_F12 = 0x1DD
    KEY_FN_1 = 0x1DE
    KEY_FN_2 = 0x1DF
    KEY_FN_D = 0x1E0
    KEY_FN_E = 0x1E1
    KEY_FN_F = 0x1E2
    KEY_FN_S = 0x1E3
    KEY_FN_B = 0x1E4
    KEY_FN_RIGHT_SHIFT = 0x1E5
    KEY_BRL_DOT1 = 0x1F1
    KEY_BRL_DOT2 = 0x1F2
    KEY_BRL_DOT3 = 0x1F3
    KEY_BRL_DOT4 = 0x1F4
    KEY_BRL_DOT5 = 0x1F5
    KEY_BRL_DOT6 = 0x1F6
    KEY_BRL_DOT7 = 0x1F7
    KEY_BRL_DOT8 = 0x1F8
    KEY_BRL_DOT9 = 0x1F9
    KEY_BRL_DOT10 = 0x1FA
    KEY_NUMERIC_0 = 0x200  # used by phones, remote controls,
    KEY_NUMERIC_1 = 0x201  # and other keypads
    KEY_NUMERIC_2 = 0x202
    KEY_NUMERIC_3 = 0x203
    KEY_NUMERIC_4 = 0x204
    KEY_NUMERIC_5 = 0x205
    KEY_NUMERIC_6 = 0x206
    KEY_NUMERIC_7 = 0x207
    KEY_NUMERIC_8 = 0x208
    KEY_NUMERIC_9 = 0x209
    KEY_NUMERIC_STAR = 0x20A
    KEY_NUMERIC_POUND = 0x20B
    KEY_NUMERIC_A = 0x20C  # Phone key A - HUT Telephony 0xb9
    KEY_NUMERIC_B = 0x20D
    KEY_NUMERIC_C = 0x20E
    KEY_NUMERIC_D = 0x20F
    KEY_CAMERA_FOCUS = 0x210
    KEY_WPS_BUTTON = 0x211  # WiFi Protected Setup key
    KEY_TOUCHPAD_TOGGLE = 0x212  # Request switch touchpad on or off
    KEY_TOUCHPAD_ON = 0x213
    KEY_TOUCHPAD_OFF = 0x214
    KEY_CAMERA_ZOOMIN = 0x215
    KEY_CAMERA_ZOOMOUT = 0x216
    KEY_CAMERA_UP = 0x217
    KEY_CAMERA_DOWN = 0x218
    KEY_CAMERA_LEFT = 0x219
    KEY_CAMERA_RIGHT = 0x21A
    KEY_ATTENDANT_ON = 0x21B
    KEY_ATTENDANT_OFF = 0x21C
    KEY_ATTENDANT_TOGGLE = 0x21D  # Attendant call on or off
    KEY_LIGHTS_TOGGLE = 0x21E  # Reading light on or off
    BTN_DPAD_UP = 0x220
    BTN_DPAD_DOWN = 0x221
    BTN_DPAD_LEFT = 0x222
    BTN_DPAD_RIGHT = 0x223
    KEY_ALS_TOGGLE = 0x230  # Ambient light sensor
    KEY_ROTATE_LOCK_TOGGLE = 0x231  # Display rotation lock
    KEY_BUTTONCONFIG = 0x240  # AL Button Configuration
    KEY_TASKMANAGER = 0x241  # AL Task/Project Manager
    KEY_JOURNAL = 0x242  # AL Log/Journal/Timecard
    KEY_CONTROLPANEL = 0x243  # AL Control Panel
    KEY_APPSELECT = 0x244  # AL Select Task/Application
    KEY_SCREENSAVER = 0x245  # AL Screen Saver
    KEY_VOICECOMMAND = 0x246  # Listening Voice Command
    KEY_ASSISTANT = 0x247  # AL Context-aware desktop assistant
    KEY_KBD_LAYOUT_NEXT = 0x248  # AC Next Keyboard Layout Select
    KEY_EMOJI_PICKER = 0x249  # Show/hide emoji picker (HUTRR101)
    KEY_DICTATE = 0x24A  # Start or Stop Voice Dictation Session (HUTRR99)
    KEY_BRIGHTNESS_MIN = 0x250  # Set Brightness to Minimum
    KEY_BRIGHTNESS_MAX = 0x251  # Set Brightness to Maximum
    KEY_KBDINPUTASSIST_PREV = 0x260
    KEY_KBDINPUTASSIST_NEXT = 0x261
    KEY_KBDINPUTASSIST_PREVGROUP = 0x262
    KEY_KBDINPUTASSIST_NEXTGROUP = 0x263
    KEY_KBDINPUTASSIST_ACCEPT = 0x264
    KEY_KBDINPUTASSIST_CANCEL = 0x265
    KEY_RIGHT_UP = 0x266
    KEY_RIGHT_DOWN = 0x267
    KEY_LEFT_UP = 0x268
    KEY_LEFT_DOWN = 0x269
    KEY_ROOT_MENU = 0x26A  # Show Device's Root Menu
    KEY_MEDIA_TOP_MENU = 0x26B
    KEY_NUMERIC_11 = 0x26C
    KEY_NUMERIC_12 = 0x26D
    KEY_AUDIO_DESC = 0x26E
    KEY_3D_MODE = 0x26F
    KEY_NEXT_FAVORITE = 0x270
    KEY_STOP_RECORD = 0x271
    KEY_PAUSE_RECORD = 0x272
    KEY_VOD = 0x273  # Video on Demand
    KEY_UNMUTE = 0x274
    KEY_FASTREVERSE = 0x275
    KEY_SLOWREVERSE = 0x276
    KEY_DATA = 0x277
    KEY_ONSCREEN_KEYBOARD = 0x278
    KEY_PRIVACY_SCREEN_TOGGLE = 0x279
    KEY_SELECTIVE_SCREENSHOT = 0x27A
    KEY_MACRO1 = 0x290
    KEY_MACRO2 = 0x291
    KEY_MACRO3 = 0x292
    KEY_MACRO4 = 0x293
    KEY_MACRO5 = 0x294
    KEY_MACRO6 = 0x295
    KEY_MACRO7 = 0x296
    KEY_MACRO8 = 0x297
    KEY_MACRO9 = 0x298
    KEY_MACRO10 = 0x299
    KEY_MACRO11 = 0x29A
    KEY_MACRO12 = 0x29B
    KEY_MACRO13 = 0x29C
    KEY_MACRO14 = 0x29D
    KEY_MACRO15 = 0x29E
    KEY_MACRO16 = 0x29F
    KEY_MACRO17 = 0x2A0
    KEY_MACRO18 = 0x2A1
    KEY_MACRO19 = 0x2A2
    KEY_MACRO20 = 0x2A3
    KEY_MACRO21 = 0x2A4
    KEY_MACRO22 = 0x2A5
    KEY_MACRO23 = 0x2A6
    KEY_MACRO24 = 0x2A7
    KEY_MACRO25 = 0x2A8
    KEY_MACRO26 = 0x2A9
    KEY_MACRO27 = 0x2AA
    KEY_MACRO28 = 0x2AB
    KEY_MACRO29 = 0x2AC
    KEY_MACRO30 = 0x2AD
    KEY_MACRO_RECORD_START = 0x2B0
    KEY_MACRO_RECORD_STOP = 0x2B1
    KEY_MACRO_PRESET_CYCLE = 0x2B2
    KEY_MACRO_PRESET1 = 0x2B3
    KEY_MACRO_PRESET2 = 0x2B4
    KEY_MACRO_PRESET3 = 0x2B5
    KEY_KBD_LCD_MENU1 = 0x2B8
    KEY_KBD_LCD_MENU2 = 0x2B9
    KEY_KBD_LCD_MENU3 = 0x2BA
    KEY_KBD_LCD_MENU4 = 0x2BB
    KEY_KBD_LCD_MENU5 = 0x2BC
    BTN_TRIGGER_HAPPY = 0x2C0
    BTN_TRIGGER_HAPPY1 = 0x2C0
    BTN_TRIGGER_HAPPY2 = 0x2C1
    BTN_TRIGGER_HAPPY3 = 0x2C2
    BTN_TRIGGER_HAPPY4 = 0x2C3
    BTN_TRIGGER_HAPPY5 = 0x2C4
    BTN_TRIGGER_HAPPY6 = 0x2C5
    BTN_TRIGGER_HAPPY7 = 0x2C6
    BTN_TRIGGER_HAPPY8 = 0x2C7
    BTN_TRIGGER_HAPPY9 = 0x2C8
    BTN_TRIGGER_HAPPY10 = 0x2C9
    BTN_TRIGGER_HAPPY11 = 0x2CA
    BTN_TRIGGER_HAPPY12 = 0x2CB
    BTN_TRIGGER_HAPPY13 = 0x2CC
    BTN_TRIGGER_HAPPY14 = 0x2CD
    BTN_TRIGGER_HAPPY15 = 0x2CE
    BTN_TRIGGER_HAPPY16 = 0x2CF
    BTN_TRIGGER_HAPPY17 = 0x2D0
    BTN_TRIGGER_HAPPY18 = 0x2D1
    BTN_TRIGGER_HAPPY19 = 0x2D2
    BTN_TRIGGER_HAPPY20 = 0x2D3
    BTN_TRIGGER_HAPPY21 = 0x2D4
    BTN_TRIGGER_HAPPY22 = 0x2D5
    BTN_TRIGGER_HAPPY23 = 0x2D6
    BTN_TRIGGER_HAPPY24 = 0x2D7
    BTN_TRIGGER_HAPPY25 = 0x2D8
    BTN_TRIGGER_HAPPY26 = 0x2D9
    BTN_TRIGGER_HAPPY27 = 0x2DA
    BTN_TRIGGER_HAPPY28 = 0x2DB
    BTN_TRIGGER_HAPPY29 = 0x2DC
    BTN_TRIGGER_HAPPY30 = 0x2DD
    BTN_TRIGGER_HAPPY31 = 0x2DE
    BTN_TRIGGER_HAPPY32 = 0x2DF
    BTN_TRIGGER_HAPPY33 = 0x2E0
    BTN_TRIGGER_HAPPY34 = 0x2E1
    BTN_TRIGGER_HAPPY35 = 0x2E2
    BTN_TRIGGER_HAPPY36 = 0x2E3
    BTN_TRIGGER_HAPPY37 = 0x2E4
    BTN_TRIGGER_HAPPY38 = 0x2E5
    BTN_TRIGGER_HAPPY39 = 0x2E6
    BTN_TRIGGER_HAPPY40 = 0x2E7
    KEY_MIN_INTERESTING = KEY_MUTE
    KEY_MAX = 0x2FF
    KEY_CNT = KEY_MAX + 1


class Relative(enum.IntEnum):
    X = 0x0
    Y = 0x1
    Z = 0x2
    RX = 0x3
    RY = 0x4
    RZ = 0x5
    HWHEEL = 0x6
    DIAL = 0x7
    WHEEL = 0x8
    MISC = 0x9
    RESERVED = 0xA
    WHEEL_HI_RES = 0xB
    HWHEEL_HI_RES = 0xC
    MAX = 0xF
    CNT = MAX + 1


class Absolute(enum.IntEnum):
    X = 0x0
    Y = 0x1
    Z = 0x2
    RX = 0x3
    RY = 0x4
    RZ = 0x5
    THROTTLE = 0x6
    RUDDER = 0x7
    WHEEL = 0x8
    GAS = 0x9
    BRAKE = 0xA
    HAT0X = 0x10
    HAT0Y = 0x11
    HAT1X = 0x12
    HAT1Y = 0x13
    HAT2X = 0x14
    HAT2Y = 0x15
    HAT3X = 0x16
    HAT3Y = 0x17
    PRESSURE = 0x18
    DISTANCE = 0x19
    TILT_X = 0x1A
    TILT_Y = 0x1B
    TOOL_WIDTH = 0x1C
    VOLUME = 0x20
    MISC = 0x28
    RESERVED = 0x2E
    MT_SLOT = 0x2F  # MT slot being modified
    MT_TOUCH_MAJOR = 0x30  # Major axis of touching ellipse
    MT_TOUCH_MINOR = 0x31  # Minor axis (omit if circular)
    MT_WIDTH_MAJOR = 0x32  # Major axis of approaching ellipse
    MT_WIDTH_MINOR = 0x33  # Minor axis (omit if circular)
    MT_ORIENTATION = 0x34  # Ellipse orientation
    MT_POSITION_X = 0x35  # Center X touch position
    MT_POSITION_Y = 0x36  # Center Y touch position
    MT_TOOL_TYPE = 0x37  # Type of touching device
    MT_BLOB_ID = 0x38  # Group a set of packets as a blob
    MT_TRACKING_ID = 0x39  # Unique ID of initiated contact
    MT_PRESSURE = 0x3A  # Pressure on contact area
    MT_DISTANCE = 0x3B  # Contact hover distance
    MT_TOOL_X = 0x3C  # Center X tool position
    MT_TOOL_Y = 0x3D  # Center Y tool position
    MAX = 0x3F
    CNT = MAX + 1


class Miscelaneous(enum.IntEnum):
    SERIAL = 0x0
    PULSELED = 0x1
    GESTURE = 0x2
    RAW = 0x3
    SCAN = 0x4
    TIMESTAMP = 0x5
    MAX = 0x7
    CNT = MAX + 1


class Synchronization(enum.IntEnum):
    REPORT = 0x0
    CONFIG = 0x1
    MT_REPORT = 0x2
    DROPPED = 0x3
    MAX = 0xF
    CNT = MAX + 1


class Led(enum.IntEnum):
    NUML = 0x0
    CAPSL = 0x1
    SCROLLL = 0x2
    COMPOSE = 0x3
    KANA = 0x4
    SLEEP = 0x5
    SUSPEND = 0x6
    MUTE = 0x7
    MISC = 0x8
    MAIL = 0x9
    CHARGING = 0xA
    MAX = 0xF
    CNT = MAX + 1


class ID(enum.IntEnum):
    BUS = 0x0
    VENDOR = 0x1
    PRODUCT = 0x2
    VERSION = 0x3


class Bus(enum.IntEnum):
    PCI = 0x1
    ISAPNP = 0x2
    USB = 0x3
    HIL = 0x4
    BLUETOOTH = 0x5
    VIRTUAL = 0x6
    ISA = 0x10
    I8042 = 0x11
    XTKBD = 0x12
    RS232 = 0x13
    GAMEPORT = 0x14
    PARPORT = 0x15
    AMIGA = 0x16
    ADB = 0x17
    I2C = 0x18
    HOST = 0x19
    GSC = 0x1A
    ATARI = 0x1B
    SPI = 0x1C
    RMI = 0x1D
    CEC = 0x1E
    INTEL_ISHTP = 0x1F


class MultiTouch(enum.IntEnum):
    FINGER = 0x0
    PEN = 0x1
    PALM = 0x2
    DIAL = 0xA
    MAX = 0xF


class ForceFeedbackStatus(enum.IntEnum):
    STOPPED = 0x0
    PLAYING = 0x1
    MAX = 0x1


class ForceFeedback(enum.IntEnum):
    RUMBLE = 0x50
    PERIODIC = 0x51
    CONSTANT = 0x52
    SPRING = 0x53
    FRICTION = 0x54
    DAMPER = 0x55
    INERTIA = 0x56
    RAMP = 0x57
    EFFECT_MIN = RUMBLE
    EFFECT_MAX = RAMP
    SQUARE = 0x58
    TRIANGLE = 0x59
    SINE = 0x5A
    SAW_UP = 0x5B
    SAW_DOWN = 0x5C
    CUSTOM = 0x5D
    WAVEFORM_MIN = SQUARE
    WAVEFORM_MAX = CUSTOM
    GAIN = 0x60
    AUTOCENTER = 0x61
    MAX_EFFECTS = GAIN
    MAX = 0x7F
    CNT = MAX + 1


class UIForceFeedback(enum.IntEnum):
    pass


class Sound(enum.IntEnum):
    CLICK = 0x0
    BELL = 0x1
    TONE = 0x2
    MAX = 0x7
    CNT = MAX + 1


class Switch(enum.IntEnum):
    LID = 0x00  # set = lid shut
    TABLET_MODE = 0x01  # set = tablet mode
    HEADPHONE_INSERT = 0x02  # set = inserted
    RFKILL_ALL = 0x03  # rfkill master switch, type "any"
    RADIO = RFKILL_ALL  # deprecated
    MICROPHONE_INSERT = 0x04  # set = inserted
    DOCK = 0x05  # set = pluggedcinto dock
    LINEOUT_INSERT = 0x06  # set = inserted
    JACK_PHYSICAL_INSERT = 0x07  # set = mechanical switch set
    VIDEOOUT_INSERT = 0x08  # set = inserted
    CAMERA_LENS_COVER = 0x09  # set = lens covered
    KEYPAD_SLIDE = 0x0A  # set = keypad slide out
    FRONT_PROXIMITY = 0x0B  # set = front proximity sensor active
    ROTATE_LOCK = 0x0C  # set = rotate locked/disabled
    LINEIN_INSERT = 0x0D  # set = inserted
    MUTE_DEVICE = 0x0E  # set = device disabled
    PEN_INSERTED = 0x0F  # set = pen inserted
    MACHINE_COVER = 0x10  # set = cover closed
    MAX = 0x10
    CNT = MAX + 1


class AutoRepeat(enum.IntEnum):
    DELAY = 0x0
    PERIOD = 0x1
    MAX = 0x1
    CNT = MAX + 1


class input_event(Struct):
    pass


input_event._fields_ = [("time", timeval), ("type", u16), ("code", u16), ("value", cint)]


class input_id(Struct):
    pass


input_id._fields_ = [("bustype", u16), ("vendor", u16), ("product", u16), ("version", u16)]


class input_absinfo(Struct):
    pass


input_absinfo._fields_ = [
    ("value", cint),
    ("minimum", cint),
    ("maximum", cint),
    ("fuzz", cint),
    ("flat", cint),
    ("resolution", cint),
]


class input_keymap_entry(Struct):
    pass


input_keymap_entry._fields_ = [("flags", u8), ("len", u8), ("index", u16), ("keycode", cuint), ("scancode", cchar * 32)]


class input_mask(Struct):
    pass


input_mask._fields_ = [("type", cuint), ("codes_size", cuint), ("codes_ptr", i64)]


class ff_replay(Struct):
    pass


ff_replay._fields_ = [("length", u16), ("delay", u16)]


class ff_trigger(Struct):
    pass


ff_trigger._fields_ = [("button", u16), ("interval", u16)]


class ff_envelope(Struct):
    pass


ff_envelope._fields_ = [("attack_length", u16), ("attack_level", u16), ("fade_length", u16), ("fade_level", u16)]


class ff_constant_effect(Struct):
    pass


ff_constant_effect._fields_ = [("level", i16), ("envelope", ff_envelope)]


class ff_ramp_effect(Struct):
    pass


ff_ramp_effect._fields_ = [("start_level", i16), ("end_level", i16), ("envelope", ff_envelope)]


class ff_condition_effect(Struct):
    pass


ff_condition_effect._fields_ = [
    ("right_saturation", u16),
    ("left_saturation", u16),
    ("right_coeff", i16),
    ("left_coeff", i16),
    ("deadband", u16),
    ("center", i16),
]


class ff_periodic_effect(Struct):
    pass


ff_periodic_effect._fields_ = [
    ("waveform", u16),
    ("period", u16),
    ("magnitude", i16),
    ("offset", i16),
    ("phase", u16),
    ("envelope", ff_envelope),
    ("custom_len", cuint),
    ("custom_data", POINTER(i16)),
]


class ff_rumble_effect(Struct):
    pass


ff_rumble_effect._fields_ = [("strong_magnitude", u16), ("weak_magnitude", u16)]


class ff_effect(Struct):
    class M1(Union):
        pass

    M1._fields_ = [
        ("constant", ff_constant_effect),
        ("ramp", ff_ramp_effect),
        ("periodic", ff_periodic_effect),
        ("condition", ff_condition_effect * 2),
        ("rumble", ff_rumble_effect),
    ]


ff_effect._fields_ = [
    ("type", u16),
    ("id", i16),
    ("direction", u16),
    ("trigger", ff_trigger),
    ("replay", ff_replay),
    ("u", ff_effect.M1),
]


class uinput_ff_upload(Struct):
    pass


uinput_ff_upload._fields_ = [("request_id", cuint), ("retval", cint), ("effect", ff_effect), ("old", ff_effect)]


class uinput_ff_erase(Struct):
    pass


uinput_ff_erase._fields_ = [("request_id", cuint), ("retval", cint), ("effect_id", cuint)]


class uinput_setup(Struct):
    pass


uinput_setup._fields_ = [("id", input_id), ("name", cchar * 80), ("ff_effects_max", cuint)]


class uinput_abs_setup(Struct):
    pass


uinput_abs_setup._fields_ = [("code", u16), ("absinfo", input_absinfo)]


class uinput_user_dev(Struct):
    pass


uinput_user_dev._fields_ = [
    ("name", cchar * 80),
    ("id", input_id),
    ("ff_effects_max", cuint),
    ("absmax", cint * 64),
    ("absmin", cint * 64),
    ("absfuzz", cint * 64),
    ("absflat", cint * 64),
]


class UIOC(enum.IntEnum):
    DEV_CREATE = _IO("U", 1)
    DEV_DESTROY = _IO("U", 2)
    DEV_SETUP = _IOW("U", 3, uinput_setup)
    ABS_SETUP = _IOW("U", 4, uinput_abs_setup)
    SET_EVBIT = _IOW("U", 100, cint)
    SET_KEYBIT = _IOW("U", 101, cint)
    SET_RELBIT = _IOW("U", 102, cint)
    SET_ABSBIT = _IOW("U", 103, cint)
    SET_MSCBIT = _IOW("U", 104, cint)
    SET_LEDBIT = _IOW("U", 105, cint)
    SET_SNDBIT = _IOW("U", 106, cint)
    SET_FFBIT = _IOW("U", 107, cint)
    SET_PHYS = _IOW("U", 108, ccharp)
    SET_SWBIT = _IOW("U", 109, cint)
    SET_PROPBIT = _IOW("U", 110, cint)
    BEGIN_FF_UPLOAD = _IOWR("U", 200, uinput_ff_upload)
    END_FF_UPLOAD = _IOW("U", 201, uinput_ff_upload)
    BEGIN_FF_ERASE = _IOWR("U", 202, uinput_ff_erase)
    END_FF_ERASE = _IOW("U", 203, uinput_ff_erase)
    GET_VERSION = _IOR("U", 45, cuint)
