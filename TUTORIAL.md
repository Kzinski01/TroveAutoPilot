> Registro hist?rico anterior ? revis?o de publica??o. Para comandos, estado e limites atuais, consulte [README.md](README.md) e [Auditoria](docs/AUDITORIA.md).

# Trove AutoBot — Tutorial de uso

Bot que joga junto com você no Trove: segura o clique esquerdo, solta as skills
assim que elas saem do cooldown, toma poção de tempos em tempos, fecha as
janelas que aparecem na tela (CLAIMS e convites), tudo lendo
com o servidor cair.

Ele **lê a tela** para saber quando cada skill está pronta. Por isso, antes do
primeiro uso, você precisa fazer uma calibração rápida (uma vez só).

---

## 1. Antes de começar

- **Windows 10 ou 11.** Não precisa instalar Python, Node nem nada: está tudo
  dentro do executável.
- Deixe o **Trove aberto** antes de abrir o bot.
- Use o Trove em **modo janela** ou **janela sem borda**. Em tela cheia
  exclusiva o Windows minimiza o jogo toda vez que você clica no bot.
- **Não mexa na posição da barra de skills** depois de calibrar. Se você mudar
  a resolução do jogo ou a interface, é preciso calibrar de novo.

## 2. Primeira execução

1. **Extraia o ZIP inteiro** para uma pasta (por exemplo a Área de Trabalho).
   Não rode o programa de dentro do ZIP: ele precisa dos arquivos que estão
   junto dele na pasta.
2. Entre na pasta `TroveAutoBot` e abra o `TroveAutoBot.exe`.
3. O Windows pode mostrar a tela azul **"O Windows protegeu o computador"**.
   Clique em **Mais informações** > **Executar assim mesmo**. Isso acontece
   porque o programa não tem assinatura digital paga — é normal.
4. Vai aparecer o aviso do **Controle de Conta de Usuário (UAC)** pedindo
   permissão de administrador. **Clique em Sim.**

Aparece o logo enquanto o programa carrega (cerca de 1 segundo) e depois a
janela. Se você clicar no ícone de novo por engano, ele **não abre uma segunda
cópia** — apenas traz a janela que já está aberta para a frente.

> **Por que administrador?** O Trove normalmente roda como administrador. O
> Windows não deixa um programa comum enviar teclas para um programa
> administrador — ele descarta os comandos **em silêncio**, sem erro nenhum. Se
> você recusar, o bot vai parecer que está funcionando e nada vai acontecer no
> jogo.

Se o antivírus reclamar, libere o arquivo. Executáveis feitos com PyInstaller
costumam dar falso positivo.

## 3. A tela do bot

```
+----------------+---------------------------------------------+
| Trove AutoBot  |  TÍTULO DA PÁGINA                           |
| foco: Trove    |                                             |
|                |  [ cartões com as opções da página ]        |
| > Funções      |                                             |
|   Skills       |                                             |
|   Janelas      |                                             |
|   Ajustes      |                                             |
|                |  +---------------------------------------+  |
|                |  | log de eventos                        |  |
| Desligado [ o] |  +---------------------------------------+  |
+----------------+---------------------------------------------+
```

- **foco:** no canto superior esquerdo mostra qual janela está ativa agora.
  Fica **verde** quando o Trove está na frente — que é quando o bot pode agir.
- **Desligado / Ligado** embaixo é a chave geral (master).
- O **log** embaixo conta tudo que o bot fez.

---

## 4. Calibrando as skills (a parte importante)

Vá na aba **Skills**. Você vai ver três cartões: **Slot M2**, **Slot 1** e
**Slot 2**. Faça isso em cada um:

### Passo 1 — marcar a área do ícone

Clique em **Área**. A janela do bot se minimiza e a tela escurece: arraste um
retângulo em cima do ícone da skill.

> **Deixe o jogo visível antes de clicar em Área.** O bot não força mais a
> troca de foco — ele fazia isso e passou a travar, então a troca foi removida.
> Use o jogo em **janela** ou **tela cheia sem bordas**, nunca em tela cheia
> exclusiva.

> Selecione **só o quadrado do ícone**. Não pegue a borda dourada, o número da
> contagem nem o espaço entre os ícones.

### Passo 2 — ensinar como é a skill PRONTA

Com o ícone **aceso** (skill disponível), clique em **Pronta**.

### Passo 3 — definir o limite

O **Limite** é o número na caixa ao lado da tecla: a skill dispara quando o
`ratio` alcança esse valor. Você decide qual é — o padrão é `0.80`.

Para ter uma referência, use a skill no jogo e, com o ícone **escurecido**,
clique em **Em cooldown (sugere limite)**. Isso **não muda** o seu limite:
apenas mede o ícone escuro e escreve uma sugestão no log:

```
Skill M2 [PRONTA]: 0.520 (oscilou 0.505-0.534)
Skill M2 [COOLDOWN]: 0.310 (oscilou 0.288-0.310)
  -> sugestao de limite: 0.79 (atual: 0.80). Ajuste na caixa 'Limite' se quiser.
```

Esse passo é **opcional**: só o passo 2 já é suficiente para o bot funcionar.

### Como conferir se ficou certo

No canto direito de cada cartão aparece `ratio / limite` ao vivo:

| O que aparece | Significado |
|---|---|
| `sem área` (vermelho) | falta o passo 1 |
| `falta calibrar` (vermelho) | falta o passo 2 |
| `0.98 / 0.80` **verde** | skill pronta, o bot dispararia agora |
| `0.45 / 0.80` cinza | skill em cooldown, o bot espera |

Com a skill acesa o número tem que ficar **verde**. Com ela em cooldown, tem que
ficar **cinza**. Se não mudar de cor, refaça o passo 1 selecionando só o ícone.

> **Ao escolher o limite, lembre:** os ícones do Trove brilham e piscam, então o
> número oscila sozinho cerca de 0.15. Um limite alto (0.95 ou mais) cai dentro
> dessa oscilação e a skill **nunca dispara**. O bom valor fica entre o ratio da
> skill acesa e o da skill escura — em geral perto de `0.80`.

### Campo "Tecla"

É a tecla que o bot aperta quando a skill fica pronta. Aceita:

- `1`, `2`, `3`, `q`, `r`, `t`, `shift`, `space`...
- `mouse_right` (botão direito), `mouse_left`, `mouse_middle`

---

## 5. Calibrando as janelas

Vá na aba **Janelas**. São duas: **Janela CLAIMS** e **Convite**.

### Janela CLAIMS

1. Abra a janela de CLAIMS no jogo.
2. Clique em **Capturar janela** e selecione um pedaço que **só exista nessa
   janela** — o título "CLAIMS" na barra de cima funciona muito bem.
3. Escolha o que fazer quando ela aparecer:
   - **Clicar** — depois clique em **Ponto de clique** e clique no **X** do
     canto superior direito da janela.
   - **Tecla** — digite a tecla que fecha a janela (por exemplo `l`).

### Convite

Mesma coisa: com o convite na tela, **Capturar janela** selecionando o botão
que você quer apertar (**STAY** para recusar e continuar onde está). Como o
clique cai no centro do que você capturou, não precisa marcar o ponto de clique.

Aqui também: deixe o jogo visível, com o diálogo aberto, antes de clicar.

> Se aparecer **"recorte liso demais"** no log, você selecionou uma área sem
> desenho (só fundo). O bot recusa porque uma área lisa combina com qualquer
> lugar da tela e ele acabaria clicando em qualquer canto. Selecione uma área
> com texto ou desenho.

---

## 6. Ajustes

| Opção | Para que serve |
|---|---|
| **Modo: Clicar / Segurar** | *Clicar* dispara cliques repetidos; *Segurar* mantém o botão pressionado |
| **Cliques por segundo** | Velocidade do modo Clicar (1 a 40) |
| **Poção: tecla e intervalo** | Qual tecla usar e de quantos em quantos segundos |
| **Somente com o jogo em foco** | Deixe **ligado**: o bot para sozinho quando você sai do jogo |
| **Título da janela do jogo** | Deixe `Trove` |
| **Outros títulos aceitos** | Outros nomes que a janela do jogo assume, separados por vírgula |
| **Pausar cliques com janela aberta** | Deixe **ligado**: evita clicar no jogo por baixo do diálogo |

---

## 6.1 Segurar tecla (T)

Rotina separada, na aba **Funções** > **Segurar tecla** (atalho **F10**). Ela
aperta a tecla, segura pelo tempo configurado, solta e **repete na hora**, sem
intervalo entre uma vez e outra.

### Ela é independente das outras

Marcada com o selo **independente** na tela: **não precisa do master (F5)**.
Basta o switch dela (ou o **F10**) e ela já trabalha, mesmo com todo o resto
desligado. As outras rotinas continuam precisando do master.

Configure em **Ajustes** > **Segurar tecla**:

| Campo | Padrão |
|---|---|
| **Tecla** | `t` |
| **Tempo segurando (segundos)** | `3` |

Vem **desligada** por padrão — ligue no switch ou pelo F10.

> A tecla é solta na hora se você desligar a rotina, apertar **F12** (pânico),
> sair do jogo ou fechar o bot, mesmo no meio dos 3 segundos. Assim ela nunca
> fica presa. Desligar só o master **não** interrompe esta rotina.

---

## 7. Atalhos de teclado

Funcionam **com o jogo em foco** — você não precisa sair do Trove.

| Atalho | O que faz |
|---|---|
| **F5** | Liga/desliga tudo (master) |
| **F6** | Liga/desliga o auto clique |
| **F7** | Liga/desliga as skills |
| **F8** | Liga/desliga a poção |
| **F9** | Liga/desliga as janelas |
| **F10** | Liga/desliga o "segurar tecla" |
| **F12** | Pânico: desliga tudo na hora |

Para trocar: aba **Funções**, clique no atalho e pressione a nova combinação
(pode usar `Ctrl`, `Alt`, `Shift`). Pressione `ESC` para remover.

---

## 8. Usando no dia a dia

1. Abra o Trove e entre no mapa.
2. Abra o bot e confira se as skills estão calibradas (aba Skills).
3. **Volte para o jogo** e pressione **F5**.

> Prefira ligar pelo **F5** dentro do jogo. Se você ligar clicando na chave da
> janela do bot, o jogo perde o foco e o bot fica esperando até você voltar.

Para parar: **F5** de novo, ou **F12** em caso de emergência.

---

## 8.1 Outros nomes de janela

O Trove nem sempre mantém o mesmo título: em telas de login, carregamento ou no
launcher ele pode aparecer com outro nome, e aí o bot entende que você saiu do
jogo (a sidebar mostra `foco:` em cinza).

Se isso acontecer, veja qual nome aparece na sidebar e escreva-o em
**Ajustes** > **Outros títulos aceitos**, separando por vírgula:

```
Glyph, Carregando, Trove Launcher
```

Vale qualquer **pedaço** do nome — `Glyph` já casa com "Glyph Client".

---

## 9. Se nada acontecer no jogo

Vá em **Ajustes** > **Diagnóstico** e clique em **Executar**. O log vai dizer,
para cada rotina, se ela está agindo ou exatamente o que está bloqueando:

```
Bot como administrador: sim
Janela em foco: 'Trove'
Master: DESLIGADO
  autoclick: bloqueado -> master off
  skills: bloqueado -> master off
  skill M2: ratio=0.99 limite=0.798 tecla='mouse_right'
```

Causas mais comuns, em ordem:

1. **`master off`** — aperte F5 com o jogo em foco.
2. **`sem foco (...)`** — o Trove não está na frente, ou o título da janela é
   diferente de `Trove` (mude em Ajustes).
3. **`Bot como administrador: NÃO`** — feche e abra de novo aceitando o UAC.
4. **Skills não disparam, mas o clique funciona** — o `ratio` nunca alcança o
   `limite`. Refaça a calibração dos dois estados (seção 4).
5. **`sem template`** nas janelas — falta capturar (seção 5).

---

## 10. Arquivos que o bot cria

Ficam na mesma pasta do executável (junto com os arquivos do programa):

- `config.json` — todas as suas configurações e calibrações.
- `templates/` — os recortes das janelas que você capturou.
- `crash.log` — só aparece se o bot fechar sozinho ou der erro. **Se o bot
  fechar do nada, abra esse arquivo**: a última parte dele diz o que aconteceu.

Para recomeçar do zero, feche o bot e apague esses dois. Para levar sua
configuração para outro computador **igual** (mesma resolução e mesma
interface), copie os dois junto com o exe — se a tela for diferente, calibre de
novo.

---

## Aviso

Automatizar comandos pode violar os termos de serviço do Trove e resultar em
punição na conta. Use por sua conta e risco.
