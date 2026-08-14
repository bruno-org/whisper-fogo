"""Whisper Fogo: ditado por voz offline, no lugar do Wispr Flow.


Fica na bandeja sem consumir GPU. O modelo carrega no primeiro uso e se
descarrega sozinho depois de OCIOSO_MIN minutos, devolvendo a VRAM.

Ctrl+Shift+Space        grava, transcreve, corrige grafia, cola no cursor.
Ctrl+Shift+Alt+Space    idem, mais reescrita pelo Gemma (tira vício de fala,
                        quebra parágrafo). Mais lento, para texto que vai ser lido.

Todo ditado fica salvo no historico.jsonl antes de ir para a área de
transferência. Clicar no ícone da bandeja abre a janela de histórico, para
recuperar o que não colou.
"""
import os
import queue
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

MAC = sys.platform == "darwin"
if not MAC:
    import ctypes
    import ctypes.wintypes as wt
    import winsound

BASE = Path(__file__).parent


def beep(frequencia, ms):
    """Sinal sonoro de início, fim e erro. É o retorno que diz que o microfone
    abriu sem você precisar olhar para a bandeja."""
    try:
        if MAC:
            subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            winsound.Beep(frequencia, ms)
    except Exception:
        pass

def ligar_log():
    """Roda por pythonw, sem console: sem isso todo erro morre em silêncio e não
    há como saber por que o ditado parou de responder. Só no main, senão quem
    importar o módulo perde a própria saída."""
    if sys.stderr is None or not sys.stderr.isatty():
        try:
            log = open(BASE / "voz.log", "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout = log
            print(f"\n=== Whisper Fogo iniciado {time.strftime('%d/%m/%Y %H:%M')} ===")
        except Exception:
            pass

# As DLLs de CUDA moram dentro do venv. PATH do processo, não do Windows.
_bins = [str(p) for _s in ("cublas", "cudnn", "cuda_nvrtc")
         if (p := BASE / ".venv" / "Lib" / "site-packages" / "nvidia" / _s / "bin").is_dir()]
os.environ["PATH"] = os.pathsep.join(_bins + [os.environ["PATH"]])

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(BASE))
import aprendizado
import observador
from clip import colar, escrever as clipboard_escrever, ler as clipboard_ler
from corrigir import corrigir
from historico import registrar
from teclado import Teclado

# ---------------- configuração ----------------
MODELO = "large-v3-turbo"
COMPUTE = "float16"
OCIOSO_MIN = 10           # minutos sem uso até liberar a VRAM
TAXA = 16000              # o Whisper trabalha em 16 kHz mono
# Trava de segurança contra microfone esquecido aberto, e não limite de uso:
# quem está em fluxo fala meia hora seguida. Uma hora de áudio ocupa 230 MB de
# RAM em float32, que qualquer máquina aguenta.
MAX_SEGUNDOS = 3600


def hotwords():
    """Termos que o reconhecedor deve esperar ouvir: o seu vocabulário de
    trabalho, nomes de produto, siglas da sua área.

    Sai de duas fontes, e as duas mudam sem reiniciar o app: a lista `hotwords`
    do `dicionario.json`, que você escreve, e as grafias que o programa aprendeu
    sozinho vendo você corrigir no campo.
    """
    import json
    try:
        d = json.loads((BASE / "dicionario.json").read_text(encoding="utf-8"))
        minhas = d.get("hotwords") or []
    except Exception:
        minhas = []
    return " ".join(list(minhas) + list(aprendizado.carregar().values()))


# Revisão pelo modelo de texto desligada por padrão: o dicionário já resolve o
# essencial sem espera, e a revisão custa alguns segundos por ditado.
REVISAR_SEMPRE = False

if not MAC:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32


# ---------------- bandeja ----------------
# A fogueira é o ícone da marca, mas a bandeja precisa dizer o estado num quadrado
# de 16 px. Solução: a chama apagada (cinza) quando o modelo não está na GPU, acesa
# quando está, mais um ponto de cor no canto durante gravação e processamento.
CORES = {"ocioso": None, "carregado": None,
         "gravando": (220, 60, 60, 255), "processando": (230, 170, 40, 255)}
_cache_icone = {}


def _icone(estado):
    from PIL import Image, ImageDraw, ImageEnhance
    if estado in _cache_icone:
        return _cache_icone[estado]
    L = 64
    try:
        base = Image.open(BASE / "fogo.png").convert("RGBA").resize((L, L), Image.LANCZOS)
    except Exception:
        # ponytail: sem a arte, o app continua de pé com o círculo de antes.
        base = Image.new("RGBA", (L, L), (0, 0, 0, 0))
        ImageDraw.Draw(base).ellipse([8, 8, L - 8, L - 8], fill=(200, 80, 60, 255))
    if estado == "ocioso":                       # brasa apagada: modelo fora da GPU
        base = ImageEnhance.Color(base).enhance(0.0)
        base.putalpha(base.getchannel("A").point(lambda a: int(a * 0.55)))
    if (cor := CORES.get(estado)):
        d = ImageDraw.Draw(base)
        r = L // 4
        d.ellipse([L - r - 2, L - r - 2, L - 2, L - 2], fill=cor,
                  outline=(20, 20, 20, 230), width=2)
    _cache_icone[estado] = base
    return base


class WhisperFogo:
    def __init__(self):
        self.modelo = None
        self.gravando = False
        self.blocos = []
        self.stream = None
        self.ultimo_uso = time.time()
        self.tray = None
        self.fila = queue.Queue()       # áudio pronto -> transcrição
        self.fila_cmd = queue.Queue()   # hook de teclado -> abrir/fechar microfone
        self.alt = False
        self.llm = None
        self.lock = threading.Lock()
        self.timer_corte = None
        self.teclado = None       # preenchido no main, para o corte destravar o atalho
        self.janela = None        # processo da janela de histórico
        # Sinaliza ao observador do ditado anterior que a fala recomeçou: é o
        # "next_dictation_started" do Wispr, que encerra a janela de 60 s.
        self.parar_observacao = threading.Event()

    def executor_comandos(self):
        """Tira do hook de teclado tudo que demora (abrir microfone, parar stream)."""
        while True:
            acao, arg = self.fila_cmd.get()
            try:
                if acao == "iniciar" and not self.gravando:
                    self.alt = bool(arg)
                    self.iniciar()
                elif acao == "parar" and self.gravando:
                    # Alt no início, durante a fala ou no encerramento inverte o
                    # padrão. Com REVISAR_SEMPRE desligado, Alt liga a revisão.
                    alt = self.alt or bool(arg)
                    self.parar(REVISAR_SEMPRE != alt)
            except Exception as e:
                print(f"[erro de comando] {e}", file=sys.stderr)

    # ---------- estado visual ----------
    def estado(self, nome):
        if self.tray:
            self.tray.icon = _icone(nome)
            self.tray.title = f"Whisper Fogo ({nome})"

    # ---------- modelo ----------
    def carregar(self):
        with self.lock:
            if self.modelo is None:
                # Com revisão sempre ligada, os dois modelos sobem em paralelo:
                # em série, o primeiro ditado do dia pagaria os dois carregamentos.
                if REVISAR_SEMPRE:
                    threading.Thread(target=self._subir_llm, daemon=True).start()
                from faster_whisper import WhisperModel
                # Placa NVIDIA quando existir; senão CPU em int8, que é o que
                # roda num Mac ou numa máquina sem GPU. Muito mais lento, mas o
                # programa funciona.
                try:
                    self.modelo = WhisperModel(MODELO, device="cuda", compute_type=COMPUTE)
                except Exception as e:
                    print(f"[sem GPU, indo de CPU] {e}", file=sys.stderr)
                    self.modelo = WhisperModel(MODELO, device="cpu", compute_type="int8")
            self.ultimo_uso = time.time()
            return self.modelo

    def _subir_llm(self):
        try:
            from limpar import subir_servidor
            self.llm = subir_servidor(self.llm)
        except Exception as e:
            print(f"[llm não subiu] {e}", file=sys.stderr)

    def vigia_ocioso(self):
        """Devolve a VRAM quando você para de ditar."""
        while True:
            time.sleep(30)
            with self.lock:
                if self.modelo and time.time() - self.ultimo_uso > OCIOSO_MIN * 60:
                    self.modelo = None
                    if self.llm and self.llm.poll() is None:
                        self.llm.terminate()
                        self.llm = None
                    import gc
                    gc.collect()
                    self.estado("ocioso")

    # ---------- gravação ----------
    def iniciar(self):
        self.blocos = []
        self.parar_observacao.set()          # encerra a observação do ditado anterior

        def captura(dados, frames, tempo, status):
            if self.gravando:
                self.blocos.append(dados.copy())

        # O PortAudio enumera os dispositivos uma vez, ao subir. Sem reinicializar,
        # trocar de microfone (tirar a webcam USB e voltar para o do notebook) só
        # valeria depois de reiniciar o app. Aqui ele relê a cada acionamento e
        # sempre usa o microfone que estiver como padrão no Windows naquele momento.
        try:
            sd._terminate()
            sd._initialize()
            self.stream = sd.InputStream(samplerate=TAXA, channels=1, dtype="float32",
                                         callback=captura, blocksize=1600)
            self.stream.start()
        except Exception as e:
            print(f"[erro de microfone] {e}", file=sys.stderr)
            beep(300, 250)
            self.stream = None
            return

        self.gravando = True
        self.estado("gravando")
        beep(880, 80)
        # Sem cancelar o timer do ditado anterior, ele continua armado e derruba
        # a gravação seguinte no meio da fala, num tempo aleatório. Era esta a
        # causa do ditado "travar" sozinho aos 20 ou 30 segundos.
        self._cancelar_corte()
        self.timer_corte = threading.Timer(MAX_SEGUNDOS, self._corte_seguranca)
        self.timer_corte.start()

    def _cancelar_corte(self):
        if self.timer_corte:
            self.timer_corte.cancel()
            self.timer_corte = None

    def _corte_seguranca(self):
        if self.gravando:
            print(f"[corte de segurança: {MAX_SEGUNDOS}s de gravação]", file=sys.stderr)
            # Pela fila, para que só uma thread mexa no microfone. Direto daqui,
            # o corte competia com o hook de teclado pelo mesmo stream.
            self.fila_cmd.put(("parar", False))
            if self.teclado:
                self.teclado.estado = "IDLE"   # senão o próximo atalho só destrava

    def parar(self, limpar_com_llm):
        self.gravando = False
        self._cancelar_corte()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        beep(660, 80)
        self.estado("processando")
        # O áudio vai junto na fila: se você acionar o próximo ditado antes de
        # este ser transcrito, o iniciar() zera self.blocos e o ditado sumiria.
        self.fila.put((self.blocos, limpar_com_llm))
        self.blocos = []

    # ---------- processamento ----------
    def trabalhador(self):
        while True:
            blocos, limpar_com_llm = self.fila.get()
            try:
                self.processar(blocos, limpar_com_llm)
            except Exception as e:
                print(f"[erro] {e}", file=sys.stderr)
                beep(300, 250)
            finally:
                self.estado("carregado" if self.modelo else "ocioso")

    def processar(self, blocos, limpar_com_llm):
        if not blocos:
            return
        audio = np.concatenate(blocos, axis=0).flatten()
        if len(audio) < TAXA * 0.4:      # menos de 0,4 s: acionamento sem querer
            return

        t0 = time.perf_counter()
        try:
            m = self.carregar()
            # As grafias aprendidas entram como hotword, igual ao "primed
            # dictionary context" do Wispr: melhor o ASR já acertar do que
            # depender da substituição depois.
            segs, _ = m.transcribe(
                audio, language="pt", beam_size=5, vad_filter=True,
                hotwords=hotwords(),
                # Alimentar o próprio texto de volta faz o Whisper entrar em loop
                # de repetição em fala longa, e aí a transcrição nunca termina. É
                # por isso que o padrão do faster-whisper é desligado.
                condition_on_previous_text=False)
            texto = corrigir(" ".join(s.text.strip() for s in segs))
        except Exception:
            self._salvar_audio(audio)    # falhou a transcrição, o áudio não se perde
            raise
        print(f"[{time.perf_counter() - t0:.2f}s para {len(audio) / TAXA:.1f}s de áudio]",
              file=sys.stderr)
        if not texto:
            return
        if limpar_com_llm:
            texto = self.limpar(texto)

        # Registra ANTES de colar: se não houver campo focado, a colagem cai no
        # vazio, mas o ditado continua recuperável pela janela de histórico.
        try:
            registrar(texto, limpar_com_llm)
        except Exception as e:
            print(f"[histórico não gravou] {e}", file=sys.stderr)

        antigo = clipboard_ler()
        clipboard_escrever(texto)
        time.sleep(0.05)
        colar()
        if antigo is not None:
            # Texto longo demora a entrar no campo de destino; devolver a área de
            # transferência cedo demais colava pela metade.
            threading.Timer(2.5, lambda: clipboard_escrever(antigo)).start()
        self.observar_correcao(texto)

    # ---------- aprendizado pela correção no campo ----------
    def observar_correcao(self, colado):
        """Fica 60 s olhando o campo. Se você corrigir uma palavra ali, vira
        regra de grafia. Espelha o Auto-add to Dictionary do Wispr Flow."""
        self.parar_observacao = threading.Event()
        observador.observar_em_thread(colado, lambda final, motivo:
                                      self._aprender(colado, final, motivo),
                                      self.parar_observacao)

    def _aprender(self, colado, final, motivo):
        try:
            pares = aprendizado.extrair_pares(colado, final)
            novos = aprendizado.registrar(pares)
            if pares:
                print(f"[correção observada: {len(pares)} palavra(s), fim por {motivo}]",
                      file=sys.stderr)
            if novos:
                print(f"[aprendido: {novos}]", file=sys.stderr)
                pythonw = BASE / ".venv" / "Scripts" / "pythonw.exe"
                subprocess.Popen([str(pythonw), str(BASE / "aviso.py")]
                                 + [f"{v}>{n}" for v, n in novos])
        except Exception as e:
            print(f"[aprendizado falhou] {e}", file=sys.stderr)

    def _salvar_audio(self, audio):
        caminho = BASE / f"falha-{time.strftime('%Y%m%d-%H%M%S')}.wav"
        with wave.open(str(caminho), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(TAXA)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        print(f"[áudio guardado em {caminho.name}]", file=sys.stderr)

    def abrir_historico(self):
        if self.janela and self.janela.poll() is None:
            return                       # já está aberta, não empilha janela
        pythonw = BASE / ".venv" / "Scripts" / "pythonw.exe"
        self.janela = subprocess.Popen([str(pythonw), str(BASE / "historico.py")])

    # ---------- reescrita opcional ----------
    def limpar(self, texto):
        from limpar import limpar as reescrever, subir_servidor
        self.llm = subir_servidor(self.llm)
        try:
            saida, _ = reescrever(texto)
            return saida
        except Exception:
            return texto  # LLM falhou: entrega a transcrição crua, não perde o ditado



def instancia_unica():
    """Segunda instância perde a disputa pelo atalho global e fica muda, sem
    avisar. Melhor sair na hora do que virar bug silencioso."""
    if not MAC:
        kernel32.CreateMutexW(None, False, "WhisperFogo_instancia_unica")
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    # macOS: arquivo de trava com o PID dentro. Se o processo antigo morreu sem
    # limpar, o arquivo fica órfão e a checagem de PID libera a vez.
    trava = BASE / "instancia.lock"
    try:
        antigo = int(trava.read_text())
        os.kill(antigo, 0)          # não mata, só pergunta se está vivo
        return False
    except Exception:
        pass
    try:
        trava.write_text(str(os.getpid()))
    except Exception:
        pass
    return True


def main():
    import pystray
    ligar_log()
    if not instancia_unica():
        print("Whisper Fogo já está rodando.", file=sys.stderr)
        return
    app = WhisperFogo()
    app.teclado = Teclado(app)
    threading.Thread(target=app.trabalhador, daemon=True).start()
    threading.Thread(target=app.executor_comandos, daemon=True).start()
    threading.Thread(target=app.vigia_ocioso, daemon=True).start()
    threading.Thread(target=app.teclado.rodar, daemon=True).start()

    menu = pystray.Menu(
        pystray.MenuItem("Histórico de ditados", lambda: app.abrir_historico(),
                         default=True),
        pystray.MenuItem("Segurar Ctrl+Shift: ditar enquanto segura", None, enabled=False),
        pystray.MenuItem("Ctrl+Shift+Space: ditar de mãos livres", None, enabled=False),
        pystray.MenuItem("Encerrar mãos livres: Ctrl+Shift", None, enabled=False),
        pystray.MenuItem("Somar Alt: revisar com o Gemma", None, enabled=False),
        pystray.MenuItem("Liberar a GPU agora", lambda: setattr(app, "modelo", None)),
        pystray.MenuItem("Sair", lambda ic: ic.stop()),
    )
    app.tray = pystray.Icon("Whisper Fogo", _icone("ocioso"),
                            "Whisper Fogo (ocioso)", menu)
    app.tray.run()


if __name__ == "__main__":
    main()
