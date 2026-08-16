#!/usr/bin/env python3
"""Monta o anexo de instalação do macOS.

Produz `dist/Instalar-Whisper-Fogo.zip`, contendo o aplicativo
"Instalar Whisper Fogo.app". O aplicativo é o formato que o Finder abre com
dois cliques, e o zip é o que transporta o bit de execução do arquivo interno
do pacote, que o macOS exige para lançar o aplicativo.

Roda em qualquer sistema, sem dependência externa:

    python instalador/empacotar-macos.py
"""

import stat
import sys
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = "Instalar Whisper Fogo.app"
SAIDA = RAIZ / "dist" / "Instalar-Whisper-Fogo.zip"

# Cada item é (caminho dentro do zip, arquivo de origem, permissão).
CONTEUDO = [
    (f"{APP}/Contents/Info.plist", RAIZ / "instalador/macos/Info.plist", 0o644),
    (f"{APP}/Contents/MacOS/instalar", RAIZ / "instalador/macos/instalar", 0o755),
    (f"{APP}/Contents/Resources/fogo.icns", RAIZ / "whisper_fogo/fogo.icns", 0o644),
]


def empacotar() -> Path:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    agora = time.localtime()[:6]

    with zipfile.ZipFile(SAIDA, "w", zipfile.ZIP_DEFLATED) as zip_final:
        for nome, origem, permissao in CONTEUDO:
            if not origem.exists():
                raise SystemExit(f"[X] Falta o arquivo de origem: {origem}")

            dados = origem.read_bytes()
            # O shell do macOS trata o retorno de carro como parte do comando,
            # então o executável do pacote viaja com quebra de linha do Unix.
            if permissao == 0o755:
                dados = dados.replace(b"\r\n", b"\n")

            item = zipfile.ZipInfo(nome, date_time=agora)
            item.create_system = 3  # Unix, para o macOS ler a permissão abaixo
            item.external_attr = (stat.S_IFREG | permissao) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            zip_final.writestr(item, dados)

    return SAIDA


if __name__ == "__main__":
    caminho = empacotar()
    tamanho = caminho.stat().st_size
    print(f"[ok] {caminho.relative_to(RAIZ)} ({tamanho / 1024:.0f} KB)")
    for nome, _, permissao in CONTEUDO:
        print(f"     {oct(permissao)[2:]}  {nome}")
    sys.exit(0)
