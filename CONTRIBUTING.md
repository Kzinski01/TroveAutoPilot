# Contribuir

Use Windows x64, Python 3.14 e Node 24. Instale `requirements-dev.txt` em um
ambiente virtual e execute `npm ci` em `ui/`. Os comandos completos estão no README.

Antes de enviar alterações, rode os testes Python, Ruff, lint, TypeScript e build
da interface. Use doubles de input nos testes: testes automatizados não devem
clicar no desktop ou controlar processos reais do jogo.

Mantenha as verificações de HWND/PID/instante de criação e as solturas pendentes.
Não substitua input dirigido por input global como fallback. Toda captura MSS
deve continuar na thread de captura; leituras frequentes não devem voltar para
a ponte .NET. A API é uma fachada: estado interno deve ter nomes privados.

Evite incluir `config.json`, `templates/`, logs, executáveis e capturas pessoais.
Mudanças no comportamento de input precisam de teste de regressão e validação
manual com duas instâncias. Recursos que só funcionam em foco ou com ícones
visíveis precisam informar essa condição na interface.
