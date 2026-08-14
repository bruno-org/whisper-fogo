"""Área de transferência e colagem, por sistema operacional.

Mora fora do voz.py porque a janela de histórico roda em outro processo e precisa
das mesmas funções, sem arrastar numpy, sounddevice e o Whisper junto.

Windows é o caminho testado, feito com ctypes puro, sem dependência nenhuma.
macOS usa `pbcopy` e `pbpaste`, com a colagem pelo `pynput`. 🔴 O caminho do
macOS foi escrito sem uma máquina Apple para testar. Ver a seção do README.
"""
import subprocess
import sys
import time

MAC = sys.platform == "darwin"

if MAC:
    # ------------------------------------------------------------- macOS
    def ler():
        """O que estava na área de transferência, para devolver depois de colar."""
        try:
            r = subprocess.run(["pbpaste"], capture_output=True, timeout=2)
            return r.stdout.decode("utf-8", "replace") or None
        except Exception:
            return None

    def escrever(texto):
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(texto.encode("utf-8"), timeout=5)
            return p.returncode == 0
        except Exception:
            return False

    def colar():
        from pynput.keyboard import Controller, Key
        teclado = Controller()
        with teclado.pressed(Key.cmd):
            teclado.press("v")
            teclado.release("v")

else:
    # ----------------------------------------------------------- Windows
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Sem declarar os tipos, o ctypes trunca handle de 64 bits para int de 32 e a
    # escrita na área de transferência estoura com access violation.
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    CF_UNICODETEXT = 13

    def _abrir(tentativas=5):
        """Outro programa pode estar com a área de transferência aberta no exato
        instante da colagem. Com uma tentativa só, o ditado ia embora."""
        for _ in range(tentativas):
            if user32.OpenClipboard(None):
                return True
            time.sleep(0.05)
        return False

    def ler():
        """O que estava na área de transferência, para devolver depois de colar."""
        if not _abrir():
            return None
        try:
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            p = kernel32.GlobalLock(h)
            try:
                return ctypes.c_wchar_p(p).value
            finally:
                kernel32.GlobalUnlock(h)
        finally:
            user32.CloseClipboard()

    def escrever(texto):
        if not _abrir():
            return False
        try:
            user32.EmptyClipboard()
            buf = ctypes.create_unicode_buffer(texto)
            tam = ctypes.sizeof(buf)
            h = kernel32.GlobalAlloc(0x0002, tam)  # GMEM_MOVEABLE
            p = kernel32.GlobalLock(h)
            ctypes.memmove(p, buf, tam)
            kernel32.GlobalUnlock(h)
            user32.SetClipboardData(CF_UNICODETEXT, h)
            return True
        finally:
            user32.CloseClipboard()

    def colar():
        # ponytail: keybd_event é antigo, mas resolve em 4 linhas o que o
        # SendInput faria em 30.
        for tecla, up in ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)):  # Ctrl, V
            user32.keybd_event(tecla, 0, up, 0)
            time.sleep(0.01)


def _autoteste():
    original = ler()
    marca = "whisper-fogo-teste-da-area-de-transferencia"
    assert escrever(marca), "não consegui escrever na área de transferência"
    assert ler() == marca, "o que voltou é diferente do que foi escrito"
    # texto com acento e quebra de linha, que é o caso real de um ditado
    complexo = "coração\nàs três, não é?"
    assert escrever(complexo) and ler() == complexo, "acento ou quebra de linha se perdeu"
    if original is not None:
        escrever(original)          # devolve o que a pessoa tinha copiado
    print("clip: 3/3 ok")


if __name__ == "__main__":
    _autoteste()
