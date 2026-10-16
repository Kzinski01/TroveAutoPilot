# Segurança

Abra relatos de vulnerabilidade pela aba Security do repositório quando o canal
privado estiver disponível. Não publique tokens, configurações pessoais ou logs
com caminhos privados em issues públicas. Remova esses dados antes de anexar logs.

O escopo é um aplicativo Windows local. A seleção de processo é explícita e
revalidada antes de enviar input. Não há garantia de isolamento de ferramentas
externas que enviem input global. A telemetria usa loopback e token por execução;
não é um serviço para acesso remoto e não protege contra outros processos maliciosos
com os mesmos privilégios do usuário.

Auditoria e riscos conhecidos: [docs/AUDITORIA.md](docs/AUDITORIA.md).
Antes de uma release, execute a CI e o roteiro manual. Reavalie alertas de
dependências: a ausência de alertas é um resultado datado, não uma garantia futura.
