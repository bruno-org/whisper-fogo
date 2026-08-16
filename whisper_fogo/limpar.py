"""Reescrita opcional pelo Gemma 3 4B: tira vício de fala e quebra parágrafo.

O servidor sobe sob demanda e morre junto com o modelo do Whisper quando o
Whisper Fogo fica ocioso, para não segurar VRAM parado.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
MAC = sys.platform == "darwin"
EXE = BASE / "llama" / ("llama-server" if MAC else "llama-server.exe")
MODELO = BASE / "modelos" / "gemma-3-4b-it-Q4_K_M.gguf"
PORTA = 8082
URL = f"http://127.0.0.1:{PORTA}/v1/chat/completions"

REGRAS = """Você recebe uma transcrição de voz em português do Brasil e devolve o mesmo texto pronto para uso.

Faça:
- Escreva a forma plena no lugar da reduzida: "pra" vira "para", "pro" vira "para o",
  "tá" vira "está", "tava" vira "estava", "tão" vira "estão", "cê" vira "você".
- Remova hesitação e vício de fala: "né", "então" no início de frase, "tipo", "ah", "éh", "assim".
- Remova "E aí" quando abre a frase sem acrescentar sentido.
- Remova repetição de palavra causada por gagueira ou correção no meio da fala.
- Pontue corretamente e quebre em parágrafos quando o assunto mudar.
- Corrija concordância e acentuação, inclusive "tem" no plural, que vira "têm".

Nunca faça:
- Nunca resuma, encurte ou remova informação.
- Nunca acrescente informação, opinião ou frase que a pessoa não disse.
- Nunca amenize palavrão nem troque a escolha de palavras: a gramática vira culta,
  o vocabulário e o tom continuam sendo os dele.
- Nunca use travessão (nem em-dash, nem "--"). Use vírgula, ponto, dois-pontos ou parênteses.
- Nunca comente o que você fez.

Responda apenas com o texto final."""


def _no_ar():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/health", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def subir_servidor(proc=None, espera=60):
    """Sobe o llama-server se ainda não estiver de pé. Devolve o processo."""
    if _no_ar():
        return proc
    env = dict(os.environ)
    # o llama.cpp precisa das DLLs de cublas, que já vieram no venv
    nv = BASE / ".venv" / "Lib" / "site-packages" / "nvidia"
    extras = [str(nv / s / "bin") for s in ("cublas", "cudnn", "cuda_nvrtc")
              if (nv / s / "bin").is_dir()]
    env["PATH"] = os.pathsep.join(extras + [env["PATH"]])
    # CREATE_NO_WINDOW existe só no Windows, e é lá que evita a janela preta
    # piscando. No macOS o processo já sobe sem janela nenhuma.
    janela = {} if MAC else {"creationflags": 0x08000000}
    proc = subprocess.Popen(
        [str(EXE), "-m", str(MODELO), "-ngl", "99", "-c", "4096",
         "--host", "127.0.0.1", "--port", str(PORTA), "-t", "6", "--no-mmap"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **janela)
    limite = time.time() + espera
    while time.time() < limite:
        if _no_ar():
            return proc
        time.sleep(0.5)
    raise RuntimeError("llama-server não subiu a tempo")


def limpar(texto, timeout=120):
    corpo = json.dumps({
        "messages": [{"role": "system", "content": REGRAS},
                     {"role": "user", "content": texto}],
        "temperature": 0.2,  # baixa: a tarefa é reescrever, não criar
        "max_tokens": 2048,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=corpo,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resposta = json.loads(r.read())
    saida = resposta["choices"][0]["message"]["content"].strip()
    # guarda contra o modelo desobedecer à regra de travessão
    saida = saida.replace(" — ", ", ").replace("—", ",").replace("–", "-")
    return saida, time.perf_counter() - t0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    entrada = sys.stdin.buffer.read().decode("utf-8").lstrip("﻿")
    p = subir_servidor()
    saida, segundos = limpar(entrada)
    print(saida)
    print(f"\n[limpeza: {segundos:.2f}s]", file=sys.stderr)
