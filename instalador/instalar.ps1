# Instalador do Whisper Fogo para Windows.
#
# Faz tudo sozinho: confere se a máquina aguenta, instala o Python isolado,
# baixa os modelos, cria o atalho e sobe o programa. Não mexe em nada fora da
# pasta de instalação.
#
# Este arquivo é UTF-8 com BOM: o PowerShell 5.1 lê .ps1 sem BOM como ANSI e
# entregaria acento quebrado. A saída do console é forçada para UTF-8 logo
# abaixo, senão o texto sai como mojibake para quem está instalando.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false
$ProgressPreference = "SilentlyContinue"

# O huggingface_hub cospe sete linhas sobre symlink do Windows em todo download.
# Nada disso muda o resultado aqui, e só polui a tela de quem está instalando.
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:PYTHONWARNINGS = "ignore"

$DESTINO   = Join-Path $env:LOCALAPPDATA "WhisperFogo"
$REPO_ZIP  = "https://github.com/bruno-org/whisper-fogo/archive/refs/heads/main.zip"
$UV_URL    = "https://astral.sh/uv/install.ps1"
$MODELO    = "large-v3-turbo"
$GEMMA_REPO = "unsloth/gemma-3-4b-it-GGUF"
$GEMMA_ARQ  = "gemma-3-4b-it-Q4_K_M.gguf"
$LLAMA_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b6193/llama-b6193-bin-win-cuda-12.4-x64.zip"
$CUDART_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b6193/cudart-llama-bin-win-cuda-12.4-x64.zip"

function Titulo($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Aviso($t)  { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Erro($t)   { Write-Host "  [X]  $t" -ForegroundColor Red }

Write-Host @"

  ####   WHISPER FOGO
  ####   Transcrição de voz offline, especializada no português brasileiro.
         Instalador para Windows

"@ -ForegroundColor Red

# ----------------------------------------------------------------- requisitos
Titulo "Conferindo se a sua máquina aguenta"

$problemas = @()
$avisos = @()

# Windows 10 ou 11, 64 bits
$os = Get-CimInstance Win32_OperatingSystem
if ([Environment]::Is64BitOperatingSystem) { Ok "Windows 64 bits: $($os.Caption)" }
else { $problemas += "O Whisper Fogo precisa de Windows 64 bits." }

# Memória RAM
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ($ramGB -ge 8) { Ok "Memória RAM: $ramGB GB" }
else { $avisos += "Você tem $ramGB GB de RAM. O recomendado são 8 GB." }

# Espaço em disco
$livreGB = [math]::Round((Get-PSDrive -Name ($env:LOCALAPPDATA.Substring(0,1))).Free / 1GB, 1)
if ($livreGB -ge 10) { Ok "Espaço livre em disco: $livreGB GB" }
else { $problemas += "Faltam $([math]::Round(10 - $livreGB, 1)) GB de espaço. A instalação completa ocupa cerca de 8 GB." }

# Placa de vídeo NVIDIA e VRAM
$usarGPU = $false
$vramGB = 0
$nvidia = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" } | Select-Object -First 1
if ($nvidia) {
    try {
        $saida = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null
        if ($saida) {
            $partes = $saida.Split(",")
            $vramGB = [math]::Round([int]$partes[1].Trim() / 1024, 1)
            Ok "Placa de vídeo: $($partes[0].Trim()), $vramGB GB de VRAM"
            $usarGPU = $true
        }
    } catch { }
    if (-not $usarGPU) {
        Ok "Placa de vídeo: $($nvidia.Name)"
        $avisos += "Não consegui ler a VRAM pelo nvidia-smi. Instale o driver mais novo da NVIDIA."
        $usarGPU = $true
    }
} else {
    $avisos += "Não encontrei placa NVIDIA. O programa vai rodar na CPU, várias vezes mais lento."
}

if ($usarGPU -and $vramGB -gt 0 -and $vramGB -lt 4) {
    $avisos += "Sua VRAM é de $vramGB GB. Abaixo de 4 GB o modelo pode não caber na placa."
}

foreach ($a in $avisos) { Aviso $a }
if ($problemas.Count) {
    foreach ($p in $problemas) { Erro $p }
    Write-Host "`nNão dá para instalar nesta máquina. Corrija os itens acima e rode de novo.`n"
    Read-Host "Pressione Enter para fechar"
    exit 1
}

$modoCPU = -not $usarGPU
if ($modoCPU) {
    Write-Host ""
    Aviso "Sem GPU, a transcrição de 1 minuto de fala pode levar mais de 1 minuto."
    $r = Read-Host "  Instalar assim mesmo? (s/N)"
    if ($r -notmatch "^[sS]") { exit 1 }
}

# --------------------------------------------------------------- o que baixar
Titulo "O que vai ser instalado"
Write-Host "  Pasta            : $DESTINO"
Write-Host "  Transcrição      : Whisper large-v3-turbo (1,6 GB)"
if ($modoCPU) {
    # sem placa NVIDIA o motor de revisão não roda, então nem oferece o download
    Write-Host "  Revisão de texto : fora, porque depende de placa NVIDIA"
    Write-Host ""
    $comRevisao = $false
} else {
    Write-Host "  Revisão de texto : Gemma 3 4B + llama.cpp (cerca de 4 GB), opcional"
    Write-Host ""
    $comRevisao = (Read-Host "  Instalar também a revisão de texto pelo Alt? (S/n)") -notmatch "^[nN]"
}

# ------------------------------------------------------------------- programa
Titulo "Instalando o programa"
New-Item -ItemType Directory -Force -Path $DESTINO | Out-Null

$tmp = Join-Path $env:TEMP "whisper-fogo-instalacao"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# Se o instalador foi rodado de dentro do repositório clonado, usa os arquivos
# locais. Senão, baixa do GitHub.
$origem = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $origem "whisper_fogo\voz.py")) {
    Ok "Usando os arquivos do repositório clonado"
} else {
    Write-Host "  Baixando o programa..."
    $zip = Join-Path $tmp "repo.zip"
    Invoke-WebRequest -Uri $REPO_ZIP -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $origem = (Get-ChildItem $tmp -Directory | Where-Object { $_.Name -like "whisper-fogo*" } | Select-Object -First 1).FullName
    Ok "Programa baixado"
}
Copy-Item (Join-Path $origem "whisper_fogo\*") $DESTINO -Recurse -Force
Ok "Arquivos copiados"

# ---------------------------------------------------------------- python e uv
Titulo "Preparando o Python"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    Write-Host "  Instalando o uv (gerenciador de Python)..."
    # o script do uv vai para o disco e roda de lá
    $uvScript = Join-Path $tmp "instalar-uv.ps1"
    Invoke-WebRequest -Uri $UV_URL -OutFile $uvScript -UseBasicParsing
    & $uvScript
    $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
}
if (-not (Test-Path $uv)) { Erro "Não consegui instalar o uv."; Read-Host; exit 1 }
Ok "uv pronto"

Push-Location $DESTINO
& $uv venv --python 3.12 .venv
Ok "Ambiente Python isolado criado"

Write-Host "  Instalando as bibliotecas (pode levar alguns minutos)..."
$pacotes = @("faster-whisper", "sounddevice", "numpy", "pystray", "pillow", "comtypes")
& $uv pip install --python "$DESTINO\.venv\Scripts\python.exe" @pacotes
Ok "Bibliotecas instaladas"

# ------------------------------------------------------------------- modelos
Titulo "Baixando o modelo de transcrição"
Write-Host "  large-v3-turbo, 1,6 GB. Só acontece uma vez."
$py = "$DESTINO\.venv\Scripts\python.exe"
$computeTipo = if ($modoCPU) { "int8" } else { "float16" }
$dispositivo = if ($modoCPU) { "cpu" } else { "cuda" }
& $py -c @"
from faster_whisper import WhisperModel
WhisperModel('$MODELO', device='$dispositivo', compute_type='$computeTipo')
print('modelo pronto')
"@
Ok "Modelo de transcrição no lugar"

if ($comRevisao) {
    Titulo "Baixando a revisão de texto"
    New-Item -ItemType Directory -Force -Path "$DESTINO\modelos", "$DESTINO\llama" | Out-Null
    Write-Host "  Gemma 3 4B, 2,4 GB..."
    & $py -c @"
from huggingface_hub import hf_hub_download
import shutil
p = hf_hub_download('$GEMMA_REPO', '$GEMMA_ARQ')
shutil.copy(p, r'$DESTINO\modelos\$GEMMA_ARQ')
print('gemma pronto')
"@
    Ok "Modelo de revisão no lugar"

    Write-Host "  llama.cpp com CUDA..."
    foreach ($u in @($LLAMA_URL, $CUDART_URL)) {
        $z = Join-Path $tmp ([System.IO.Path]::GetFileName($u))
        Invoke-WebRequest -Uri $u -OutFile $z
        Expand-Archive -Path $z -DestinationPath "$DESTINO\llama" -Force
    }
    Ok "Motor de revisão instalado"
}

# --------------------------------------------------------------- dicionario
if (-not (Test-Path "$DESTINO\dicionario.json")) {
    Copy-Item (Join-Path $origem "whisper_fogo\dicionario.exemplo.json") "$DESTINO\dicionario.json" -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------------- atalhos
Titulo "Criando os atalhos"

# Onde fica o Desktop é o Windows que responde. Com o OneDrive ligado, a pasta
# real é "...\OneDrive\Desktop" e "$env:USERPROFILE\Desktop" não existe.
function Pasta-Do-Sistema($nome, $reserva) {
    $p = [Environment]::GetFolderPath($nome)
    if (-not $p -or -not (Test-Path $p)) { $p = $reserva }
    return $p
}
$pastaDesktop = Pasta-Do-Sistema 'DesktopDirectory' "$env:USERPROFILE\Desktop"
$pastaMenu    = Pasta-Do-Sistema 'Programs' "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

$ws = New-Object -ComObject WScript.Shell
$feitos = @()
foreach ($pasta in @($pastaDesktop, $pastaMenu)) {
    $destinoLnk = Join-Path $pasta "Whisper Fogo.lnk"
    try {
        if (-not (Test-Path $pasta)) { New-Item -ItemType Directory -Force -Path $pasta | Out-Null }
        Remove-Item $destinoLnk -Force -ErrorAction SilentlyContinue
        $l = $ws.CreateShortcut($destinoLnk)
        $l.TargetPath = "$DESTINO\.venv\Scripts\pythonw.exe"
        $l.Arguments = "`"$DESTINO\voz.py`""
        $l.WorkingDirectory = $DESTINO
        $l.IconLocation = "$DESTINO\fogo.ico,0"
        $l.Description = "Whisper Fogo: ditado por voz offline"
        $l.WindowStyle = 7
        $l.Save()
        # conferir relendo do disco: editar .lnk pela metade zera o alvo em silêncio
        $conf = $ws.CreateShortcut($destinoLnk)
        if ($conf.TargetPath -and (Test-Path $conf.TargetPath)) { $feitos += $destinoLnk }
    } catch {
        # atalho é conveniência: avisa e segue, o programa já está no lugar
        Aviso "Não consegui criar o atalho em $pasta"
    }
}
if ($feitos.Count -eq 2)    { Ok "Atalho no Desktop e no menu Iniciar" }
elseif ($feitos.Count -eq 1) { Ok "Atalho criado em $(Split-Path $feitos[0] -Parent)" }
else {
    Aviso "Não consegui criar atalho nenhum. Para abrir o programa, rode:"
    Aviso "$DESTINO\.venv\Scripts\pythonw.exe `"$DESTINO\voz.py`""
}

# --------------------------------------------------------------------- testes
Titulo "Conferindo a instalação"
foreach ($t in @("corrigir.py", "aprendizado.py", "observador.py", "tema.py")) {
    $saida = & $py (Join-Path $DESTINO $t) 2>&1 | Select-Object -Last 1
    Write-Host "  $saida"
}
# o historico.py abre a janela quando chamado sem argumento, por isso o --teste
$saida = & $py (Join-Path $DESTINO "historico.py") --teste 2>&1 | Select-Object -Last 1
Write-Host "  $saida"
Pop-Location
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------- fim
Write-Host @"

  Pronto. O Whisper Fogo está instalado.

  Como usar:
    Segure Ctrl esquerdo + Shift esquerdo .... fala e solta, o texto cola sozinho
    Ctrl + Shift + Espaço ................... mãos livres, a mesma tecla encerra
    Somar Alt ............................... revisa o texto antes de colar
    Clique no ícone da bandeja .............. abre o histórico de ditados

  O primeiro ditado demora alguns segundos a mais, porque carrega o modelo.

"@ -ForegroundColor Green

$abrir = (Read-Host "  Abrir o Whisper Fogo agora? (S/n)") -notmatch "^[nN]"
if ($abrir) { Start-Process -FilePath "$DESTINO\.venv\Scripts\pythonw.exe" -ArgumentList "`"$DESTINO\voz.py`"" -WindowStyle Hidden }
