#!/usr/bin/env bash
# Instalador do Whisper Fogo para macOS.
#
# ATENCAO, e esta e a informacao mais importante deste arquivo: o Whisper Fogo
# foi construido e testado no Windows. O caminho do macOS existe, foi escrito com
# as APIs certas, mas nunca rodou numa maquina Apple. Trate como beta de verdade.
# Se algo quebrar, abra uma issue: https://github.com/bruno-org/whisper-fogo/issues
#
# Sem acentuacao de proposito, para nao depender do locale do terminal.

set -euo pipefail

DESTINO="$HOME/Library/Application Support/WhisperFogo"
REPO_ZIP="https://github.com/bruno-org/whisper-fogo/archive/refs/heads/main.zip"
MODELO="large-v3-turbo"
GEMMA_REPO="unsloth/gemma-3-4b-it-GGUF"
GEMMA_ARQ="gemma-3-4b-it-Q4_K_M.gguf"

titulo() { printf "\n\033[36m=== %s ===\033[0m\n" "$1"; }
ok()     { printf "  \033[32m[ok]\033[0m %s\n" "$1"; }
aviso()  { printf "  \033[33m[!]\033[0m  %s\n" "$1"; }
erro()   { printf "  \033[31m[X]\033[0m  %s\n" "$1"; }

cat <<'ARTE'

  ####   WHISPER FOGO
  ####   Ditado por voz offline, em portugues do Brasil.
         Instalador para macOS (beta, nunca testado em Mac)

ARTE

# ------------------------------------------------------------------ requisitos
titulo "Conferindo se a sua maquina aguenta"

problemas=0

if [[ "$(uname)" != "Darwin" ]]; then
  erro "Este instalador e do macOS. No Windows use o Instalar-Whisper-Fogo.bat."
  exit 1
fi
ok "macOS $(sw_vers -productVersion)"

arquitetura="$(uname -m)"
if [[ "$arquitetura" == "arm64" ]]; then
  ok "Apple Silicon ($(sysctl -n machdep.cpu.brand_string))"
else
  aviso "Mac Intel. A transcricao roda na CPU e fica bem mais lenta."
fi

ramGB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if (( ramGB >= 8 )); then ok "Memoria RAM: ${ramGB} GB"
else aviso "Voce tem ${ramGB} GB de RAM. O recomendado sao 8 GB."; fi

livreGB=$(df -g "$HOME" | awk 'NR==2 {print $4}')
if (( livreGB >= 10 )); then ok "Espaco livre: ${livreGB} GB"
else erro "Faltam $(( 10 - livreGB )) GB de espaco. A instalacao ocupa cerca de 8 GB."; problemas=1; fi

if ! xcode-select -p >/dev/null 2>&1; then
  aviso "Ferramentas de linha de comando da Apple ausentes. Vou pedir a instalacao."
  xcode-select --install || true
fi

(( problemas == 0 )) || { erro "Corrija os itens acima e rode de novo."; exit 1; }

# ------------------------------------------------------------------- programa
titulo "Instalando o programa"
mkdir -p "$DESTINO"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

origem="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$origem/whisper_fogo/voz.py" ]]; then
  ok "Usando os arquivos do repositorio clonado"
else
  echo "  Baixando o programa..."
  curl -fsSL "$REPO_ZIP" -o "$tmp/repo.zip"
  unzip -q "$tmp/repo.zip" -d "$tmp"
  origem="$(find "$tmp" -maxdepth 1 -type d -name 'whisper-fogo*' | head -1)"
  ok "Programa baixado"
fi
cp -R "$origem/whisper_fogo/." "$DESTINO/"
ok "Arquivos copiados"

# -------------------------------------------------------------------- python
titulo "Preparando o Python"
if ! command -v uv >/dev/null 2>&1; then
  echo "  Instalando o uv (gerenciador de Python)..."
  curl -fsSL https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv pronto"

cd "$DESTINO"
uv venv --python 3.12 .venv
ok "Ambiente Python isolado criado"

echo "  Instalando as bibliotecas (pode levar alguns minutos)..."
uv pip install --python "$DESTINO/.venv/bin/python" \
  faster-whisper sounddevice numpy pystray pillow pynput pyobjc-framework-Quartz
ok "Bibliotecas instaladas"

# -------------------------------------------------------------------- modelos
titulo "Baixando o modelo de transcricao"
echo "  large-v3-turbo, 1,6 GB. So acontece uma vez."
"$DESTINO/.venv/bin/python" - <<PY
from faster_whisper import WhisperModel
WhisperModel("$MODELO", device="cpu", compute_type="int8")
print("modelo pronto")
PY
ok "Modelo de transcricao no lugar"

printf "\n  Instalar tambem a revisao de texto pelo Alt? (S/n) "
read -r resposta
if [[ ! "$resposta" =~ ^[nN] ]]; then
  titulo "Baixando a revisao de texto"
  mkdir -p "$DESTINO/modelos"
  "$DESTINO/.venv/bin/python" - <<PY
from huggingface_hub import hf_hub_download
import shutil
p = hf_hub_download("$GEMMA_REPO", "$GEMMA_ARQ")
shutil.copy(p, "$DESTINO/modelos/$GEMMA_ARQ")
print("gemma pronto")
PY
  ok "Modelo de revisao no lugar"
  aviso "No macOS o motor llama.cpp nao e instalado automaticamente ainda."
  aviso "Instale com: brew install llama.cpp"
fi

# --------------------------------------------------------------- dicionario
[[ -f "$DESTINO/dicionario.json" ]] || cp "$origem/whisper_fogo/dicionario.exemplo.json" "$DESTINO/dicionario.json" 2>/dev/null || true

# --------------------------------------------------------------------- atalho
titulo "Criando o atalho"
APP="$HOME/Applications/Whisper Fogo.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/MacOS/whisper-fogo" <<LANCADOR
#!/bin/bash
exec "$DESTINO/.venv/bin/python" "$DESTINO/voz.py"
LANCADOR
chmod +x "$APP/Contents/MacOS/whisper-fogo"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Whisper Fogo</string>
  <key>CFBundleIdentifier</key><string>ai.whisperfogo.app</string>
  <key>CFBundleExecutable</key><string>whisper-fogo</string>
  <key>CFBundleIconFile</key><string>fogo</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>O Whisper Fogo grava a sua voz para transcrever, sempre na sua maquina.</string>
</dict></plist>
PLIST
cp "$DESTINO/fogo.png" "$APP/Contents/Resources/fogo.png" 2>/dev/null || true
ok "Aplicativo criado em ~/Applications"

# --------------------------------------------------------------------- testes
titulo "Conferindo a instalacao"
for t in corrigir.py aprendizado.py; do
  "$DESTINO/.venv/bin/python" "$DESTINO/$t" | tail -1
done

cat <<'FIM'

  Pronto. Antes do primeiro uso, o macOS vai exigir duas permissoes:

    Ajustes > Privacidade e Seguranca > Microfone ......... marque o Whisper Fogo
    Ajustes > Privacidade e Seguranca > Acessibilidade ... marque o Whisper Fogo

  Sem a segunda, o atalho global nao funciona.

  Como usar:
    Segure Command + Shift ........ fala e solta, o texto cola sozinho
    Command + Shift + Espaco ...... maos livres, a mesma tecla encerra
    Somar Option .................. revisa o texto antes de colar
    Icone na barra de menus ....... abre o historico de ditados

  O aprendizado por correcao no campo ainda nao funciona no macOS: depende da
  API de Acessibilidade da Apple, que nao pude testar. O resto funciona.

FIM
