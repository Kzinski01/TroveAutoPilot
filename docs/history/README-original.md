> Documento hist?rico anterior ? auditoria de 16/10/2026. Instru??es e resultados podem estar desatualizados. Consulte o README da raiz.

# Trove AutoBot

Distribuição pronta: `Build Final.zip`. Extraia a pasta inteira e abra
`Build Final/TroveAutoBot.exe`, mantendo `_internal` ao lado. A configuração do
pacote é limpa: cada pessoa seleciona suas janelas e calibra as skills. Para
regerar, use `python build_release.py`. A revisão e as verificações estão em
[RELATORIO_BUILD_FINAL.md](../../RELATORIO_BUILD_FINAL.md).

Bot para o Trove com deteccao de cooldown por imagem. A interface e um app
**Next.js + React + TypeScript + Tailwind** (design do template Orbit) exibido
numa janela nativa; o nucleo (visao, input, atalhos) e Python.

## Arquitetura

```
+---------------------------- janela pywebview (WebView2) ----------------------+
|  ui/  Next.js 15 + React 19 + TypeScript + Tailwind 3 (export estatico)       |
|         |  window.pywebview.api.<metodo>()                                    |
+---------|--------------------------------------------------------------------+
          v
   api.py  ponte tipada (ver ui/lib/api.ts + ui/types/index.ts)
          |
   bot.py  5 threads: auto clique | skills | pocao | janelas | tecla
          |
   vision.py (OpenCV + mss)   input_sender.py (SendInput scancode)   hotkeys.py
```

Nao ha servidor HTTP proprio nem porta aberta: a comunicacao usa a ponte JS do
pywebview. O `http_server` do pywebview serve `ui/out` apenas em `127.0.0.1`
para o Next resolver os assets.

## Executavel (recomendado)

`dist/TroveAutoBot/` — **pasta**, nao arquivo unico. Nao precisa de Python, Node
nem instalar nada; a interface compilada vai embutida. `config.json` e
`templates/` sao criados ao lado do exe. Ele pede elevacao de administrador ao
abrir.

### Por que onedir e nao onefile

O `--onefile` extraia ~66 MB para o `%TEMP%` a cada execucao: **3,5 s de tela
preta** antes da janela aparecer. Como nao havia retorno visual, era natural
clicar de novo — e o segundo clique subia uma segunda instancia, com dois
listeners de atalho e dois bots disputando o mouse (um segurando o botao,
outro soltando). Com `--onedir` a abertura caiu para **1,0 s**; alem disso:

- **Instancia unica** (`single_instance.py`): um mutex nomeado impede a segunda
  copia e traz a janela existente para a frente.
- **Tela de abertura** (`--splash`): o logo aparece no instante do clique.
  Ela e fechada por uma thread propria — chamar `pyi_splash.close()` de dentro
  de uma chamada da ponte (thread do WebView2) nao funciona. O gatilho e o
  primeiro `poll()` da interface, com timeout de seguranca.

Para gerar de novo:

```
pip install pyinstaller
python build.py              # compila a UI e empacota
python build.py --skip-ui    # reaproveita ui/out ja compilado
```

### Icone

`assets/logo.png` e a arte oficial. O build converte para `assets/icon.ico`
(16 a 256 px) e o aplica no executavel e na barra de titulo da janela. Para
trocar o icone, substitua o `logo.png` e rode o build de novo — ou
`python make_icon.py` para so regerar o `.ico`. Precisa de Pillow
(`pip install pillow`); sem ele o build segue com o icone padrao.

## Rodando pelo codigo

```
pip install -r requirements.txt
cd ui && npm install && npm run build && cd ..
python main.py
```

Faltando alguma lib Python, o bot abre uma janela com **Instalar dependencias**
antes da interface. O mesmo botao esta na aba **Ajustes**.

Para mexer na interface com recarga automatica: `cd ui && npm run dev`. No
navegador a ponte nao existe, entao a UI aparece sem dados — o layout e
estilo continuam validos.

## O que ele faz

| Funcao | Comportamento | Atalho padrao |
|---|---|---|
| Auto clique (M1) | Clique esquerdo continuo — prioridade maxima | F6 |
| Skills M2 / 1 / 2 | Le o icone e dispara ao sair do cooldown | F7 |
| Pocao (Q) | Pressiona a tecla em intervalo fixo | F8 |
| Segurar tecla | Segura a tecla N segundos, solta e repete sem pausa. **Independente do master** | F10 |
| Janelas | Fecha o CLAIMS e responde aos convites | F9 |
| Master | Liga/desliga tudo (menos as rotinas independentes) | F5 |
| Panico | Desliga tudo na hora | F12 |

Clique no atalho e pressione a nova combinacao para trocar; ESC durante a
captura remove o atalho (ou use o **x** que aparece ao passar o mouse).

`bot.INDEPENDENT_FEATURES` lista as rotinas que ignoram o master: elas so
obedecem ao proprio switch. Continuam respeitando o filtro de foco e o
panico (F12), que sao travas de seguranca, nao acoplamento.

## Calibracao

**Skills** (aba Skills), para cada slot:

1. **Area** — arraste sobre o icone, so o icone.
2. Com a skill acesa, **Pronta** (define o `ready_score`, base do ratio).
3. O **limite** e digitado na caixa da propria skill; o padrao e `0.80`.

**Em cooldown (sugere limite)** e opcional: mede o icone escuro e escreve uma
sugestao no log, sem alterar o valor que voce escolheu. Os icones do Trove
pulsam e o ratio de uma skill pronta oscila cerca de 0.15, entao um limite alto
(0.95+) cai dentro desse ruido e a skill **nunca dispara**. O numero a direita
mostra `ratio / limite` ao vivo (verde = dispararia).

Antes de qualquer captura o bot minimiza a propria janela e nada mais: quem
deixa o jogo visivel e o usuario. Ja houve aqui uma troca de foco por
`EnumWindows`/`SetForegroundWindow` mais uma contagem de 2 s, para garantir que
o jogo estivesse na frente. **Foi tudo removido**: o app passou a cair depois
dessa mudanca (secao "O bot fechava sozinho"). Depois que o seletor fecha,
`REDRAW_DELAY` evita que o proprio overlay entre no template.

**Janelas** (aba Janelas): com o dialogo aberto, **Capturar janela** sobre um
trecho unico (o titulo "CLAIMS" funciona bem) e depois **Ponto de clique** no X.
Recortes lisos sao recusados: sem textura o `matchTemplate` casa em qualquer
lugar e o bot clicaria a esmo.

## A janela trava em "Conectando ao motor do bot"

Causa ja corrigida, registrada aqui porque a armadilha e facil de repetir: o
pywebview monta a ponte percorrendo os atributos **publicos** do objeto passado
em `js_api` e desce recursivamente nos que nao sao chamaveis
(`webview/util.py`, `get_functions`). Guardar a janela em `api.window` fazia ele
descer em `window.native.AccessibilityObject.Bounds.Empty.Empty.Empty...` —
`Rectangle.Empty` do .NET devolve outro `Rectangle`, entao a travessia nao
termina. A ponte nunca chegava ao JavaScript: a interface ficava em "Conectando
ao motor do bot", a janela virava "Nao esta respondendo" e o splash nao saia.

Por isso todo o estado da `Api` fica em atributos privados (`_cfg`, `_bot`,
`_window`...) e a janela entra por `bind_window()`. **Publico na `Api` deve ser
somente metodo que o JS chama.** `tests/test_api.py::BridgeSurfaceTest` replica
a regra do pywebview e falha se algum objeto voltar a vazar.

## O bot fechava sozinho (corrigido)

Foram **tres** causas, todas achadas por `crash.log` de quedas reais. Todas
apareciam como `STATUS_BREAKPOINT` (`0x80000003`) durante uma coleta de lixo, o
que enganava: a pilha aponta para quem *estava alocando* na hora, nao para quem
corrompeu a memoria. Por isso o crash parecia mudar de lugar a cada vez.

### 1. Capturador de tela por thread

```
Windows fatal exception: code 0x80000003
Current thread [Thread-144 (_call)]:  Garbage-collecting
```

`Thread-144 (_call)` e do pywebview: ele cria **uma thread nova por chamada da
ponte** (`js_bridge_call` -> `Thread(target=_call)`). O `poll` media os ratios
com `vision.skill_ratio()`, e `vision._sct()` guarda o capturador do mss em
`threading.local()` — ou seja, **um capturador novo por chamada**, so liberado
na coleta de lixo. Medido com 200 chamadas em threads separadas: **200
capturadores antes, 0 depois**.

Correcao: o `poll` nao captura tela. Quem mede e o `_loop_skills`, que vive o
tempo todo (inclusive parado, em ritmo lento, para a calibracao ao vivo).

### 2. Delegates .NET a cada resposta

O segundo crash caiu dentro do proprio pywebview:

```
Thread-144 (_call):  edgechromium.py, line 152 in evaluate_js
Current thread:      Garbage-collecting <- edgechromium.py, line 154 in <lambda>
```

Para devolver o resultado ao JS, o pywebview monta delegates .NET via pythonnet
(`Func[Object]`, `Action[Task[String]]`) e faz `Invoke` na thread de UI. A 4
chamadas por segundo, isso vira uma corrida entre o coletor do Python e o
runtime .NET.

Correcao: **a leitura de estado saiu da ponte** (`telemetry_server.py`). Um
servidor HTTP da stdlib, so em `127.0.0.1` e com token sorteado no arranque,
serve `/poll` e `/state`; a interface usa `fetch`. A ponte fica para as acoes
do usuario, que sao raras. Se o servidor nao subir, `ui/lib/api.ts` cai de
volta para a ponte, para a interface nunca ficar muda.

Medido com o exe rodando:

| | antes | depois |
|---|---|---|
| Handles no arranque | 931 | **640** |
| Handles depois de alguns minutos | 1075, subindo | **642, plano** |
| 5 min continuos | caia | sem queda, respondendo |

### 3. O capturador do mss finalizado na thread errada (causa de fundo)

Um crash caiu na thread do servidor de telemetria e outro na thread de uma
requisicao HTTP — lugares que nem existiam nas quedas anteriores. O que os dois
tinham em comum era `Garbage-collecting`, e num deles uma calibracao estava em
andamento:

```
Thread-690 (_call):  calibration.py, line 24 in sample_scores
Current thread [telemetria]:  Garbage-collecting  <- morreu aqui
```

Quem morre nao e quem causa. O `vision._sct()` guardava o mss em
`threading.local()`, e o mss segura um *device context* e um DIB do Windows,
que precisam ser devolvidos **pela mesma thread que os criou**. Nas chamadas da
ponte a thread morre logo depois: o objeto ficava orfao e quem o finalizava era
o coletor, numa thread qualquer. Isso corrompe a heap, e o estouro aparece na
proxima alocacao — em quem estivesse trabalhando naquele instante.

Correcao: **toda captura roda numa unica thread permanente** (`captura`, em
`vision.py`). Existe um so mss no processo inteiro, criado e usado sempre pela
mesma thread, e nada para finalizar. `grab()` e `grab_screen()` enfileiram o
trabalho e esperam o resultado, entao nenhum chamador precisou mudar.

Custo medido: **4,19 ms** por captura de icone contra **4,17 ms** chamando o mss
direto — 0,02 ms de fila. Com as 6 rotinas capturando ao mesmo tempo, 360
capturas levaram 1,5 s, bem acima do que o bot precisa.

`tests/test_core.py::CaptureThreadTest` falha se alguma captura voltar a rodar
na thread de quem pediu.

### 4. Uma thread por requisicao no servidor de telemetria

O `ThreadingHTTPServer` cria uma thread por requisicao. Em HTTP/1.0 o navegador
reconectava a cada 250 ms — daí os numeros altos nos logs (`Thread-655`,
`Thread-690`): milhares de threads e sockets por hora, so lixo alimentando o
coletor.

Correcao: `protocol_version = "HTTP/1.1"`, que mantem a conexao viva. Medido:
**200 consultas -> 1 thread** (antes, 200).

### 5. O que foi removido (sem mecanismo provado)

As correcoes 1 a 4 tinham causa medida. Esta nao tem, e vale registrar isso com
honestidade: **o crash continuou depois delas**. O usuario apontou que as quedas
comecaram junto com a mudanca que forcava o foco da janela do jogo, entao o
caminho suspeito foi desfeito por inteiro:

- `input_sender.find_window()` / `focus_window()` — enumeravam janelas com
  `EnumWindows` e um callback ctypes, e chamavam `SetForegroundWindow`.
  `foreground_window_title()` **fica**: e so leitura, e o bot precisa dela para
  saber se o jogo esta em foco.
- A contagem de 2 s antes do seletor (`_Countdown`) — abria uma **segunda**
  janela Tk a cada captura.
- O auto retry (rotina, atalho e o script `retry_watcher.py`) — removido a
  pedido, para diminuir o que roda em segundo plano.

Tentei antes reproduzir o mecanismo mais provavel (objetos do tkinter criados
numa thread da ponte, que morre logo depois, e finalizados pelo coletor noutra
thread). **Nao reproduziu**: o `destroy()` desfaz o ciclo de referencias e o
refcount libera tudo na thread certa. A hipotese esta descartada.

O que ficou da tentativa, porque e correto de qualquer forma: **todo o tkinter
roda numa unica thread permanente** (`seletor`, em `region_selector.py`), com
`try/finally` garantindo o `destroy()`. Mesmo padrao da thread de captura.

### Se voltar a acontecer

`crash_log.py` grava `crash.log` ao lado do executavel. Como o app roda com
`--windowed`, sem ele qualquer morte seria invisivel. Cobre os tres casos:

| Caso | Coletor |
|---|---|
| Excecao na thread principal | `sys.excepthook` |
| Excecao numa rotina do bot | `threading.excepthook` (antes a rotina morria calada) |
| Crash nativo / access violation | `faulthandler`, que imprime a pilha Python |

O log tambem marca "Bot iniciado" e "Bot encerrado normalmente", para separar
um fechamento limpo de uma queda.

Todas as chamadas Win32 declaram `argtypes`/`restype` (`input_sender.py`,
`single_instance.py`). Sem isso o ctypes trata `HWND`/`HANDLE` como int de 32
bits e trunca o handle em 64 bits — comportamento indefinido que pode derrubar
o processo.

## Nada acontece no jogo?

Aba **Ajustes** > **Diagnostico**. Ele lista, por rotina, se esta agindo ou o
motivo exato do bloqueio, mais os ratios das skills.

1. **Limite alto demais** — o ratio nunca alcanca o limite. Refaca a calibracao
   dos dois estados.
2. **Sem administrador** — se o Trove roda elevado e o bot nao, o Windows (UIPI)
   descarta o `SendInput` sem erro nenhum. O exe ja pede elevacao; pelo codigo
   use `--no-elevate` para desativar esse pedido.
3. **Jogo sem foco** — a sidebar mostra a janela em foco em verde quando bate
   com o filtro. Ligue pelo **F5** com o jogo em foco.

`--selftest` abre a janela, confere se a interface carregou e grava
`selftest.json` ao lado do exe (util quando a janela nao pode ser inspecionada
por fora, porque roda elevada).

## Testes

```
python -m unittest discover -s tests
```

152 testes: configuracao, visao (cooldown e templates), calibracao, atalhos,
rotinas do bot com input simulado (incluindo a garantia de que a tecla segurada
nunca fica presa) e a ponte `api.py`.

## Notas

- `npm audit` acusa vulnerabilidades no Next 15.3.8, todas em recursos de
  servidor (Image Optimizer, middleware/SSRF, request smuggling, Server
  Components). Aqui o app e export estatico servido em `127.0.0.1`, com
  `images.unoptimized` e sem middleware — nenhuma delas e alcancavel. A correcao
  exigiria migrar para o Next 16.
- Automatizar entradas pode violar os termos de servico do Trove. Use por sua
  conta e risco.
## Seleção de instância e input

O bot agora exige a seleção explícita da janela do jogo por HWND/PID.
O seletor aparece acima das abas. Veja [AUDITORIA_INPUT.md](../../AUDITORIA_INPUT.md)
para o diagnóstico original, os dois backends, limitações e o teste com duas
contas. Recapture as regiões antigas de skills na janela da Conta 2.
No modo Mensagens, skills continuam sem foco se os ícones ficarem visíveis.
Use `dist/background-skills/TroveAutoBot/TroveAutoBot.exe` para essa correção.

## Dois processos no mesmo bot

Use `dist/two-game/TroveAutoBot/TroveAutoBot.exe` para manter os ataques em uma
janela e enviar E periodicamente à outra. Na aba Funções, configure **Jogo 2 —
tecla periódica** (padrão: E a cada 20 segundos). Veja
[DUAS_INSTANCIAS.md](../../DUAS_INSTANCIAS.md) para seleção, controles e testes.
# Localização automática dos slots

O novo pacote `dist/auto-slots/TroveAutoBot/TroveAutoBot.exe` reconhece M2, 1 e 2
na janela de ataques selecionada e acompanha mudanças de tamanho. Na primeira
adoção das novas áreas, capture **Pronta** uma vez por slot. As calibrações são
reutilizadas depois disso. Veja [AUTO_SLOTS.md](../../AUTO_SLOTS.md) para instruções,
limites, testes e reversão. O controle separado de E do segundo jogo permanece.
