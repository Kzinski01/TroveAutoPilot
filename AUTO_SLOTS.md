> Registro hist?rico anterior ? revis?o de publica??o. Para comandos, estado e limites atuais, consulte [README.md](README.md) e [Auditoria](docs/AUDITORIA.md).

# Localização automática de M2, 1 e 2

O pacote está em `dist/auto-slots/TroveAutoBot/TroveAutoBot.exe`. Feche o bot
anterior antes de abrir este. Os ajustes e templates do pacote `two-game` são
copiados para o novo pacote; os executáveis anteriores permanecem disponíveis.

## Usar

1. Selecione a instância de ataques em **Jogo 1**, como antes. Para operar sem
   foco, mantenha o backend **Mensagens à janela**.
2. Na aba **Skills**, deixe **Localizar automaticamente** ligado. No novo pacote
   ele vem ligado. Ao executar os fontes, ele é opcional e começa desligado
   para preservar o modo manual das configurações antigas.
3. Deixe a barra M2/1/2 visível. O bot reconhece os três rótulos juntos e
   preenche as áreas, sem arrastar retângulos. **Localizar agora** minimiza o
   menu temporariamente para repetir a busca, sem forçar foco no jogo.
4. Na primeira adoção das novas áreas, aguarde as três skills ficarem prontas
   e clique **Pronta** em cada slot. Isso estabelece a base de brilho da nova
   área. Não há ataque de teste nem suposição automática de estado pronto.
   A amostra antiga de um recorte manual diferente não é reutilizada.
5. As próximas aberturas e mudanças de tamanho localizam a barra novamente e
   preservam a calibração salva, as teclas, limites e intervalos. Escolha a
   instância explicitamente em cada abertura. A rotina E do Jogo 2 segue igual.

Você não precisa selecionar as áreas novamente ao alternar entre tela cheia e
meia tela. Mantenha a barra exposta, inclusive ao posicionar o menu do bot.
Trocar de classe, tema ou escala da interface pode exigir nova captura de
**Pronta** e ajuste do limite, porque altera os pixels usados no cooldown.
O botão **Área** desliga a localização automática e permite voltar ao modo
manual; sua captura manual continua funcionando como antes.

## Como reconhece e protege

O detector usa uma referência que já existia no projeto, agora distribuída
como `assets/skill-bar-reference.png`. Com OpenCV, procura os rótulos brancos
M2, 1 e 2 na metade inferior da área cliente, em várias escalas (0,65 a 2 vezes
a referência). Os três precisam estar na mesma linha e no espaçamento esperado.
Ele não depende do desenho colorido da skill nem multiplica coordenadas antigas
pelo tamanho da janela. A escala é estimada pelo reconhecimento visual.

A busca completa acontece ao iniciar, trocar a janela, redimensionar ou perder
a barra conhecida. A cada 1,5 segundo, o detector verifica uma pequena área
próxima à última posição. Isso limita o custo de captura e processamento.
Uma alteração da área cliente bloqueia imediatamente a leitura antiga, antes
da nova identificação. A busca completa inicial pode atrasar por cerca de um
segundo o ciclo de skills; as demais rotinas têm suas próprias threads.

Antes de aplicar as três regiões, confirma a barra em uma segunda captura,
revalida HWND/PID/criação do processo, posição/tamanho da janela e a visibilidade
dos pontos da barra e das áreas. Uma captura invalidada por troca de seleção,
desativação ou encerramento não pode aplicar seu resultado depois disso.

Não reconhecer, reconhecer duas barras, detectar uma sobreposição ou minimizar
a janela pausa as skills. Não existe fallback para coordenadas estimadas. O
detector não envia teclado/mouse, não ativa E, não troca o foco e não seleciona
outro processo. O envio continua passando pelas proteções de `TargetedInput`.

Há limites: os rótulos precisam permanecer M2/1/2, a barra deve estar na metade
inferior e sua aparência/escala deve corresponder às referências suportadas.
Uma interface personalizada ou renderização diferente pode não ser reconhecida;
nesse caso, use o modo manual. As verificações de visibilidade reaproveitam a
checagem por pontos do projeto, não uma prova de visibilidade de cada pixel.

Logs usam `[Bot][Slots]` e mostram o resultado, motivo de pausa, HWND, PID,
escala e confiança da correspondência. Confiança visual não mede o estado de
cooldown: este continua usando a calibração de brilho e o limite configurado.

## Testar e reverter

Com os ataques desligados, selecione a janela e confira os três retângulos
indicados na aba Skills. Capture Pronta uma vez, ligue as skills e alterne entre
tela cheia e meia tela. As áreas devem mudar sem alterar o destino ou enviar
comandos ao Jogo 2. Cubra a barra ou minimize o jogo: o status deve indicar pausa.
Remova a obstrução: a identificação e a leitura devem ser retomadas.

Testes automatizados cobrem escalas, ordem errada, rótulo isolado, barras
ambíguas, números de cooldown de um recorte real, fechamento, minimização,
troca de processo, sobreposição e mudança da janela durante as capturas.
Todos esses testes substituem o transporte de input. Também foi verificada
a localização nas duas janelas reais lado a lado, somente com leitura.
Os 253 testes da suíte passaram, e os builds da interface e do executável
foram concluídos. O novo pacote não foi aberto sobre o bot anterior em execução.

| Arquivo | Alteração |
|---|---|
| `slot_detection.py` (novo) | Reconhecimento visual dos três rótulos e validação de ambiguidade |
| `auto_slots.py` (novo) | Busca automática, confirmação e associação à janela escolhida |
| `bot.py` | Atualiza a localização no loop de skills e bloqueia leituras não validadas |
| `api.py` | Switch, botão Localizar agora, telemetria e retorno ao modo manual |
| `config.py` | Persiste a opção de localização automática |
| `ui/components/pages/skills-page.tsx` | Controles, status, confiança e áreas atualizadas ao vivo |
| `ui/lib/api.ts`, `ui/types/index.ts` | Contrato das novas ações e estado |
| `build.py`, `assets/skill-bar-reference.png` | Referência visual incluída no executável |
| `tests/test_auto_slots.py`, `tests/fixtures/skill-bar-cooldown.png` | Testes de reconhecimento e isolamento |

Para reverter o comportamento, desligue o switch e use **Área**. Para voltar à
versão anterior completa, abra `dist/two-game/TroveAutoBot/TroveAutoBot.exe`.
O backup dos fontes anteriores está em `backups/before-auto-slots.zip`.
