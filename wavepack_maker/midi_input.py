"""Windows MIDI 输入封装（基于 ctypes + winmm.dll）。"""

import ctypes
import ctypes.wintypes
from typing import Optional

from PySide6.QtCore import QObject, Signal


# Windows MIDI API 常量
MAXPNAMELEN = 32
MIDI_IO_STATUS = 0x00000020
MIM_OPEN = 0x3C1
MIM_CLOSE = 0x3C2
MIM_DATA = 0x3C3
MIM_LONGDATA = 0x3C4
MIM_ERROR = 0x3C5
MIM_LONGERROR = 0x3C6


class MIDIINCAPS(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.wintypes.WORD),
        ("wPid", ctypes.wintypes.WORD),
        ("vDriverVersion", ctypes.wintypes.DWORD),
        ("szPname", ctypes.wintypes.WCHAR * MAXPNAMELEN),
        ("dwSupport", ctypes.wintypes.DWORD),
    ]


class HMIDIIN(ctypes.c_void_p):
    pass


class MidiInput(QObject):
    """监听 Windows MIDI 输入设备，收到 NOTE_ON 时发出 note_on 信号。"""

    note_on = Signal(int, int)  # note, velocity

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._handle: Optional[HMIDIIN] = None
        self._callback_type = ctypes.WINFUNCTYPE(
            ctypes.wintypes.DWORD,
            HMIDIIN,
            ctypes.wintypes.UINT,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
        )
        self._callback = self._callback_type(self._midi_in_proc)
        self._winmm = ctypes.windll.winmm

    def available_ports(self) -> list[str]:
        """返回可用 MIDI 输入设备名称列表。"""
        count = self._winmm.midiInGetNumDevs()
        names = []
        for i in range(count):
            caps = MIDIINCAPS()
            if self._winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                names.append(caps.szPname)
        return names

    def open(self, port_index: int = 0) -> bool:
        """打开指定索引的 MIDI 输入设备。"""
        if self._handle is not None:
            return True
        handle = HMIDIIN()
        result = self._winmm.midiInOpen(
            ctypes.byref(handle),
            port_index,
            self._callback,
            0,
            MIDI_IO_STATUS,
        )
        if result != 0:
            return False
        self._handle = handle
        self._winmm.midiInStart(self._handle)
        return True

    def close(self) -> None:
        """关闭 MIDI 输入设备。"""
        if self._handle is None:
            return
        self._winmm.midiInStop(self._handle)
        self._winmm.midiInClose(self._handle)
        self._handle = None

    def _midi_in_proc(
        self,
        hMidiIn: HMIDIIN,
        wMsg: ctypes.wintypes.UINT,
        dwInstance: ctypes.wintypes.DWORD,
        dwParam1: ctypes.wintypes.DWORD,
        dwParam2: ctypes.wintypes.DWORD,
    ) -> ctypes.wintypes.DWORD:
        """Windows MIDI 回调函数。"""
        if wMsg == MIM_DATA:
            status = dwParam1 & 0xFF
            data1 = (dwParam1 >> 8) & 0xFF
            data2 = (dwParam1 >> 16) & 0xFF
            cmd = status & 0xF0
            # NOTE_ON velocity > 0
            if cmd == 0x90 and data2 > 0:
                self.note_on.emit(data1, data2)
        return 0
