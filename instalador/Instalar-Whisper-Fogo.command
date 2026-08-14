#!/usr/bin/env bash
# Instalador de um clique do Whisper Fogo para macOS.
# Baixe este arquivo e de dois cliques nele.
#
# Se o macOS recusar por nao ser de desenvolvedor identificado, clique com o
# botao direito no arquivo e escolha Abrir, ou rode uma vez:
#   xattr -d com.apple.quarantine "Instalar-Whisper-Fogo.command"

set -euo pipefail
cd "$(dirname "$0")"

if [[ -f "instalar.sh" ]]; then
  bash instalar.sh
else
  curl -fsSL https://raw.githubusercontent.com/bruno-org/whisper-fogo/main/instalador/instalar.sh | bash
fi

printf "\nPressione Enter para fechar."
read -r _
