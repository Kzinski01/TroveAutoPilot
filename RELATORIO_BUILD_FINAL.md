> Registro hist?rico anterior ? revis?o de publica??o. Para comandos, estado e limites atuais, consulte [README.md](README.md) e [Auditoria](docs/AUDITORIA.md).

# Revisão e distribuição final

Revisão concluída em 27/09/2026. O pacote compartilhável está em **Build Final**
e **Build Final.zip**. Os executáveis anteriores e suas configurações pessoais
permanecem nas pastas `dist`. O backup dos fontes anteriores à revisão é
`backups/before-final-review.zip`.

## Organização e comportamento

`bot.py` concentra inicialização, estado, controle das threads e a fronteira de
input. As rotinas de auto clique, skills, poção, segurar tecla e diálogos foram
extraídas para classes de responsabilidade única em `routines.py`, preservando
os métodos, intervalos e verificações existentes. O motor ficou com menos de
200 linhas. Os aliases usados pelas integrações e testes atuais foram mantidos.

`auto_slots.py` separa busca visual, transformação das regiões e confirmação da
segunda captura. Um objeto `SlotLocation` reúne os dados da captura, incluindo
sua revisão, para impedir a aplicação de uma busca invalidada durante o trabalho.

`settings_validation.py` concentra a validação dos ajustes editáveis. A ponte
continua sendo o ponto de entrada do menu; o transporte de teclado e mouse
continua em `TargetedInput`. A arquitetura não foi reescrita e não foram
alteradas as teclas, os ritmos ou os limites de detecção do usuário.

## Verificações e correções de segurança

| Área | Resultado |
|---|---|
| Destino de input | Revisadas a seleção explícita, identidade HWND/PID/criação/executável e ausência de fallback global no modo Mensagens |
| Duas instâncias | Mantida a recusa do mesmo PID nos dois destinos e o transporte independente da tecla periódica |
| Menu | Allowlist de campos editáveis; patches não podem substituir HWND, backend, ID de skill, áreas capturadas ou caminho de template |
| Valores inválidos | Números não finitos, tipos incorretos e valores fora de faixa são recusados atomicamente; estado inválido de calibração é recusado |
| Configuração | JSON com raiz/seções inválidas e números não finitos não derruba a leitura; preservada compatibilidade com flags antigas 0/1 |
| Templates | Caminhos relativos não podem escapar de `templates`; caminhos absolutos antigos existentes continuam aceitos por compatibilidade local |
| Telemetria HTTP | Somente loopback, token aleatório comparado em tempo constante, validação de Host e Origin, sem CORS `*`, somente rotas de leitura |
| Erros HTTP | Exceções internas não são devolvidas ao cliente; respostas têm `no-store` e `nosniff`; conexões inativas têm timeout |
| Memória e encerramento | Fila de logs pendentes limitada a 400 linhas; servidor encerrado com fechamento do socket |
| Diagnóstico | Selftest oculto, sem iniciar rotinas, sem registrar atalhos e sem ocupar o mutex do bot normal |

A revisão não equivale a uma garantia de ausência de vulnerabilidades. O modo
Compatibilidade usa input global com verificações de foco e continua sujeito à
corrida inerente à mudança de foco do Windows; o pacote final começa no modo
Mensagens. PostMessage só funciona se o jogo aceitar as mensagens. A leitura de
skills continua exigindo pixels visíveis, e a validação de obstruções usa pontos,
não uma prova de visibilidade de cada pixel. Não há injeção no processo do jogo.

## Dependências

NPM inicialmente apontou alertas em dependências da interface. Next foi
atualizado para **15.5.26**, PostCSS para **8.5.28**, e foram fixadas resoluções
compatíveis de PostCSS e Sharp (`^0.35.4`) no lockfile. A aplicação continua sendo
uma exportação estática; um servidor Next/Node não acompanha o bot.

Após as atualizações, `npm audit` reportou **zero vulnerabilidades conhecidas**,
incluindo as dependências de desenvolvimento. `pip-audit` reportou **zero
vulnerabilidades conhecidas** nos 13 pacotes Python do fechamento de dependências
de execução. As versões auditadas estão em `requirements-lock.txt`.

Evidências: `build/npm-audit-before.json`, `build/npm-audit-final.json` e
`build/python-audit.json`. Os scanners verificam avisos conhecidos de pacotes;
não certificam todas as bibliotecas nativas nem o WebView2 instalado no computador
de quem receber o programa.

## Validação

- **278 testes automatizados passaram**, incluindo isolamento de janelas,
  ataques, tecla periódica, localização visual e os novos limites de segurança.
- Build estático da interface passou em Next 15.5.26.
- Build Windows de 64 bits passou em PyInstaller 6.21.0 / Python 3.14.6.
- O ZIP é verificado por CRC e por comparação dos bytes de cada arquivo com a
  pasta final. O SHA-256 está em `Build Final.zip.sha256`.
- O diagnóstico nativo roda em uma cópia em `build`, sem modificar a pasta
  compartilhável nem enviar comandos aos jogos. O executável final abriu a
  interface estilizada, carregou a ponte e confirmou uma resposta HTTP de estado
  pela origem real do WebView2: `telemetry_ok: true`, encerrando com código 0.
  Evidência: `build/final-native-check-verified/selftest.json`.

ZIP final: 72.193.767 bytes. SHA-256:
`2818438eacd2bc2c7770cb883a6dfeb70a2293878e0d31723787e8722be8874d`.

## Conteúdo compartilhável

```
Build Final/
    TroveAutoBot.exe
    config.json
    _internal/
```

`_internal` contém Python, DLLs, dependências, recursos e a interface compilada
necessários ao executável, incluindo arquivos auxiliares dos fornecedores.
Não deve ser removida nem separada do EXE. Não acompanham o ZIP os fontes do
projeto, testes, ferramentas de auditoria, backups, node_modules, capturas,
logs, relatórios ou configurações pessoais.

A configuração é criada a partir dos defaults, não copiada do bot do usuário:
nenhum HWND/PID/caminho de processo salvo, nenhuma área ou amostra de calibração,
e todas as rotinas de ação desligadas. Localização automática ligada e backend
Mensagens. Cada pessoa escolhe suas janelas e calibra Pronta uma vez por slot.

Para enviar: compartilhe **Build Final.zip**. Quem receber deve extrair tudo
antes de abrir `Build Final/TroveAutoBot.exe`. Não precisa instalar Python ou
Node; precisa de Windows de 64 bits e do runtime WebView2 compatível. Templates,
configuração e logs são criados/atualizados pelo programa durante o uso.

Para gerar novamente: preserve/mova os arquivos Build Final anteriores e rode
`python build_release.py`. O script executa os testes, compila a interface,
empacota somente a saída de execução, gera configuração limpa e verifica o ZIP.

## Arquivos da revisão

| Arquivo | Alteração |
|---|---|
| `routines.py` (novo), `bot.py` | Separação das rotinas e do ciclo de vida |
| `auto_slots.py` | Etapas menores e objeto com o resultado da captura |
| `settings_validation.py` (novo), `api.py` | Validação central, patches limitados e logs limitados |
| `config.py` | Leitura estrutural defensiva e contenção de paths relativos |
| `telemetry_server.py` | Host/Origin/token, respostas e conexões |
| `main.py` | Fechamento do servidor e diagnóstico sem ações de jogo |
| `ui/package.json`, `ui/package-lock.json` | Atualizações de dependências e resoluções auditadas |
| `requirements-lock.txt` (novo) | Versões Python de execução auditadas |
| `build_release.py` (novo) | Distribuição limpa e ZIP verificável |
| `tests/test_security.py`, `tests/test_release.py` (novos), `tests/test_api.py` | Cobertura de segurança, distribuição e fechamento dos sockets de teste |
