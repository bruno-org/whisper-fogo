#!/usr/bin/env bash
# Instalador de um clique do Whisper Fogo para macOS.
# Baixe este arquivo e dê dois cliques nele.
#
# Se o macOS recusar por não ser de desenvolvedor identificado, clique com o
# botão direito no arquivo e escolha Abrir, ou rode uma vez:
#   xattr -d com.apple.quarantine "Instalar-Whisper-Fogo.command"

set -euo pipefail
cd "$(dirname "$0")"

# O script vai para o disco antes de rodar, e não direto do cano para o bash.
# No Windows esse encadeamento fazia o antivírus matar o instalador; aqui ele
# não chega a esse ponto, mas separar também deixa o erro de download visível
# em vez de virar um bash lendo um cano vazio.
if [[ -f "instalar.sh" ]]; then
  bash instalar.sh
else
  destino="${TMPDIR:-/tmp}/whisper-fogo-instalar.sh"
  echo "Baixando o instalador..."
  if ! curl -fsSL -o "$destino" https://raw.githubusercontent.com/bruno-org/whisper-fogo/main/instalador/instalar.sh; then
    echo "Não consegui baixar o instalador. Confira a sua conexão com a internet."
    printf "\nPressione Enter para fechar."
    read -r _
    exit 1
  fi
  bash "$destino"
fi

printf "\nPressione Enter para fechar."
read -r _
