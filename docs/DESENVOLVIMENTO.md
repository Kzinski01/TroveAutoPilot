# Desenvolvimento

## Executar pelo código

No PowerShell, na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Push-Location ui
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe main.py
```

Use o lockfile para reproduzir o ambiente auditado. `requirements.txt` lista apenas requisitos mínimos e não representa um ambiente auditado/reproduzível.

`config.json` e `templates/` são gerados localmente, ao lado do código ou executável. Cada pessoa escolhe suas próprias janelas e calibra suas skills. Handles salvos nunca ativam uma janela automaticamente no próximo arranque.

## Desenvolvimento da interface

```powershell
cd ui
npm ci
npm run dev
```

Acesse `http://localhost:3000/?preview=1` para uma **prévia com dados de exemplo e ações desativadas**. Sem esse parâmetro, o navegador informa que o motor não está conectado. O aplicativo desktop usa o build estático de `ui/out/`.

Fundo Glass Fold azul, foco de teclado visível e suporte a movimento reduzido. [Interface](DESIGN.md).

## Verificar e gerar executável

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
python -m ruff check .
python -m pip_audit -r requirements-lock.txt --no-deps --disable-pip
python -m bandit -q -r . -x './.venv,./.audit-venv,./ui,./build,./dist,./release,./release-audit,./Build Final,./tests,./backups' -ll
Push-Location ui
npm run lint
npm run typecheck
npm audit --omit=dev
npm run build
Pop-Location
python build_release.py --skip-ui --output-dir release-audit
```

O pacote é uma **pasta**, não um executável isolado: mantenha `_internal` ao lado de `TroveAutoBot.exe`. O build gera configuração limpa, ZIP e SHA-256, inclui licenças e recusa sobrescrever uma distribuição anterior. Para um build comum, use `python build.py`.

Mantenha também **`TroveAutoBot.exe.config` ao lado do EXE**. Esse arquivo configura
o carregador .NET do aplicativo para aceitar suas DLLs locais quando o Windows
as marca como baixadas da internet. Sem ele, uma extração pelo Explorador pode
falhar com `Failed to resolve Python.Runtime.Loader.Initialize`.

O build de release agora extrai o ZIP em uma pasta temporária, adiciona a marca
de download (`ZoneId=3`) aos arquivos e exige um selftest aprovado. Para repetir:
`python release_smoke.py 'release-audit/Build Final.zip'`.

A verificação `TroveAutoBot.exe --selftest` carrega a interface e a telemetria sem iniciar rotinas ou registrar atalhos de jogo. Não valida a aceitação de input pelo Trove. [Roteiro de teste com duas instâncias](VALIDACAO_MANUAL.md).
