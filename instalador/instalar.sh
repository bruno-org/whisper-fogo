#!/usr/bin/env bash
# Instalador do Whisper Fogo para macOS.
#
# Instala um aplicativo só, em ~/Applications, com o interpretador, as
# bibliotecas, o código e os modelos dentro dele. O macOS então pede microfone e
# acessibilidade uma vez, em nome do Whisper Fogo.
#
# Se algo quebrar, abra uma issue: https://github.com/bruno-org/whisper-fogo/issues
#

set -euo pipefail

# Cada janela do macOS monta o PATH de um jeito, e o Homebrew muda de lugar entre
# Apple Silicon e Intel. Os três caminhos onde as ferramentas costumam morar
# entram desde já, para que o que já está na máquina seja reaproveitado.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# O interpretador, as bibliotecas e o código moram dentro do próprio aplicativo.
# É o que faz o macOS identificar um programa só, com o nome e o ícone do
# Whisper Fogo, na hora de pedir microfone e acessibilidade.
APP="$HOME/Applications/Whisper Fogo.app"
RECURSOS="$APP/Contents/Resources"
DESTINO="$RECURSOS/app"
VENV="$RECURSOS/venv"
PYTHON="$VENV/bin/python"
# O aplicativo é assinado, e aplicativo assinado não muda depois de instalado.
# O que nasce durante o uso, como o histórico e os modelos, mora na pasta de
# dados que o macOS reserva para cada programa.
DADOS="$HOME/Library/Application Support/WhisperFogo"
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
  ####   Transcrição de voz offline, especializada no português brasileiro.
         Instalador para macOS

ARTE

# ------------------------------------------------------------------ requisitos
titulo "Conferindo se a sua máquina aguenta"

problemas=0

if [[ "$(uname)" != "Darwin" ]]; then
  erro "Este instalador é do macOS. No Windows use o Instalar-Whisper-Fogo.bat."
  exit 1
fi
ok "macOS $(sw_vers -productVersion)"

arquitetura="$(uname -m)"
if [[ "$arquitetura" == "arm64" ]]; then
  ok "Apple Silicon ($(sysctl -n machdep.cpu.brand_string))"
else
  aviso "Mac Intel. A transcrição roda na CPU e fica bem mais lenta."
fi

ramGB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if (( ramGB >= 8 )); then ok "Memória RAM: ${ramGB} GB"
else aviso "Você tem ${ramGB} GB de RAM. O recomendado são 8 GB."; fi

livreGB=$(df -g "$HOME" | awk 'NR==2 {print $4}')
if (( livreGB >= 10 )); then ok "Espaço livre: ${livreGB} GB"
else erro "Faltam $(( 10 - livreGB )) GB de espaço. A instalação ocupa cerca de 8 GB."; problemas=1; fi

# Tudo o que a instalação usa vem no macOS de fábrica (curl, tar, unzip) ou é
# binário pronto para esta arquitetura: o Python isolado do uv e as bibliotecas
# em formato wheel. Nada é compilado na sua máquina.
for ferramenta in curl tar unzip; do
  command -v "$ferramenta" >/dev/null 2>&1 || { erro "Falta o comando $ferramenta."; problemas=1; }
done

if ! curl -fsS --head --max-time 20 https://github.com >/dev/null 2>&1; then
  erro "Não consegui falar com a internet. Confira a sua conexão e rode de novo."
  problemas=1
fi
ok "Conexão com a internet"

(( problemas == 0 )) || { erro "Corrija os itens acima e rode de novo."; exit 1; }

# ------------------------------------------------------------------- programa
titulo "Instalando o programa"
mkdir -p "$DESTINO" "$APP/Contents/MacOS" "$RECURSOS" "$DADOS"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

origem="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$origem/whisper_fogo/voz.py" ]]; then
  ok "Usando os arquivos do repositório clonado"
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
  # Mesma lógica do arquivo de um clique: baixa, confere, depois roda.
  curl -fsSL -o "$tmp/instalar-uv.sh" https://astral.sh/uv/install.sh
  sh "$tmp/instalar-uv.sh"
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv pronto"

# O interpretador vem para dentro do aplicativo como arquivo, e não como atalho
# para uma pasta de fora. O macOS resolve o atalho até o arquivo verdadeiro
# quando decide de quem é o pedido de permissão, e é o arquivo verdadeiro que
# ele mostra na lista de Ajustes.
rm -rf "$VENV" "$RECURSOS/python"
uv venv --python 3.12 "$tmp/venv-base" >/dev/null
raiz_python="$("$tmp/venv-base/bin/python" -c \
  'import os, sys; print(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))))')"
cp -R "$raiz_python" "$RECURSOS/python"
ok "Python embarcado no aplicativo ($(du -sh "$RECURSOS/python" | cut -f1))"

uv venv --python "$RECURSOS/python/bin/python3.12" "$VENV" >/dev/null
ok "Ambiente Python isolado criado"

echo "  Instalando as bibliotecas (pode levar alguns minutos)..."
uv pip install --python "$PYTHON" \
  faster-whisper sounddevice numpy pystray pillow pynput pyobjc-framework-Quartz
ok "Bibliotecas instaladas"

# -------------------------------------------------------------------- modelos
titulo "Baixando o modelo de transcrição"
echo "  large-v3-turbo, 1,6 GB. Só acontece uma vez."
"$PYTHON" - <<PY
from faster_whisper import WhisperModel
WhisperModel("$MODELO", device="cpu", compute_type="int8")
print("modelo pronto")
PY
ok "Modelo de transcrição no lugar"

printf "\n  Instalar também a revisão de texto pelo Control? (S/n) "
read -r resposta || resposta="n"
if [[ ! "$resposta" =~ ^[nN] ]]; then
  titulo "Baixando a revisão de texto"
  mkdir -p "$DADOS/modelos"
  "$PYTHON" - <<PY
from huggingface_hub import hf_hub_download
import shutil
p = hf_hub_download("$GEMMA_REPO", "$GEMMA_ARQ")
shutil.copy(p, "$DADOS/modelos/$GEMMA_ARQ")
print("gemma pronto")
PY
  ok "Modelo de revisão no lugar"

  # O motor que roda o modelo vem pronto das versões oficiais do llama.cpp, na
  # variante da arquitetura desta máquina, com aceleração por Metal.
  echo "  Baixando o motor de revisão..."
  variante="macos-arm64"
  [[ "$arquitetura" == "arm64" ]] || variante="macos-x64"
  url_motor="$("$PYTHON" - "$variante" <<'PY'
import json, sys, urllib.request
variante = sys.argv[1]
api = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
try:
    with urllib.request.urlopen(api, timeout=30) as resposta:
        dados = json.load(resposta)
    for anexo in dados.get("assets", []):
        if variante in anexo["name"] and anexo["name"].endswith(".tar.gz"):
            print(anexo["browser_download_url"])
            break
except Exception:
    pass
PY
)"
  if [[ -n "$url_motor" ]] && curl -fsSL -o "$tmp/motor.tar.gz" "$url_motor"; then
    mkdir -p "$DADOS/llama"
    tar -xzf "$tmp/motor.tar.gz" -C "$DADOS/llama" --strip-components=1
    chmod +x "$DADOS/llama/llama-server"
    ok "Motor de revisão instalado"
  else
    aviso "Não consegui baixar o motor de revisão. O ditado funciona; a revisão fica de fora."
  fi
fi

# --------------------------------------------------------------- dicionario
[[ -f "$DADOS/dicionario.json" ]] || cp "$origem/whisper_fogo/dicionario.exemplo.json" "$DADOS/dicionario.json" 2>/dev/null || true

# ----------------------------------------------------------------- aplicativo
titulo "Finalizando o aplicativo"
# O executável do pacote é o próprio interpretador. É assim que o macOS trata
# tudo como um programa só: a lista de Ajustes mostra uma linha, com o nome e o
# ícone do Whisper Fogo, em vez do interpretador que roda por baixo.
cp "$RECURSOS/python/bin/python3.12" "$APP/Contents/MacOS/whisper-fogo"
chmod +x "$APP/Contents/MacOS/whisper-fogo"

# O interpretador do pacote enxerga as bibliotecas por estas duas peças, e o
# ponto de entrada abre o programa quando o Finder lança o aplicativo.
cat > "$APP/Contents/pyvenv.cfg" <<CFG
home = $RECURSOS/python/bin
include-system-site-packages = false
version = $("$PYTHON" -c 'import platform; print(platform.python_version())')
CFG
ln -sfn "$RECURSOS/venv/lib" "$APP/Contents/lib"
cp "$origem/instalador/macos/sitecustomize.py" \
   "$VENV/lib/python3.12/site-packages/sitecustomize.py"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Whisper Fogo</string>
  <key>CFBundleIdentifier</key><string>ai.whisperfogo.app</string>
  <key>CFBundleExecutable</key><string>whisper-fogo</string>
  <key>CFBundleIconFile</key><string>fogo</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>O Whisper Fogo grava a sua voz para transcrever, sempre na sua máquina.</string>
</dict></plist>
PLIST
cp "$DESTINO/fogo.icns" "$RECURSOS/fogo.icns" 2>/dev/null || true
ok "Aplicativo criado em ~/Applications"

# --------------------------------------------------------------------- testes
titulo "Conferindo a instalação"
# A conferência é informativa: o programa já está instalado neste ponto, e o
# resultado de cada suíte aparece na tela sem interromper o restante.
export PYTHONDONTWRITEBYTECODE=1
for t in corrigir.py aprendizado.py tema.py; do
  "$PYTHON" "$DESTINO/$t" 2>&1 | tail -1 || true
done
# o historico.py abre a janela quando chamado sem argumento, por isso o --teste
"$PYTHON" "$DESTINO/historico.py" --teste 2>&1 | tail -1 || true

# A assinatura local dá identidade ao pacote, e é por ela que o macOS mostra o
# nome e o ícone do Whisper Fogo ao pedir microfone e acessibilidade, em vez do
# caminho de um arquivo solto. O codesign vem no macOS de fábrica, e a
# assinatura é a última etapa porque vale a partir do que está no pacote agora.
# O Python guarda uma versão compilada de cada módulo na primeira vez que o usa.
# Deixar essa etapa pronta agora é o que mantém o pacote igual ao que foi
# assinado, em vez de ele mudar sozinho durante o primeiro uso.
echo "  Preparando os módulos..."
"$PYTHON" -m compileall -q "$RECURSOS/python/lib" "$VENV/lib" "$DESTINO" >/dev/null 2>&1 || true
codesign --force --deep --sign - "$APP" >/dev/null 2>&1   && ok "Aplicativo assinado"   || aviso "Não consegui assinar o aplicativo. Ele funciona, e o pedido de permissão é que fica com o nome do arquivo."

# ------------------------------------------------------------------ na conta
titulo "Deixando o Whisper Fogo pronto"

# Abre junto com o Mac, como qualquer programa que vive na barra de menus.
mkdir -p "$HOME/Library/LaunchAgents"
AGENTE="$HOME/Library/LaunchAgents/ai.whisperfogo.app.plist"
cat > "$AGENTE" <<AGENT
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>ai.whisperfogo.app</string>
  <key>ProgramArguments</key>
  <array><string>$APP/Contents/MacOS/whisper-fogo</string></array>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
AGENT
ok "Abre junto com o Mac"

# Ícone fixo no Dock, para achar o programa junto com os outros. O Dock guarda
# o endereço com os espaços escritos como %20, e é por esse formato que a
# checagem passa, senão a mesma entrada entraria de novo a cada instalação.
APP_URL="file://$(printf '%s' "$APP" | sed 's/ /%20/g')/"
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -qF "$APP_URL"; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP_URL</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>" \
    2>/dev/null && killall Dock 2>/dev/null
fi
ok "Ícone no Dock"

# Sobe agora, para o ícone já aparecer na barra de menus.
open "$APP" 2>/dev/null && ok "Whisper Fogo aberto"

cat <<'FIM'

  Pronto. Antes do primeiro uso, o macOS vai exigir duas permissões:

    Ajustes > Privacidade e Segurança > Microfone ......... marque o Whisper Fogo
    Ajustes > Privacidade e Segurança > Acessibilidade ... marque o Whisper Fogo

  Sem a segunda, o atalho global não funciona.

  Como usar:
    Segure a tecla Fn ............. fala e solta, o texto cola sozinho
    Fn + Espaço ................... mãos livres, a Fn de novo encerra
    Somar Control ................. revisa o texto antes de colar
    Ícone na barra de menus ....... abre o histórico de ditados

FIM
