#!/usr/bin/env bash
# Instalador do Whisper Fogo para macOS, para quem já tem os arquivos em disco.
#
# O caminho de dois cliques é o aplicativo "Instalar Whisper Fogo", que sai do
# botão de download do README. Este arquivo roda o mesmo instalador a partir de
# uma pasta do repositório, pelo Terminal:
#
#   bash instalador/Instalar-Whisper-Fogo.command

set -euo pipefail
cd "$(dirname "$0")"

# O script vai para o disco antes de rodar, e não direto do cano para o bash:
# assim um download interrompido aparece como erro, em vez de virar um bash
# lendo um cano vazio.
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
