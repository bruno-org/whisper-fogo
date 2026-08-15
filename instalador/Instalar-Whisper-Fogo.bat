@echo off
REM Instalador de um clique do Whisper Fogo para Windows.
REM Baixe este arquivo e dê dois cliques. Ele busca o instalador completo e roda.
REM
REM Este arquivo é UTF-8 sem BOM e a primeira coisa que ele faz é trocar a
REM codepage do console para 65001. Sem isso o console lê os bytes como CP850 e
REM a acentuação aparece quebrada na tela de quem está instalando.
chcp 65001 > nul

title Instalar o Whisper Fogo

REM Se o arquivo está dentro do repositório clonado, usa o script local.
REM Quando vem de fora, o script é gravado em disco e executado de lá.
set "INSTALADOR=%~dp0instalar.ps1"
if not exist "%INSTALADOR%" (
    echo Baixando o instalador...
    curl.exe -fsSL -o "%TEMP%\whisper-fogo-instalar.ps1" "https://raw.githubusercontent.com/bruno-org/whisper-fogo/main/instalador/instalar.ps1"
    if errorlevel 1 (
        echo.
        echo Não consegui baixar o instalador. Confira a sua conexão com a internet.
        pause
        exit /b 1
    )
    set "INSTALADOR=%TEMP%\whisper-fogo-instalar.ps1"
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALADOR%"

if errorlevel 1 (
    echo.
    echo A instalação não terminou. Leia a mensagem acima.
    pause
)
