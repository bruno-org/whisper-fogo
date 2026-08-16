"""Atalho global de teclado, por sistema operacional.

O comportamento copiado do Wispr Flow, e que o `RegisterHotKey` do Windows não
alcança: reagir a modificador sozinho, sem tecla comum junto, e reagir à soltura
da tecla. Por isso é hook de baixo nível no Windows e listener global no macOS.

No Windows:

    IDLE    -> segura Ctrl+Shift por SEGURAR_MS ........ grava enquanto segurar
            -> Ctrl+Shift+Espaço ....................... grava de mãos livres
    PTT     -> soltou Ctrl ou Shift .................... encerra e cola
            -> apertou Espaço no meio .................. vira mãos livres
    TRAVADO -> Ctrl+Shift de novo (com ou sem Espaço) .. encerra e cola

No macOS as teclas são as que o Wispr Flow usa lá: a Fn no lugar do par de
modificadores, e o Control no lugar do Alt. A leitura do teclado depende da
permissão de Acessibilidade, e a escuta só nasce depois que ela está valendo.
Ver a seção do README.
"""
import sys
import threading
import time

MAC = sys.platform == "darwin"

SEGURAR_MS = 250        # tempo com Ctrl+Shift parados antes de virar gravação

if not MAC:
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32

    # Teclas iguais às do Wispr Flow, lidas do splitKeybinds dele:
    #   [160, 162]     -> "ptt"  (segurar Shift esq + Ctrl esq)
    #   [160, 162, 32] -> "popo" (Shift esq + Ctrl esq + Espaço, mãos livres)
    VK_LSHIFT, VK_LCONTROL, VK_SPACE = 0xA0, 0xA2, 0x20
    ALT_LIMPEZA = 0xA4  # Alt esq junto inverte o padrão de revisão, nos dois sentidos

    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
    user32.CallNextHookEx.restype = LRESULT


    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]


    class Teclado:
        """Reproduz o comportamento do Wispr Flow, que o RegisterHotKey não alcança:
        ele precisa reagir a modificadores sozinhos e à soltura de tecla.

        IDLE    -> segura Ctrl+Shift por SEGURAR_MS ......... grava enquanto segurar
                -> Ctrl+Shift+Space ........................ grava de mãos livres
        PTT     -> soltou Ctrl ou Shift .................... encerra e cola
                -> apertou Space no meio ................... vira mãos livres
        TRAVADO -> Ctrl+Shift de novo (com ou sem Space) ... encerra e cola
        """

        def __init__(self, app):
            self.app = app
            self.baixo = set()
            self.estado = "IDLE"
            self.cancelado = False       # outra tecla entrou: era atalho comum
            self.timer = None
            self.proc = HOOKPROC(self._callback)

        # o callback do hook tem orçamento de milissegundos: só mexe em flag e sai.
        def _callback(self, ncode, wparam, lparam):
            if ncode == 0:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = info.vkCode
                if wparam in (0x0100, 0x0104):      # WM_KEYDOWN / WM_SYSKEYDOWN
                    if vk not in self.baixo:
                        self.baixo.add(vk)
                        if self._descer(vk):
                            return 1                # engole o Space da combinação
                elif wparam in (0x0101, 0x0105):    # WM_KEYUP / WM_SYSKEYUP
                    self.baixo.discard(vk)
                    self._subir(vk)
            return user32.CallNextHookEx(None, ncode, wparam, lparam)

        @property
        def _modificadores(self):
            return VK_LSHIFT in self.baixo and VK_LCONTROL in self.baixo

        def _descer(self, vk):
            if vk in (VK_LSHIFT, VK_LCONTROL):
                if self._modificadores:
                    if self.estado == "TRAVADO":
                        self._parar()
                        self.estado = "ENCERRANDO"
                    elif self.estado == "IDLE":
                        self.estado = "ARMADO"
                        self.cancelado = False
                        self.timer = threading.Timer(SEGURAR_MS / 1000, self._virar_ptt)
                        self.timer.start()
            elif vk == VK_SPACE and self._modificadores:
                if self.estado in ("ARMADO", "PTT"):
                    self._cancelar_timer()
                    if self.estado == "ARMADO":
                        self.app.fila_cmd.put(("iniciar", ALT_LIMPEZA in self.baixo))
                    self.estado = "TRAVADO"
                    return True                     # bloqueia: senão digita espaço no campo
            elif vk == ALT_LIMPEZA:
                # Alt é modificador auxiliar, nunca cancela o arme (senão
                # Ctrl+Shift+Alt+Space morria antes do Space chegar). Vale a qualquer
                # instante da fala: só dá para saber que o texto merece revisão
                # depois de falar, não antes.
                if self.estado in ("PTT", "TRAVADO"):
                    self.app.alt = True
            elif self.estado == "ARMADO":
                self.cancelado = True               # Ctrl+Shift+outra coisa: atalho normal
                self._cancelar_timer()
                self.estado = "IGNORANDO"
            return False

        def _subir(self, vk):
            if vk in (VK_LSHIFT, VK_LCONTROL):
                if self.estado == "PTT":
                    self._parar()
                    self.estado = "IDLE"
                elif self.estado in ("ARMADO", "IGNORANDO", "ENCERRANDO"):
                    self._cancelar_timer()
                    self.estado = "IDLE"

        def _virar_ptt(self):
            if self.estado == "ARMADO" and not self.cancelado and self._modificadores:
                self.estado = "PTT"
                self.app.fila_cmd.put(("iniciar", ALT_LIMPEZA in self.baixo))

        def _parar(self):
            # também aceita o Alt segurado no momento de encerrar
            self.app.fila_cmd.put(("parar", ALT_LIMPEZA in self.baixo))

        def _cancelar_timer(self):
            if self.timer:
                self.timer.cancel()
                self.timer = None

        def rodar(self):
            h = user32.SetWindowsHookExW(13, self.proc, None, 0)  # WH_KEYBOARD_LL
            if not h:
                print("[erro] hook de teclado recusado", file=sys.stderr)
                return
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))


else:
    # --------------------------------------------------------------- macOS
    def esperar_confianca(intervalo=2.0):
        """Só devolve o controle quando o macOS liberar a leitura do teclado.

        Ler tecla fora da própria janela depende da permissão de Acessibilidade,
        e o sistema responde conforme o estado do momento: marcar a caixa em
        Ajustes muda a resposta na hora, sem precisar abrir o programa de novo.
        A primeira consulta pede a permissão pela janela do próprio macOS, que
        já leva ao painel certo.
        """
        try:
            from ApplicationServices import (AXIsProcessTrusted,
                                             AXIsProcessTrustedWithOptions,
                                             kAXTrustedCheckOptionPrompt)
        except ImportError:
            return

        if AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}):
            return

        print("[o atalho global espera a permissão de Acessibilidade em Ajustes "
              "do Sistema, Privacidade e Segurança]", file=sys.stderr)
        while not AXIsProcessTrusted():
            time.sleep(intervalo)
        print("[permissão de Acessibilidade concedida, atalho no ar]", file=sys.stderr)

    # Teclas do Wispr Flow no macOS, lidas da configuração dele: a Fn sozinha
    # grava enquanto segura, a Fn com espaço grava de mãos livres, e o Control
    # somado à Fn manda o texto para revisão. São os códigos do sistema.
    ESPACO = 49
    MASCARA_FN = 0x800000
    MASCARA_CONTROL = 0x40000

    class Teclado:
        """Mesma máquina de estados, ouvindo o teclado pelo Quartz.

        A Fn não chega como tecla comum: ela vira um sinalizador no evento de
        mudança de modificadores, e é por isso que a escuta acontece nesse nível
        em vez de na camada de teclas.

            IDLE    -> segura Fn por SEGURAR_MS ......... grava enquanto segurar
                    -> Fn + Espaço ..................... grava de mãos livres
            PTT     -> soltou Fn ....................... encerra e cola
                    -> apertou Espaço no meio .......... vira mãos livres
            TRAVADO -> Fn de novo ...................... encerra e cola
        """

        def __init__(self, app):
            self.app = app
            self.estado = "IDLE"
            self.timer = None
            self.alt_pressionado = False
            self.fn_baixa = False
            self.ja_viu_fn = False

        def _evento(self, proxy, tipo, evento, refcon):
            from Quartz import (CGEventGetFlags, CGEventGetIntegerValueField,
                                kCGEventFlagsChanged, kCGKeyboardEventKeycode)
            try:
                flags = CGEventGetFlags(evento)
                if tipo == kCGEventFlagsChanged:
                    fn = bool(flags & MASCARA_FN)
                    if bool(flags & MASCARA_CONTROL) and self.estado in ("PTT", "TRAVADO"):
                        self.app.alt = True          # revisão pedida no meio da fala
                    if fn and not self.fn_baixa:
                        self.fn_baixa = True
                        if not self.ja_viu_fn:      # confirma a escuta, uma vez
                            self.ja_viu_fn = True
                            print("[tecla Fn reconhecida]", file=sys.stderr)
                        self.alt_pressionado = bool(flags & MASCARA_CONTROL)
                        self._fn_desceu()
                    elif not fn and self.fn_baixa:
                        self.fn_baixa = False
                        self._fn_subiu()
                elif self.fn_baixa and CGEventGetIntegerValueField(
                        evento, kCGKeyboardEventKeycode) == ESPACO:
                    self._espaco()
            except Exception as e:
                print(f"[teclado] {type(e).__name__}: {e}", file=sys.stderr)
            return evento

        def _fn_desceu(self):
            if self.estado == "TRAVADO":
                self._parar()
                self.estado = "ENCERRANDO"
            elif self.estado == "IDLE":
                self.estado = "ARMADO"
                self.timer = threading.Timer(SEGURAR_MS / 1000, self._virar_ptt)
                self.timer.start()

        def _fn_subiu(self):
            if self.estado == "PTT":
                self._parar()
                self.estado = "IDLE"
            elif self.estado in ("ARMADO", "ENCERRANDO"):
                self._cancelar_timer()
                self.estado = "IDLE"

        def _espaco(self):
            if self.estado in ("ARMADO", "PTT"):
                self._cancelar_timer()
                if self.estado == "ARMADO":
                    self.app.fila_cmd.put(("iniciar", self.alt_pressionado))
                self.estado = "TRAVADO"

        def _virar_ptt(self):
            if self.estado == "ARMADO" and self.fn_baixa:
                self.estado = "PTT"
                self.app.fila_cmd.put(("iniciar", self.alt_pressionado))

        def _parar(self):
            self.app.fila_cmd.put(("parar", self.alt_pressionado))

        def _cancelar_timer(self):
            if self.timer:
                self.timer.cancel()
                self.timer = None

        def rodar(self):
            from Quartz import (CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
                                CFRunLoopGetCurrent, CFRunLoopRun, CGEventMaskBit,
                                CGEventTapCreate, CGEventTapEnable, kCFRunLoopCommonModes,
                                kCGEventFlagsChanged, kCGEventKeyDown,
                                kCGHeadInsertEventTap, kCGSessionEventTap,
                                kCGEventTapOptionListenOnly)
            # a escuta nasce depois da liberação, senão ela sobe surda
            esperar_confianca()
            tap = CGEventTapCreate(
                kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly,
                CGEventMaskBit(kCGEventFlagsChanged) | CGEventMaskBit(kCGEventKeyDown),
                self._evento, None)
            if not tap:
                print("[erro] não consegui ouvir o teclado", file=sys.stderr)
                return
            fonte = CFMachPortCreateRunLoopSource(None, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), fonte, kCFRunLoopCommonModes)
            CGEventTapEnable(tap, True)
            CFRunLoopRun()
