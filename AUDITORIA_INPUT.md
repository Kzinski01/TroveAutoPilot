> Registro hist?rico anterior ? revis?o de publica??o. Para comandos, estado e limites atuais, consulte [README.md](README.md) e [Auditoria](docs/AUDITORIA.md).

# Auditoria e isolamento das instâncias

A versão atual também controla uma segunda janela com tecla periódica:
veja [DUAS_INSTANCIAS.md](DUAS_INSTANCIAS.md) e o pacote `dist/two-game`.

Auditoria realizada antes das alterações. Uma cópia dos fontes anteriores está
em `backups/before-window-isolation.zip` (sem dependências ou executáveis).

## Diagnóstico original

O projeto envia input com `ctypes.WinDLL("user32")` e `SendInput`, em
`input_sender.py`. Eventos de teclado usam scancodes físicos com
`KEYEVENTF_SCANCODE`; mouse usa estruturas `MOUSEINPUT`. Não existe biblioteca
DirectInput: o comentário sobre compatibilidade com jogos não comprova qual API
o Trove usa internamente.

| Rotina em bot.py | Funções | Envio em input_sender.py |
|---|---|---|
| Ataque básico | `_loop_autoclick`, `_spam_click`, `_hold_mouse`, `_release_mouse` | `click`, `mouse_down`, `mouse_up` |
| Skills M2, 1 e 2 | `_loop_skills`, `_try_skill`, `_press` | `click` ou `tap` |
| Poção Q | `_loop_potion`, `_press` | `tap` |
| Tecla mantida, padrão T | `_loop_holdkey`, `_hold_key_once`, `_release_held_key` | `key_down`, `key_up` |
| CLAIM/invites | `_handle_dialog`, `_dismiss_dialog`, `_press` | `tap` ou `click_at` |

Todos os envios convergem para `_send`, que chama `SendInput` **sem HWND**.
`click_at` move o cursor global com `move_to` e depois o restaura. Ataques normais
usam a posição atual do cursor. `tap`/`key_down` pressionam teclas globalmente.
Não existe rotina automática de E nos padrões/configuração auditados; E é uma
tecla suportada caso seja configurada pelo usuário.

`hotkeys.py` usa `pynput.keyboard.Listener` para **escutar** atalhos globais,
sem suprimir as teclas nem enviar ataques. Não usa `keyboard.Controller`.
Não foram encontrados envios por pyautogui, pacote keyboard, pacote mouse,
pynput.mouse, win32api/gui/con, pydirectinput, PostMessage ou SendMessage. A
referência a pyautogui era apenas um comentário.

O HWND obtido por `GetForegroundWindow` era usado apenas para ler o título.
`Bot.blocked_reason` comparava esse título por substring com `target_window` e
`extra_windows`. Desligar `only_when_focused` removia essa checagem. Não havia
PID, identificação do processo do jogo ou seleção de instância. Portanto duas
janelas chamadas Trove passavam pelo mesmo filtro. O projeto não contava jogos
abertos: assumia que qualquer título compatível representava o mesmo alvo.

`single_instance.py` usa mutex, FindWindow e SetForegroundWindow **para o bot**,
impedindo dois bots abertos; isso não restringe quantos jogos podem ser abertos.
`main.py` controla elevação e DPI. `api.py` apenas minimizava/restaurava a UI para
calibração; não focava o jogo. `vision.py` capturava regiões absolutas das skills
e procurava templates de diálogos no monitor inteiro, também sem identidade.

## Arquitetura aplicada

1. `game_windows.py`: lista somente janelas visíveis de `Trove.exe` ou
   `Trove_x64.exe` que passam pelo filtro de títulos de Ajustes. Exclui o próprio
   bot e não chama SetForegroundWindow. Isso exclui Explorer/VS Code com Trove
   no título. Ordena pelo início do processo; a ordem não identifica uma conta.
2. A UI mostra título, HWND, PID e retângulo da área cliente. A seleção envia a
   identidade inteira; o backend enumera novamente e recusa uma linha obsoleta.
3. `targeted_input.py` concentra **todas** as ações do motor, inclusive solturas,
   movimento para diálogos e troca de backend. Valida HWND, PID, criação do
   processo e executável. Título não participa da identidade durante execução.
4. `config.json` passa a poder salvar `selected_window` e `input_mode`. O alvo
   salvo serve como registro; a cada início é preciso selecionar explicitamente
   uma instância novamente. Não existe escolha automática de outra janela ao
   encerrar o jogo.
5. Trocar alvo ou backend desliga o master e a rotina independente de tecla
   mantida. A seleção é recusada se houver solturas globais pendentes no alvo
   anterior. Os atalhos continuam globais e não devem coincidir com os do macro.
6. Skills passam a usar `window_region`, relativa à área cliente e vinculada ao
   seu tamanho. É preciso recapturar as regiões antigas uma vez. Mover a janela
   translada a região; redimensionar exige recaptura. Os valores, limiares,
   intervalos e templates anteriores são preservados.
7. A visão continua por captura da tela: **no backend de mensagens, skills
   funcionam sem foco quando seus ícones estão visíveis**. A leitura verifica
   nove pontos do recorte antes e depois da captura e pausa se detectar outra
   janela cobrindo o ícone. Diálogos continuam exigindo foco. Templates são procurados
   apenas na área cliente selecionada. Calibração suspende o input do bot e
   valida que o recorte pertence à janela escolhida.

## Backends e limitações reais

**Compatibilidade (padrão):** mantém SendInput com os mesmos scancodes e tempos.
O alvo escolhido deve estar em primeiro plano; desativar o antigo filtro não
contorna essa exigência. Cliques exigem cursor/ponto dentro da área cliente e a
janela escolhida sob o ponto. Não há troca automática de foco. Diálogos ainda
movem/restauram o cursor global; os dois programas compartilham esse cursor.
O código verifica o retorno de SendInput e não registra sucesso em caso de falha.

Se o foco mudar entre pressionar e soltar, a soltura **não é injetada na outra
conta**: fica pendente até o alvo anterior voltar ao foco. Isso pode deixar uma
tecla/botão logicamente pressionado. Volte à Conta 2 antes de desligar/encerrar;
se ela já tiver sido fechada, pressione e solte fisicamente o botão/tecla usado.
Não existe soltura global irrestrita no pânico/shutdown como atalho de limpeza.

SendInput continua global. A checagem do foco e o envio não são uma operação
atômica do Windows: há uma corrida residual se outro programa trocar o foco no
instante do envio. Uma tecla já pressionada também pode influenciar o estado
global de input. Portanto este modo **não oferece isolamento absoluto** nem
permite prometer dois jogos recebendo input global independente ao mesmo tempo.

**Mensagens à janela (experimental):** usa PostMessageW com WM_KEYDOWN/UP e
WM_*BUTTONDOWN/UP, incluindo scancode e coordenadas de cliente. Não chama
SendInput nem move o cursor. Se o cursor estiver fora da Conta 2, ataques de
mouse usam o centro da área cliente; cliques de diálogos usam seu ponto detectado.
Quando um botão é mantido, a mensagem de soltura mantém o mesmo destino.
Não envia para HWND nulo ou broadcast. Falha não ativa fallback global.

Uma mensagem enfileirada não confirma que o jogo reconheceu o comando. Jogos
que leem dispositivos por Raw Input/DirectInput podem ignorá-la. A aceitação
pelo Trove, inclusive no modo segurar, precisa de teste real. O usuário confirmou
recebimento do input direcionado; os testes automatizados não validam o jogo.
Janela minimizada bloqueia novas ações. Se mensagens forem
ignoradas, selecione Compatibilidade e mantenha a Conta 2 em foco. Para isolamento
rigoroso caso o jogo rejeite mensagens, use sessões/máquinas separadas que
consigam executar o jogo com seus requisitos gráficos. Não há solução comprovada
de input em segundo plano para o Trove neste projeto.

Um macro externo que injeta E globalmente atingirá a Conta 2 quando ela estiver
em foco. Este bot não consegue atribuir esse E à Conta 1. O macro também precisa
direcionar seus comandos à sua própria janela, com suporte real do jogo, ou ser
executado em sessão/máquina separada.

**Macro informado pelo usuário: mouse Logitech.** Para um macro comum de teclas
do mouse/G HUB, trate E como input global. Perfis por jogo não são seleção por
HWND/PID de uma das contas. A combinação a testar é Conta 1 em foco com o macro
Logitech e Conta 2 selecionada no bot em modo Mensagens, inicialmente só com
Auto clique. Se o Trove ignorar as mensagens, essa combinação não tem isolamento
simultâneo comprovado. Em Compatibilidade, pare o macro antes de focar a Conta 2;
F12 para apenas o bot, não o macro Logitech. Não foram alteradas configurações
do mouse ou do G HUB.

Fontes técnicas: [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput),
[PostMessageW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-postmessagew),
[Raw Input](https://learn.microsoft.com/en-us/windows/win32/inputdev/about-raw-input).

## Como selecionar a Conta 2 e testar

1. Abra `dist/background-skills/TroveAutoBot/TroveAutoBot.exe`, ou execute os
   fontes atualizados com `python main.py`. Esse pacote inclui a correção de
   skills sem foco, as calibrações mais recentes do pacote `window-isolated`
   e o modo Mensagens selecionado. A interface compilada em `ui/out` também foi
   atualizada. Os executáveis anteriores de `dist/TroveAutoBot` e `release`
   foram preservados e não incorporam estas alterações.
2. Abra as duas contas em modo janela. Identifique a Conta 2 visualmente e
   coloque-a em uma posição diferente da Conta 1. No Gerenciador de Tarefas,
   consulte o PID do processo correspondente, se necessário.
3. No seletor acima das abas, clique Atualizar e escolha a linha da Conta 2
   conferindo HWND, PID e área/posição. Clique Selecionar. Confira os logs
   `[Bot] Janela selecionada`, `HWND` e `PID`. Números/ordem não revelam a conta.
4. Recapture as áreas das skills com a Conta 2 visível e em foco e calibre
   Pronta. Os templates de diálogo podem ser reaproveitados; confira os offsets.
5. Primeiro deixe o macro da Conta 1 desligado. Ative apenas Auto clique,
   desligue skills/poção/diálogos/segurar tecla e ligue F5 na Conta 2. Confira o
   ataque nessa conta e o HWND dos logs. Depois teste cada rotina separadamente.
6. Em Compatibilidade, pressione F12 com a Conta 2 em foco antes de trocar de
   conta. Em um teste separado, ao perder foco com o bot ativo, confira `Janela
   perdeu foco`/`Input ignorado por segurança`; retorne à Conta 2 para liberar
   qualquer soltura pendente. A Conta 1 não deve receber novos ataques do bot.
7. Se desejar segundo plano, pare o bot, selecione Mensagens, ligue inicialmente
   só Auto clique e teste a Conta 2 em foco e depois em segundo plano. Se não
   houver ataques, o log de mensagem enviada **não** prova funcionamento.
   Teste tanto Clicar quanto Segurar. Volte ao modo Compatibilidade se necessário.
8. Teste o macro da Conta 1 sozinho, com a Conta 2 em foco. Se E causar ação na
   Conta 2, o macro é global ou está mal direcionado: ainda existe interferência.
9. Somente após esses testes, ligue os dois. Cada conta deve exibir apenas as
   ações esperadas. Verifique também atalhos compartilhados e movimento do
   cursor. Feche/reabra a Conta 2 em um teste com input parado: o bot deve bloquear
   o alvo antigo e exigir uma nova seleção, sem assumir a Conta 1.

Logs de input aparecem no painel existente. Sucessos são resumidos no máximo
uma vez por segundo para não inundar a UI; bloqueios de foco são registrados
quando o motivo muda. Mensagens de seleção/bloqueio incluem a identidade.

## Riscos, validação e reversão

Arquivos alterados/criados:

| Arquivos | Alteração |
|---|---|
| `game_windows.py` (novo) | Descoberta Win32, identidade HWND/PID/criação/executável, área cliente e hit-test |
| `targeted_input.py` (novo) | Destino obrigatório, backends, solturas pendentes, serialização e logs |
| `input_sender.py` | Assinatura/retorno de SendInput e coordenadas corretas no desktop virtual |
| `bot.py` | Todas as ações passam pelo destino; visão limitada; falhas não contam como sucesso |
| `api.py` | Listagem/seleção/modo, telemetria por identidade, calibração suspensa e validada |
| `config.py` | Defaults de `selected_window` e `input_mode` |
| `ui/components/window-selector.tsx` (novo), `ui/app/page.tsx` | Seletor permanente, modo de input e motivo do bloqueio |
| `ui/lib/api.ts`, `ui/types/index.ts` | Contrato TypeScript dos novos métodos e estados |
| `ui/components/pages/settings-page.tsx` | Filtro de foco obrigatório na compatibilidade |
| `tests/test_core.py`, `tests/test_api.py`, `tests/fake_target.py` (novo), `tests/test_targeted_input.py` (novo) | Doubles separados do transporte real e testes do isolamento |
| `README.md`, `AUDITORIA_INPUT.md` (novo) | Diagnóstico, uso, limites e reversão |
| `ui/out`, `dist/window-isolated`, `build/window-isolated` | Interface e pacote atualizados; artefatos do build |

O `config.json` original, templates originais, requirements e executáveis
anteriores não foram alterados. O novo pacote contém cópias do config/templates.

Riscos: mensagens ignoradas pelo jogo; captura de tela indisponível no segundo
plano; calibração antiga bloqueada; soltura adiada ao perder foco; corrida do
backend global; macro externo e atalhos globais. A descoberta usa callback
ctypes com assinaturas explícitas e só coleta HWNDs; nenhuma exceção Python é
propagada pela fronteira nativa. O histórico do projeto registra crashes após
antigas mudanças de foco, portanto elas não foram reintroduzidas.

Os envios são serializados para impedir que a seleção/backend mude entre
pressionar e soltar. Isso pode atrasar um clique enquanto outra rotina envia
uma tecla; os tempos e intervalos configurados foram mantidos.

Testes automatizados simulam duas janelas com títulos iguais, PID/HWND
reaproveitados, foco perdido durante tap/hold, solturas, falhas de API, cliques
encobertos, movimento da janela, redimensionamento, seleção obsoleta e mensagens
sem fallback global. Não injetam ataques no jogo aberto. A listagem Win32 real
foi verificada em leitura; a UI passou pelo build com checagem TypeScript.
Resultado após a correção das skills em segundo plano: 194 testes aprovados.
Os testes adicionais verificam disparos repetidos sem foco com intervalo
preservado, bloqueio ao cobrir o ícone durante a captura, manutenção do bloqueio
de foco no backend global e logs sem repetição desnecessária.
Há avisos de sockets não fechados e depreciação
do mss que também apareciam na suíte original, antes das mudanças.
O pacote anterior (`window-isolated`) também passou pelo `--selftest`: ponte carregada, estilos
aplicados, seletor preenchido com a janela real do jogo e nenhum alvo armado
automaticamente. Não foram enviados ataques durante esse teste.
O pacote `background-skills` passou pelo build; seu selftest não foi executado
enquanto a versão anterior permanece aberta, pois o mutex permite apenas um bot.

A versão corrigida está em `dist/background-skills`; a anterior, atualmente
aberta, não é substituída durante a execução. Feche a versão antiga e abra a
nova para carregar a correção. As alterações desta correção estão em
`targeted_input.py`, `bot.py`, `ui/components/window-selector.tsx`, seus testes
e documentação. Backup anterior à correção: `backups/before-background-skills.zip`.

Para reverter, restaure os fontes do ZIP, remova `game_windows.py`,
`targeted_input.py`, `ui/components/window-selector.tsx` e os novos testes, e
recompile a UI com `cd ui` / `npm run build`. O config antigo é compatível: as
chaves novas são ignoradas pela versão anterior. Nenhuma dependência nova foi
adicionada e os executáveis antigos foram preservados.
