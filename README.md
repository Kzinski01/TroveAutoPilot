# Trove AutoPilot

Aplicativo Windows para automatizar rotinas no **Trove** e controlar até dois processos do jogo. A janela do aplicativo ainda se chama **Trove AutoBot**.

Interface React/Next.js em uma janela nativa WebView2, motor Python e seleção explícita de cada processo por HWND, PID e instante de criação.

> A versão de código desta auditoria passou nos testes automatizados e na compilação da interface. O envio por mensagens é experimental: o Windows aceitar uma mensagem não comprova que o jogo executou a ação. Veja os limites em [Auditoria](docs/AUDITORIA.md).

## Recursos

| Controle | Comportamento | Atalho inicial |
|---|---|---|
| Master do Jogo 1 | Liga ou pausa ataques | F5 |
| Auto clique | Cliques contínuos ou botão pressionado | F6 |
| Skills M2 / 1 / 2 | Detecta cooldown visual e envia a skill pronta | F7 |
| Poção | Pressiona Q em intervalo configurável | F8 |
| Diálogos | Reconhece Claim e convites por imagem | F9 |
| Segurar tecla | Segura, solta e repete; independente do master | F10 |
| Parar tudo | Desativa master, tecla segurada e Jogo 2 | F12 |
| Jogo 2 | Envia uma tecla periódica ao segundo processo | Controle na interface |

Os atalhos são configuráveis. A parada geral também tem um botão visível na barra lateral. A localização automática acompanha os slots quando a janela muda de tamanho; a primeira calibração continua necessária.

![Interface Midnight Galaxy em prévia sem ações](docs/assets/interface.png)

## Requisitos

- Windows 10/11 de 64 bits e Microsoft Edge WebView2 Runtime.
- Código validado com **Python 3.14.6** e **Node.js 24.16.0**.
- Duas janelas do Trove somente se você for usar o controle do Jogo 2.
- A janela escolhida precisa estar visível para leitura das skills; ícones cobertos ou jogo minimizado pausam essa leitura.

O aplicativo pede elevação por compatibilidade com jogos elevados. Para executar o código sem esse pedido, use `python main.py --no-elevate`. O Windows pode bloquear o input se o jogo tiver privilégios superiores.

## Executar pelo código

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Push-Location ui
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe main.py
```

Use o lockfile para reproduzir o ambiente auditado. `requirements.txt` lista apenas requisitos mínimos e não representa um ambiente auditado/reproduzível.

`config.json` e `templates/` são gerados localmente, ao lado do código ou executável. Cada pessoa escolhe suas próprias janelas e calibra suas skills. Handles salvos nunca ativam uma janela automaticamente no próximo arranque.

## Primeiro uso

1. Abra o Trove e selecione a janela de ataques em **Jogo 1**.
2. Escolha o modo de envio. **Compatibilidade** requer foco; **Mensagens** é experimental e não troca o foco.
3. Na aba **Skills**, ative a localização automática e deixe a barra visível. Capture **Pronta** para cada slot. O modo manual permite selecionar **Área**.
4. Ative as rotinas desejadas e ligue o master com F5 no jogo. O limite inicial das skills é `0.80`.
5. Para o Jogo 2, selecione outro processo em **Funções**, configure tecla/intervalo e ligue o controle próprio. Ele independe do master do Jogo 1.
6. Para diálogos, capture um trecho com texto ou ícone e defina o ponto de clique. Recortes sem textura são recusados.

F12 para as duas instâncias e a tecla segurada. No modo Compatibilidade, uma soltura global pode ser adiada quando a janela perde foco, para não atingir outra conta: volte à janela selecionada. Ao fechar o aplicativo fora de foco, uma soltura pendente pode exigir pressionar/soltar fisicamente a tecla ou botão.

## Desenvolvimento da interface

```powershell
cd ui
npm ci
npm run dev
```

Acesse `http://localhost:3000/?preview=1` para uma **prévia com dados de exemplo e ações desativadas**. Sem esse parâmetro, o navegador informa que o motor não está conectado. O aplicativo desktop usa o build estático de `ui/out/`.

Tema **Midnight Galaxy**, escolhido pelo mantenedor: roxo profundo e lavanda, foco de teclado visível, estados de conexão e suporte a movimento reduzido. [Decisões de design](docs/DESIGN.md).

## Verificar e gerar executável

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
python -m ruff check .
python -m pip_audit -r requirements-lock.txt --no-deps --disable-pip
python -m bandit -q -r . -x './.venv,./.audit-venv,./ui,./build,./dist,./release,./release-audit,./Build Final,./tests,./backups' -ll
Push-Location ui
npm run lint
npm run typecheck
npm audit --omit=dev
npm run build
Pop-Location
python build_release.py --skip-ui --output-dir release-audit
```

O pacote é uma **pasta**, não um executável isolado: mantenha `_internal` ao lado de `TroveAutoBot.exe`. O build gera configuração limpa, ZIP e SHA-256, inclui licenças e recusa sobrescrever uma distribuição anterior. Para um build comum, use `python build.py`.

A verificação `TroveAutoBot.exe --selftest` carrega a interface e a telemetria sem iniciar rotinas ou registrar atalhos de jogo. Não valida a aceitação de input pelo Trove. [Roteiro de teste com duas instâncias](docs/VALIDACAO_MANUAL.md).

## Arquitetura e segurança

```text
ui/                 interface estática Next.js + React + TypeScript
api.py              ações da interface pela ponte pywebview
telemetry_server.py leitura de estado em HTTP/1.1 local com token efêmero
bot.py / routines.py rotinas e ciclo de vida do Jogo 1
periodic_key.py      tecla periódica independente do Jogo 2
targeted_input.py   validação de identidade, foco e solturas
game_windows.py    descoberta Win32 com lista permitida de executáveis
vision.py          capturas em uma thread permanente
config_validation.py validação de campos carregados do disco
```

O pywebview serve os arquivos estáticos por HTTP local. Há **também** um servidor próprio de telemetria em `127.0.0.1`, porta aleatória, com token por arranque, validação de Host/Origin e respostas sem cache. Ele não envia dados para serviços externos. Instalação de dependências e desenvolvimento consultam os registros de pacotes.

Não foram encontrados tokens ou chaves privadas pelos padrões usados na auditoria. Isso não substitui secret scanning contínuo. Configurações, logs, capturas pessoais, caches e builds são excluídos pelo `.gitignore`.

Consulte [Auditoria](docs/AUDITORIA.md), [Política de segurança](SECURITY.md) e [Contribuição](CONTRIBUTING.md). Há sete alertas de desenvolvimento ligados à cadeia de `braces`; a auditoria de dependências de produção do frontend passou sem alertas. Não exponha o servidor de desenvolvimento à rede nem compile conteúdo não confiável. Os documentos antigos na raiz e em `docs/history/` são registros históricos.

## Licença

Código próprio sob [MIT](LICENSE), conforme autorizado pelo mantenedor. Fontes, dependências e materiais do jogo mantêm seus próprios direitos: [avisos de terceiros](THIRD_PARTY_NOTICES.md). O mantenedor declarou autoria do logo e permissão para redistribuir a base Orbit; o texto original dessa permissão não foi fornecido à auditoria.

Projeto independente. Automatizar entradas pode contrariar as regras do jogo; a publicação do código não garante permissão de uso no Trove.
