"""Un singolo tentativo di click pesca; nessun ciclo di input."""


def click_singolo(api, hwnd, stop, held, read_target, move, wait):
    """read_target verifica finestra, area, rosso e contatore su una cattura nuova."""
    def valid(point):
        return (not stop.is_set() and api.foreground()==hwnd and api.owner(point)==hwnd)
    if stop.is_set():return False,'STOP: tentativo annullato',None,None
    first=read_target()
    if first is None:return False,'Rosso, pesce o contatore non confermati',None,None
    point,baseline=first
    if not valid(point) or api.left_down():return False,'Finestra cambiata o tasto sinistro gia premuto',None,None
    move(*point)
    second=read_target()
    if second is None:return False,'Bersaglio perso dopo il movimento',None,None
    current,count=second
    if count!=baseline:
        return False,'Contatore cambiato prima del click',None,None
    if not valid(current) or api.left_down():
        return False,'Focus cambiato o tasto sinistro gia premuto',None,None
    # Il pesce si muove normalmente: raggiungi la posizione della lettura nuova.
    point=current
    move(*point)
    if not valid(point) or api.left_down():
        return False,'Focus cambiato o tasto sinistro gia premuto',None,None
    try:
        held.value=1
        # Ultimo controllo dopo aver attivato il rilascio di emergenza condiviso.
        if stop.is_set():return False,'STOP: tentativo annullato',None,None
        api.down()
        wait(0.06)
        return True,'Un click inviato; attendo avanzamento contatore',point,baseline
    finally:
        if held.value:
            api.up();held.value=0


class MouseWindows:
    def __init__(self,u):
        import ctypes
        from ctypes import wintypes
        self.u=u;self.point_type=wintypes.POINT
        u.WindowFromPoint.argtypes=[wintypes.POINT];u.WindowFromPoint.restype=wintypes.HWND
        u.GetAncestor.argtypes=[wintypes.HWND,ctypes.c_uint];u.GetAncestor.restype=wintypes.HWND
        u.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int];u.SetCursorPos.restype=wintypes.BOOL
        u.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)];u.GetCursorPos.restype=wintypes.BOOL
        u.GetAsyncKeyState.argtypes=[ctypes.c_int];u.GetAsyncKeyState.restype=ctypes.c_short
    def foreground(self):return self.u.GetForegroundWindow()
    def owner(self,p):return self.u.GetAncestor(self.u.WindowFromPoint(self.point_type(*p)),2)
    def left_down(self):return bool(self.u.GetAsyncKeyState(1)&0x8000)
    def down(self):self.u.mouse_event(0x0002,0,0,0,0)
    def up(self):self.u.mouse_event(0x0004,0,0,0,0)
