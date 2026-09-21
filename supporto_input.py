"""Short Windows key presses with independent release and focus/stop checks."""
import ctypes as C
import threading
import time
from supporto_core import normalize_key


class KeyboardInput(C.Structure):
    _fields_=[('vk',C.c_uint16),('scan',C.c_uint16),('flags',C.c_uint32),
              ('time',C.c_uint32),('extra',C.c_size_t)]


class MouseInput(C.Structure):
    _fields_=[('x',C.c_int32),('y',C.c_int32),('data',C.c_uint32),
              ('flags',C.c_uint32),('time',C.c_uint32),('extra',C.c_size_t)]


class InputUnion(C.Union):
    _fields_=[('keyboard',KeyboardInput),('mouse',MouseInput)]


class Input(C.Structure):
    _fields_=[('type',C.c_uint32),('data',InputUnion)]


def virtual_key(key):
    if key in ("CTRL","ALT","SHIFT"):return {"CTRL":0x11,"ALT":0x12,"SHIFT":0x10}[key]
    key=normalize_key(key)
    if "+" in key:raise ValueError("virtual_key richiede un solo tasto.")
    if len(key)==1:return ord(key)
    if key.startswith('NUM'):return 0x60+int(key[3:])
    if key.startswith('F') and key[1:].isdigit():return 0x70+int(key[1:])-1
    return dict(SPACE=0x20,TAB=9,ENTER=13,BACKSPACE=8,INSERT=0x2D,DELETE=0x2E,
                HOME=0x24,END=0x23,PAGEUP=0x21,PAGEDOWN=0x22,
                UP=0x26,DOWN=0x28,LEFT=0x25,RIGHT=0x27)[key]


class WindowsKeyboard:
    def __init__(self,hwnd):
        self.hwnd=hwnd
        self.u=C.WinDLL('user32',use_last_error=True)
        for name in ('IsWindow','IsIconic'):
            fn=getattr(self.u,name);fn.argtypes=[C.c_void_p];fn.restype=C.c_int
        self.u.GetForegroundWindow.restype=C.c_void_p
        self.u.GetAsyncKeyState.argtypes=[C.c_int];self.u.GetAsyncKeyState.restype=C.c_int16
        self.u.MapVirtualKeyW.argtypes=[C.c_uint32,C.c_uint32];self.u.MapVirtualKeyW.restype=C.c_uint32
        self.u.SendInput.argtypes=[C.c_uint32,C.POINTER(Input),C.c_int];self.u.SendInput.restype=C.c_uint32

    def active(self):
        return bool(self.u.IsWindow(self.hwnd) and not self.u.IsIconic(self.hwnd)
                    and self.u.GetForegroundWindow()==self.hwnd)

    def busy(self,key):
        return any(self.u.GetAsyncKeyState(v)&0x8000 for v in
                   tuple(virtual_key(k) for k in normalize_key(key).split("+"))+(0x10,0x11,0x12,0x5B,0x5C))

    def send(self,key,up=False):
        vk=virtual_key(key);scan=self.u.MapVirtualKeyW(vk,0)
        if not scan:raise RuntimeError('Tasto non traducibile da Windows: '+key)
        extended=key in ('INSERT','DELETE','HOME','END','PAGEUP','PAGEDOWN','UP','DOWN','LEFT','RIGHT')
        item=Input();item.type=1
        item.data.keyboard=KeyboardInput(0,scan,8|(2 if up else 0)|(1 if extended else 0),0,0)
        C.set_last_error(0)
        if self.u.SendInput(1,C.byref(item),C.sizeof(Input))!=1:
            raise RuntimeError(f'Windows non ha accettato il tasto {key} (errore {C.get_last_error()}). '
                               'Verifica che MetinHub sia avviato come amministratore, come Metin2.')


class KeySender:
    """Only the worker requests presses; watchdog releases even during capture."""
    def __init__(self,api,stop,clock=time.monotonic,watch=True):
        self.api=api;self.stop=stop;self.clock=clock
        self.held=[];self.deadline=0;self.error=None
        self.lock=threading.Lock();self.closed=threading.Event();self.thread=None
        if watch:
            self.thread=threading.Thread(target=self._watch,daemon=True)
            self.thread.start()

    def press(self,key):
        key=normalize_key(key)
        with self.lock:
            if self.error:raise RuntimeError(self.error)
            if self.closed.is_set() or self.stop.is_set() or self.held or not self.api.active():return False
            if self.api.busy(key):return False
            # Check immediately before keydown; never activate/raise the game window.
            if self.stop.is_set() or not self.api.active():return False
            self.deadline=self.clock()+.06
            try:
                for part in key.split('+'):
                    if self.stop.is_set() or not self.api.active():
                        self._release();return False
                    self.held.append(part)
                    self.api.send(part)
            except Exception:
                self._release()
                raise
            return True

    def _release(self):
        errors=[]
        for key in list(reversed(self.held)):
            try:
                self.api.send(key,up=True)
                self.held.remove(key)
            except Exception as exc:errors.append(str(exc))
        if errors:raise RuntimeError('; '.join(errors))

    def poll(self):
        with self.lock:
            if self.held and (self.stop.is_set() or not self.api.active() or self.clock()>=self.deadline):
                self._release()

    def _watch(self):
        while not self.closed.wait(.01):
            try:self.poll()
            except Exception as exc:
                self.error=str(exc);self.stop.set();return

    def close(self):
        self.closed.set()
        if self.thread:self.thread.join(timeout=.2)
        with self.lock:self._release()
