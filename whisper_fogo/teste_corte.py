"""Prova que o ditado não é mais cortado sozinho no meio da fala.

O bug: cada gravação armava um threading.Timer de corte e nunca o cancelava.
Um ditado curto deixava a bomba armada, e ela derrubava a gravação seguinte num
tempo aleatório, que era o "travou aos 20 ou 30 segundos".

Roda sem microfone e sem GPU: o InputStream é falso e o modelo nunca é chamado.
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import voz


class StreamFalso:
    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


def preparar():
    voz.winsound.Beep = lambda *a: None       # teste silencioso
    # Só o InputStream é falso. Trocar o _terminate do sounddevice deixaria o
    # PortAudio sem encerrar e o processo do teste travava na saída, sem que o
    # app real tivesse problema nenhum.
    voz.sd.InputStream = lambda **kw: StreamFalso()
    app = voz.WhisperFogo()
    threading.Thread(target=app.executor_comandos, daemon=True).start()
    return app


def teste_timer_antigo_nao_derruba_o_ditado_seguinte():
    app = preparar()
    voz.MAX_SEGUNDOS = 0.5                    # ditado curto, teto curto
    app.iniciar()
    app.parar(False)
    voz.MAX_SEGUNDOS = 60                     # o próximo ditado tem teto folgado
    app.iniciar()
    time.sleep(1.5)                           # bem além do teto do ditado anterior
    assert app.gravando, "o timer do ditado anterior derrubou a gravação seguinte"
    app.parar(False)


def teste_corte_de_seguranca_ainda_funciona():
    app = preparar()
    voz.MAX_SEGUNDOS = 0.5
    app.teclado = type("T", (), {"estado": "TRAVADO"})()
    app.iniciar()
    time.sleep(1.5)
    assert not app.gravando, "o corte de segurança parou de agir"
    assert app.teclado.estado == "IDLE", "o atalho ficaria travado depois do corte"


def teste_audio_nao_some_quando_o_proximo_ditado_comeca():
    app = preparar()
    voz.MAX_SEGUNDOS = 60
    app.iniciar()
    app.blocos = ["áudio do primeiro ditado"]
    app.parar(False)
    app.iniciar()                             # zera self.blocos
    blocos, _ = app.fila.get_nowait()
    assert blocos == ["áudio do primeiro ditado"], "o ditado anterior foi perdido"
    app.parar(False)


if __name__ == "__main__":
    teste_timer_antigo_nao_derruba_o_ditado_seguinte()
    teste_corte_de_seguranca_ainda_funciona()
    teste_audio_nao_some_quando_o_proximo_ditado_comeca()
    print("teste_corte: 3/3 ok")
