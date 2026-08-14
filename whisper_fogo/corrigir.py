"""Correção de grafia por substituição literal, antes do texto ser colado.

Hotword enviesa o reconhecedor, mas não garante grafia: mesmo com "Claude Code"
na lista, o modelo às vezes escreve "Cloud Code". Para nome próprio de grafia
fixa, substituição literal acerta sempre e custa zero.

Duas fontes alimentam este módulo:

1. `dicionario.json`, que você edita à mão quando quiser. Nasce vazio.
2. `aprendido.json`, escrito sozinho quando você corrige uma palavra no campo
   depois de ditar. Ver `aprendizado.py`.

As expansões de fala vêm desligadas. Ligue em `dicionario.json` se quiser que
"pra" vire "para" e "tá" vire "está" no texto final.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).parent
DICIONARIO = BASE / "dicionario.json"

# Reduções da fala corrente do português brasileiro. Não é correção de erro do
# reconhecedor, é escolha de estilo: quem dita mensagem de WhatsApp quer "pra",
# quem dita documento quer "para". Por isso vem desligado.
EXPANSOES = [
    (r"\bpra\b", "para"), (r"\bPra\b", "Para"),
    (r"\bpro\b", "para o"), (r"\bPro\b", "Para o"),
    (r"\btá\b", "está"), (r"\bTá\b", "Está"),
    (r"\btava\b", "estava"), (r"\bTava\b", "Estava"),
    (r"\bcê\b", "você"), (r"\bCê\b", "Você"),
]

# Ficaram de fora de propósito, porque o lado errado é palavra corrente e a troca
# estragaria texto legítimo:
#   "tão" -> "estão": "tão bonito" viraria "estão bonito"
#   "tem" -> "têm": depende de o sujeito estar no plural, exige contexto
#   "sessão" -> "seção": as duas existem, só o sentido da frase separa
# Substituição literal não tem contexto de frase. Quando precisar disso, use a
# revisão pelo modelo de texto (Alt durante o ditado).

MODELO_DICIONARIO = {
    "_leia_me": "trocas é o que o reconhecedor escreve e como deve ficar. "
                "expansoes liga as reduções da fala. maiusculas conserta só a caixa.",
    "trocas": {},
    "maiusculas": [],
    "expansoes": False,
}

_cache = None


def _carregar_dicionario():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(DICIONARIO.read_text(encoding="utf-8"))
        except Exception:
            _cache = dict(MODELO_DICIONARIO)
    return _cache


def recarregar():
    """Chame depois de editar o dicionario.json com o app aberto."""
    global _cache
    _cache = None


def corrigir(texto):
    texto = texto.lstrip("﻿")          # BOM de arquivo gravado no Windows
    d = _carregar_dicionario()

    # 1. O que foi aprendido observando você corrigir no campo. Vem primeiro:
    #    correção observada vale mais que regra escrita à mão. Sensível à caixa,
    #    ver aprendizado.carregar().
    try:
        from aprendizado import carregar
        for errado, certo in carregar().items():
            texto = re.sub(rf"\b{re.escape(errado)}\b", certo.replace("\\", r"\\"), texto)
    except Exception:
        pass          # o dicionário aprendido é acessório, nunca derruba o ditado

    # 2. As trocas que você escreveu à mão.
    for errado, certo in (d.get("trocas") or {}).items():
        texto = re.sub(rf"\b{re.escape(errado)}\b", certo, texto)

    # 3. Marcas cuja única falha é a caixa: corrige em qualquer capitalização.
    for marca in (d.get("maiusculas") or []):
        texto = re.sub(re.escape(marca), marca, texto, flags=re.IGNORECASE)

    # 4. Expansões da fala, se você ligou.
    if d.get("expansoes"):
        for padrao, troca in EXPANSOES:
            texto = re.sub(padrao, troca, texto)
    return texto


def _autoteste():
    global _cache
    _cache = {"trocas": {"Cloud Code": "Claude Code", "Kubernets": "Kubernetes"},
              "maiusculas": ["GitHub", "PostgreSQL"], "expansoes": True}

    assert corrigir("eu uso muito o Cloud Code") == "eu uso muito o Claude Code"
    assert corrigir("vendido pela Kubernets") == "vendido pela Kubernetes"
    # a caixa é corrigida em qualquer capitalização
    assert corrigir("commit no github") == "commit no GitHub"
    assert corrigir("banco postgresql aqui") == "banco PostgreSQL aqui"
    # não pode estragar texto que já estava certo
    assert corrigir("o Claude Code e o GitHub") == "o Claude Code e o GitHub"
    # fronteira de palavra: não casa dentro de outra palavra
    _cache["trocas"] = {"verso": "Vercel"}
    assert corrigir("universo inteiro") == "universo inteiro"
    # expansões ligadas
    _cache["trocas"] = {}
    assert corrigir("vou fazer pra você") == "vou fazer para você"
    assert corrigir("Tá bom, tava certo") == "Está bom, estava certo"
    # expansões desligadas não mexem em nada
    _cache["expansoes"] = False
    assert corrigir("vou fazer pra você") == "vou fazer pra você"
    # dicionário vazio devolve o texto intacto
    _cache = {"trocas": {}, "maiusculas": [], "expansoes": False}
    assert corrigir("qualquer frase aqui") == "qualquer frase aqui"
    print("corrigir: 10/10 ok")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stdin":
        # stdin evita mojibake ao passar acento como argumento no PowerShell 5.1,
        # que lê em CP850 enquanto o Python espera UTF-8
        sys.stdout.reconfigure(encoding="utf-8")
        print(corrigir(sys.stdin.buffer.read().decode("utf-8")))
    else:
        _autoteste()
