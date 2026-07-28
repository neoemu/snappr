# Snappr

Ferramenta de captura de tela para Linux (X11) inspirada no [Shottr](https://shottr.cc/),
com foco na captura **em scroll** (scrolling screenshot): junta vários frames de
uma região fixa enquanto você rola o conteúdo, produzindo uma única imagem alta.

## Recursos (MVP)
- Captura de **região** (seleção retangular).
- Captura de **tela cheia** (todos os monitores).
- **Captura em scroll** manual: selecione uma região, role o conteúdo e o app
  costura os frames automaticamente.
- **Salvar** em PNG e **copiar** para a área de transferência.
- Ícone na **bandeja do sistema** + **atalhos globais** configuráveis.

## Requisitos
- Linux com sessão **X11** (testado em Linux Mint / Cinnamon).
- Python 3.10+.
- `xclip` (opcional, fallback de cópia para a área de transferência).

## Dependências de sistema (nova máquina)
Em uma máquina limpa, instale primeiro as bibliotecas de runtime do Qt6/PySide6
(OpenGL/EGL, `libxkbcommon`, plugins `xcb-util`) e o `python3`+venv:

```bash
./system-deps.sh          # detecta apt/dnf/pacman/zypper e instala; usa sudo
./system-deps.sh -y       # instala sem confirmar
./system-deps.sh -n       # dry-run: só mostra o que seria instalado
```

Se o distro não for detectado, o script imprime a lista de pacotes para instalar
manualmente. As dependências **Python** são tratadas à parte pelo `run.sh` /
`install.sh` dentro do virtualenv.

## Como rodar
```bash
./run.sh
```
Na primeira execução o script cria um virtualenv em `.venv/` e instala as
dependências de `requirements.txt`. O app fica na bandeja do sistema.

Alternativa manual:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Instalar no menu
Para instalar o launcher e o ícone no menu do usuário atual:

```bash
./install.sh
```

Para também iniciar automaticamente após login:

```bash
./install.sh --autostart
```

Para remover o launcher, autostart e ícone:

```bash
./uninstall.sh
```

Para remover também `.venv/` e `~/.config/snappr/`:

```bash
./uninstall.sh --all
```

## Atalhos padrão
- `Ctrl+Shift+A` — capturar região
- `Ctrl+Shift+S` — captura em scroll
- `Ctrl+Shift+F` — capturar tela cheia

Configuráveis em `~/.config/snappr/config.json`.

## Como usar a captura em scroll automático
1. Acione a captura em scroll (atalho ou menu da bandeja).
2. Selecione a **região** que contém o conteúdo rolável (mantenha a seleção
   dentro da área que vai rolar, sem incluir barras de rolagem fixas).
3. O app move o mouse para o centro da região, rola automaticamente e captura
   cada passo.
4. A captura termina sozinha quando a visualização parar de mudar, normalmente
   no fim da página.
5. Durante a captura, pressione `Enter`, `Espaço` ou `Ctrl+Enter` para concluir
   manualmente; pressione `Esc` para cancelar.

## Testes
```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

## Limitações conhecidas
- Apenas **X11** (Wayland não suportado neste MVP).
- Headers/rodapés fixos ou barras de rolagem dentro da região podem atrapalhar
  a costura. Selecione apenas a área de conteúdo.
- Sem anotação, OCR ou pin-na-tela ainda (planejado para próximas versões).

## Arquitetura
- `snappr/capture.py` — captura via `mss`.
- `snappr/stitch.py` — costura vertical (template matching com OpenCV).
- `snappr/scroll_capture.py` — orquestra a sessão de scroll.
- `snappr/overlay.py` — overlay de seleção de região.
- `snappr/preview.py` — janela de resultado.
- `snappr/tray.py` / `snappr/hotkey.py` — bandeja e atalhos globais.
- `snappr/app.py` — controller que liga tudo.
