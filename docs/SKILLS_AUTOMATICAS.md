# Skills automáticas

1. Selecione a janela em Jogo 1 e clique em Detectar skills.
2. Deixe os ícones visíveis, ative Skills e ligue os ataques com F5.
3. O app faz tentativas com pelo menos 2s de intervalo. Ao observar o cooldown e o retorno do ícone, passa a usar a leitura visual para decidir os próximos comandos.

O aprendizado é separado por skill, processo, tecla e área da tela. Ele recomeça a cada sessão. Se o app começar com uma skill em cooldown, pode precisar acompanhar mais de um uso. Trocas de classe que alterem o ícone também exigem novo aprendizado; Reaprender skills permite reiniciá-lo.

## Cooldown variável

A rotina compara novas imagens com o estado aprendido. O tempo do último ciclo serve apenas como informação: não determina o próximo disparo. Uma poção ou outra skill pode antecipar o retorno, desde que a imagem confirme que a skill ficou pronta.

A comparação exige várias amostras consistentes para filtrar oscilações e reconhece números de cooldown mesmo com pouca redução de brilho. Existe um pequeno atraso de leitura e uma pausa mínima entre comandos.

Após cada envio, o app procura uma resposta no ícone. Se ela não ocorrer, avisa e repete a tentativa com pelo menos 2s de intervalo; uma pausa configurada maior também é respeitada. Tentativa enviada não confirma que o Trove aceitou o comando. Confira o modo de envio em Ajustes nesses casos.

## Ícones encobertos

Janelas sobre a barra pausam a leitura e geram um aviso no app. Mova a janela que estiver cobrindo os ícones, inclusive o próprio AutoPilot. Ao voltar a ver a barra, o app coleta novas amostras antes de retomar.

O aviso de ícone encoberto exige uma janela sobre a área usada na leitura. Falha de reconhecimento, área fora dos limites e janela indisponível têm mensagens diferentes. Espaços vazios ao redor dos ícones não bloqueiam a rotina, e o app procura a nova posição se a barra mudar de lugar.

## Limites

A leitura usa pixels da tela; não consulta o estado interno do Trove. Efeitos visuais, modificações da interface e skills sem cooldown visível podem impedir o aprendizado. Nesses casos, o app mantém as tentativas espaçadas enquanto a rotina estiver ativa e o ícone estiver estável e visível. É possível desligar o modo automático e usar as capturas manuais nos ajustes avançados de cada skill.

Os testes usam sequências de imagens e uma ponte simulada. O comportamento de cada classe e a aceitação de comandos precisam ser conferidos [no jogo](VALIDACAO_MANUAL.md).
