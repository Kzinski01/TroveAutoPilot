# Auditoria de segurança, funcionamento e publicação

Data: **16/10/2026**. Ambiente: Windows 11 x64, Python 3.14.6, Node 24.16.0.
Escopo: código Python, fronteira Win32 de input, dois processos, ponte pywebview,
telemetria HTTP, configuração, dependências, frontend, build e preparação do GitHub.

## Parecer

O código pode ser publicado com os limites abaixo documentados. A pasta original
não deveria ser enviada inteira: continha configurações pessoais, logs, backups
e binários antigos, sem `.gitignore`, licença ou CI. Não havia repositório Git
local; o destino informado pelo mantenedor estava vazio.

Os bloqueios de publicação do código e os defeitos reproduzidos foram tratados.
Isso **não certifica funcionamento integral no Trove**: não foi feita uma sessão
com dois processos reais nem teste prolongado no jogo nesta auditoria. A aceitação
de mensagens de input pelo jogo permanece experimental. O roteiro para concluir
essa validação está em [VALIDACAO_MANUAL.md](VALIDACAO_MANUAL.md).

## Achados e correções

| Prioridade | Achado | Correção e evidência |
|---|---|---|
| Alta, publicação | Configuração, capturas pessoais, logs e builds poderiam entrar no primeiro commit | `.gitignore`, revisão dos arquivos preparados para Git e configuração limpa de distribuição; dados locais preservados |
| Média | Números negativos e bindings malformados no JSON podiam matar rotinas ou causar exceções ao ler skills | `config_validation.py`, reparo por campo e testes de JSON malformado, região e botão inválidos |
| Média | Lista usada como ID de skill causava erro de chave não hashable no carregamento | IDs salvos são filtrados por tipo; teste de regressão |
| Média | Repetição do teclado criava callbacks/threads e alternava o master enquanto o atalho era segurado | Um disparo por keydown até keyup; teste com 100 repetições |
| Média | Atalho duplicado de rotina podia substituir o pânico | Novas duplicatas recusadas e pânico tem prioridade em configurações antigas |
| Média | Capturas concorrentes podiam restaurar input enquanto outra calibração continuava aberta | Lock próprio serializa a operação inteira; teste de concorrência |
| Média | Falha ao criar MSS encerrava a thread antes de responder à captura | Inicialização responde com erro ao pedido e permite nova tentativa; espera limitada a 10 s |
| Média | Verificação de dependências não incluía pywebview | Bootstrap detecta sua ausência antes de importar a interface |
| Média | String `"false"` era verdadeira na coerção de controles da API | Ativação exige booleanos reais; teste cobre master, tecla segurada, slots e Jogo 2 |
| Média | Switches usavam snapshot antigo após alterações por atalhos | Estado de features exibido pela telemetria; exercício no navegador com ponte simulada |
| Média | Falha de telemetria podia voltar a 4 chamadas/s na ponte associada aos crashes anteriores | Timeout HTTP e reconexão sem fallback frequente quando o endpoint já foi estabelecido |
| Baixa | Espera pela ponte ficava sem fim e sobrevivia à desmontagem do componente | Timeout, cancelamento, mensagem de orientação e prévia explícita sem ações |
| Baixa | Build usava shell sem necessidade e instalação sem lockfile npm | Resolução explícita do executável e `npm ci` |
| Baixa | Resolução de template permitia arquivo absoluto externo existente | Migração pelo nome e confinamento à pasta `templates/` |
| Publicação | README contraditório e comandos de pacotes antigos | README reescrito, histórico preservado, licença MIT autorizada, avisos, CI Windows e Dependabot |

Refatoração dirigida: validação de configuração extraída da persistência, captura
da API dividida em coordenação e execução, imports explícitos e lint reproduzível.
O desenho das rotinas e a fachada pública da API foram mantidos para preservar
compatibilidade da ponte e das salvaguardas de input.

## Dependências

- **Python:** `pip-audit` sobre todas as entradas de `requirements-lock.txt`, sem
  resolução adicional, retornou **zero vulnerabilidades conhecidas**. Uma nova
  `.venv` instalou o lockfile e executou a suíte. As versões são fixas, mas o
  arquivo Python ainda não contém hashes dos wheels.
- **Frontend de produção:** `npm audit --omit=dev` retornou **zero alertas**.
- **Frontend completo:** nove alertas no início; após correções disponíveis,
  **sete entradas de gravidade alta**, todas em dependências de desenvolvimento
  que chegam a `braces` via Tailwind 3 e ferramentas ESLint. Não há correção
  publicada de `braces` na data consultada. A migração de Tailwind exige uma
  revisão própria e não foi aplicada automaticamente por `audit fix --force`.
- Next atualizado para **15.5.28**, `source-map-js` atualizado e parser PostCSS
  fixado em **7.1.6**. O projeto continua com export estático, sem servidor Next
  em produção. Tailwind e seu plugin de animações ficam em devDependencies.

O risco remanescente envolve padrões de glob não confiáveis durante ferramentas
de build/lint; o executável distribui HTML/CSS/JS já compilados e não executa
essas ferramentas. Não use esse ambiente para compilar projetos de origem
desconhecida. A CI reprova vulnerabilidades de produção e mostra a auditoria
completa sem ocultar os alertas de desenvolvimento.

Fontes consultadas:
[braces sem versão corrigida](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm),
[parser PostCSS](https://github.com/advisories/GHSA-rj75-hqrm-r3gf),
[Next SSG/ISR](https://github.com/advisories/GHSA-4jqv-mc3x-m676).

## Verificações executadas

| Verificação | Resultado |
|---|---|
| Suíte inicial | 278 testes passaram |
| Suíte final, incluindo regressões | 290 testes passaram |
| Instalação isolada Windows/Python 3.14 | Lockfile instalado e suíte aprovada |
| Ruff, incluindo testes | Sem erros |
| ESLint, sem warnings permitidos | Aprovado |
| TypeScript | Aprovado |
| Build/export Next.js | Aprovado |
| pip-audit do runtime fixado | Zero alertas conhecidos |
| npm audit produção | Zero alertas conhecidos |
| Bandit | Nenhum achado médio/alto; achados baixos revisados: placeholders vazios de token e subprocessos com argumentos controlados |
| Navegador: quatro abas | Revisão visual em prévia sem input |
| Layout: 1040, 920 e 390 px | Sem elementos do conteúdo excedendo a largura nos layouts examinados |
| Frontend: master, pânico e mudança de feature pela telemetria | Aprovado com ponte simulada, sem eventos reais de input |
| Build Windows/PyInstaller | Pasta, ZIP e SHA-256 gerados, com configuração limpa |
| Executável `--selftest` | Ponte `object`, CSS `rgb(23, 18, 33)`, telemetria aprovada |

O teste da interface nativa (`--selftest`) verifica CSS, ponte e telemetria e
não inicia workers nem atalhos de jogo. Seu resultado é registrado no pacote
local e é excluído do Git. Não deve ser confundido com o roteiro no jogo.

## Riscos e limites remanescentes

1. **Input global:** em Compatibilidade há uma janela de corrida entre conferir
   foco e chamar SendInput. Não é possível garantir isolamento atômico nessa API.
   Solturas são adiadas quando o alvo perde foco para não atingir outra conta;
   fechar o aplicativo nessa condição pode exigir soltura física pelo usuário.
2. **Mensagens:** PostMessage retornar sucesso indica enfileiramento, sem prova
   de que o Trove aceitou o comando. Versão do jogo, UAC e modo de janela afetam
   o resultado. Não foi criado fallback global para contornar essa limitação.
3. **Visão:** MSS captura pixels visíveis, não o framebuffer isolado do processo.
   Oclusão, minimização, DPI e mudança de classe exigem as travas/calibração
   existentes. Não há promessa de skills funcionais com o jogo oculto.
4. **Serviços locais:** token efêmero, validação de Host/Origin, loopback e
   allowlist de rotas foram inspecionados/testados. Isso não protege de malware
   local com os mesmos privilégios, nem transforma a stdlib HTTP em serviço
   adequado à exposição externa. O app roda elevado por compatibilidade de input.
5. **Licenças:** MIT autorizada para o código próprio; autoria do logo e permissão
   de redistribuição Orbit declaradas pelo mantenedor. A licença original Orbit
   não foi fornecida para conferência. Imagens e marcas do jogo não são
   relicenciadas como MIT. Veja [avisos](../THIRD_PARTY_NOTICES.md).
6. **Credenciais:** busca por padrões comuns de tokens/chaves não encontrou
   segredos no conjunto de fonte revisado. Não é prova de ausência de todo
   segredo possível. Configuração e logs de sessões reais não vão para o Git.

Os ZIPs antigos da pasta original não foram substituídos nem passam a representar
esta revisão. O novo pacote está em `release-audit/validated/`; binários não são
incluídos no histórico do repositório.
