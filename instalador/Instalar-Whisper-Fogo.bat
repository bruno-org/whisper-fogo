@echo off
REM Instalador de um clique do Whisper Fogo para Windows.
REM Baixe este arquivo e de dois cliques. Ele busca o instalador completo e roda.
REM
REM Sem acentuacao de proposito: o console do Windows le em CP850 e acento em
REM UTF-8 aparece quebrado na tela de quem esta instalando.

title Instalar o Whisper Fogo

REM Se o arquivo esta dentro do repositorio clonado, usa o script local.
if exist "%~dp0instalar.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/bruno-org/whisper-fogo/main/instalador/instalar.ps1 | iex"
)

if errorlevel 1 (
    echo.
    echo A instalacao nao terminou. Leia a mensagem acima.
    pause
)
