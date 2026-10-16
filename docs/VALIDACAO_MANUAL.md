# Validação de uma release com o jogo

Este roteiro exige duas instâncias reais do Trove. Não foi executado durante a
auditoria: os testes de input usam doubles; o selftest verifica carregamento e
telemetria sem iniciar automação.

1. Em um Windows limpo, extraia a pasta completa do ZIP e abra o executável.
   Confirme WebView2, tela inicial e ausência de seleção automática de handles antigos.
   Use uma cópia baixada pelo navegador e extraída pelo Explorador, mantendo
   `TroveAutoBot.exe.config` junto do EXE. A aplicação deve abrir mesmo quando
   as DLLs recebem `Zone.Identifier` com `ZoneId=3`.
2. Abra dois processos do jogo. Confirme que os seletores listam PIDs diferentes
   e que selecionar o mesmo processo nos dois controles é recusado.
3. No Jogo 1, teste auto clique e skills em Compatibilidade. Tire o foco:
   os ataques devem parar. Retorne à janela e confirme a soltura pendente.
4. Teste Mensagens. Verifique dentro do jogo se os comandos são aceitos:
   mensagem enfileirada no Windows não comprova ação dentro do Trove.
5. Calibre cada slot pronto, confirme ratios e cooldowns, mova e redimensione
   a janela. Cubra os ícones e minimize: a leitura deve pausar.
6. No Jogo 2, teste E em intervalo conhecido. O primeiro envio ocorre após
   o intervalo; desligar o master do Jogo 1 não desliga essa rotina.
7. Com uma tecla segurada e o Jogo 2 ativo, use F12 e o botão Parar tudo.
   Confirme a parada das duas rotinas. Segurar um atalho não deve oscilar o estado.
8. Feche e reabra um processo do jogo: handles/PIDs reaproveitados não devem
   ser aceitos sem nova seleção. Abra duas cópias do bot: só uma deve controlar o jogo.
9. Capture Claim/convite, calibre o clique e teste com resolução/escala do usuário.
   Confirme que a ação fica dentro da janela escolhida.
10. Faça uma sessão prolongada, incluindo troca de foco, UAC e fechamento fora
    de foco. Verifique teclas presas, crash.log e consumo de recursos.

Registre versão do Windows, escala DPI, resolução, build do Trove, modo de
input, SHA-256 do ZIP e resultados por etapa antes de declarar a release
validada no jogo.
