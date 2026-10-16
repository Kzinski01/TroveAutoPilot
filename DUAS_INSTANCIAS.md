> Registro hist?rico anterior ? revis?o de publica??o. Para comandos, estado e limites atuais, consulte [README.md](README.md) e [Auditoria](docs/AUDITORIA.md).

# Um bot para dois jogos

Abra `dist/two-game/TroveAutoBot/TroveAutoBot.exe` e feche versões anteriores
antes disso. O novo pacote preserva as calibrações e ajustes do pacote
`background-skills`; os pacotes anteriores continuam disponíveis para reversão.

Os nomes Jogo 1 e Jogo 2 representam **funções**, não a ordem de abertura das
contas. Você escolhe qual processo receberá cada função:

| Destino | Comportamento |
|---|---|
| Jogo 1 — ataques | Auto clique, skills, poção, diálogos e segurar tecla existentes |
| Jogo 2 — tecla periódica | E a cada 20 segundos, com tecla e intervalo configuráveis |

## Configurar

1. Abra as duas instâncias em modo janela e coloque-as lado a lado.
2. No seletor acima das abas, escolha a janela que continuará recebendo os
   ataques. Confira HWND, PID e posição. Use o backend Mensagens.
3. Na aba **Funções**, procure **Jogo 2 — tecla periódica**. Clique Atualizar e
   selecione o outro processo. O programa recusa o mesmo PID nos dois destinos,
   mesmo que existam dois HWNDs nesse processo.
4. Deixe a tecla E e o intervalo 20, ou altere-os e clique **Salvar ajustes**.
   São aceitas teclas da tabela existente de scancodes e intervalos entre
   0,5 e 86400 segundos.
5. Ligue o switch **Tecla periódica**. O primeiro envio ocorre após o intervalo
   completo; a contagem aparece ao vivo. Mudar tecla/intervalo ou religar o switch
   reinicia essa contagem. Não há sequência acumulada de envios após uma pausa.
6. Ligue as rotinas e o master do Jogo 1 como antes. Deixe os ícones desse jogo
   visíveis; se redimensionar a janela, recapture as áreas das skills.

O switch da tecla periódica funciona independentemente do master de ataques.
**F12 para ambos**, incluindo a rotina independente de segurar tecla. Selecionar
ou trocar o backend do Jogo 1 usa o pânico existente e também desliga a tecla
periódica. Selecionar o Jogo 2 desliga somente sua rotina antes da mudança.

Não é necessário o macro Logitech. Desligue-o para evitar E duplicado/global.

## Isolamento e limites

Cada destino possui sua própria instância de `TargetedInput`, configuração,
HWND/PID/criação do processo e estado de teclas pressionadas. A seleção e os
envios periódicos usam um lock compartilhado para não permitir que uma troca de
destino cause colisão com o processo de ataques.

O Jogo 2 usa exclusivamente PostMessage: não chama SendInput, não muda o foco
e não interfere no cursor global. Não existe fallback global. Continua sem foco,
sem depender da leitura de imagens ou das skills do Jogo 1. Janelas minimizadas,
encerradas ou com identidade alterada bloqueiam o envio. Encerrar uma janela não
faz o bot escolher outra automaticamente.

A escolha salva é um registro: é preciso selecionar explicitamente os destinos
a cada início. A tecla periódica sempre inicia desligada. O jogo deve aceitar
as mensagens — o usuário confirmou funcionamento do mecanismo no seu cenário;
mensagem enfileirada continua não sendo uma confirmação automática de execução.

Logs da segunda rotina incluem `[Bot][Jogo 2]`, tecla, HWND e PID. A contagem e
os motivos de pausa aparecem no menu. O input de ataques segue as proteções e
limitações já documentadas em `AUDITORIA_INPUT.md`.

## Verificação

Primeiro deixe somente a tecla periódica ligada e confira E no Jogo 2 após 20s.
Depois ligue os ataques: os logs de skills devem mostrar o destino de ataques;
os logs `[Jogo 2] E enviado` devem apontar para o outro HWND/PID. Alterne o foco
e confira que E continua apenas no Jogo 2. Teste também F12 e o fechamento do
Jogo 2: nenhum evento deve passar para o Jogo 1.

Os testes automatizados simulam os dois processos com transporte Win32
substituído, sem enviar teclas para os jogos abertos. Verificam os dois destinos,
o primeiro prazo, repetição, alteração de intervalo, tecla configurável, PID
duplicado, HWND reaproveitado, minimização, falhas de PostMessage, pânico e
shutdown. Os 221 testes da suíte passaram. O build da interface e do executável
foi concluído; o selftest do pacote confirmou a interface carregada e a ponte
com Python. Os envios dentro do jogo devem ser confirmados pelo teste acima.

Arquivos desta mudança: `periodic_key.py` (novo), `bot.py`, `api.py`, `config.py`,
`targeted_input.py` (repetição de solturas direcionadas pendentes sem exigir foco),
`ui/components/secondary-controls.tsx` (novo),
`ui/components/pages/functions-page.tsx`, `ui/components/window-selector.tsx`,
`ui/lib/api.ts`, `ui/types/index.ts`, `tests/test_periodic_key.py` (novo) e
documentação. Backup dos fontes anteriores: `backups/before-two-game-control.zip`.
