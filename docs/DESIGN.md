# Interface Midnight Galaxy

Tema escolhido pelo mantenedor em 16/10/2026, após apresentação do catálogo da
[theme-factory](https://github.com/anthropics/skills/tree/main/skills/theme-factory).
Revisão orientada também por
[frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design).

## Plano e revisão

O aplicativo é um painel compacto de automação para quem acompanha duas janelas
do Trove. A prioridade visual é identificar destinos, estado do motor e parada
geral. Não há contagens inventadas ou indicadores de sucesso de input sem prova.

Paleta: fundo `#171221`, superfície `#21182f`, roxo profundo `#2b1e3e`, azul
cósmico `#4a4e8f`, lavanda `#a490c2`, texto prata `#e6e6fa`. Os tokens CSS
usam aproximações HSL dessas cores, com tons auxiliares para bordas e textos.
Foi mantida a Geist local já embutida, com sua licença OFL, como adaptação
tipográfica do tema: nenhuma fonte é carregada da rede.

```text
Navegação | Título e conexão
          | Jogo 1 / Jogo 2
          | Seleção de destino
          | Controles da aba (rolagem)
Master    | Atividade (recolhível)
Parar tudo|
```

A proposta inicial de cartões de métricas decorativas foi descartada: não
ajudava a escolher os processos. Os dois resumos exibem os destinos reais. A
marca de blocos é uma referência discreta ao mundo voxel do jogo; o restante
usa linhas e hierarquia simples. As referências [Spell](https://spell.sh/),
[21st](https://21st.dev/) e [Inspora](https://www.inspora.design/) orientaram a
qualidade de acabamento, sem copiar componentes ou introduzir código remoto.

## Implementação

- Navegação com página atual e foco de teclado visível.
- Parada geral acessível pela barra lateral, além do atalho configurado.
- Cores e switches alinhados ao tema; botão ativo com contraste escuro.
- Log recolhível e selecionável, estados de espera, erro e desconexão explícitos.
- Prévia opt-in (`?preview=1`), sem ponte de input e com ações desabilitadas.
- Navegação compacta em telas pequenas; campos e linhas quebram sem perder controles.
- Preferência de movimento reduzido respeitada.

A revisão visual usa a prévia sem ações e o selftest da janela nativa. A prévia
não representa uma sessão conectada a processos reais.
