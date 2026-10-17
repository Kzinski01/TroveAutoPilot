# Materiais e dependências de terceiros

A licença MIT na raiz cobre o código de autoria dos contribuidores deste projeto.
Dependências, fontes e materiais do jogo preservam suas próprias licenças.

- **Logo:** o mantenedor declarou autoria própria em 16/10/2026 e autorizou a publicação.
- **Interface anterior:** o README antigo atribuía a base ao template Orbit. O mantenedor
  declarou ter permissão de redistribuição em 16/10/2026. Não havia texto de licença ou
  URL do template na pasta recebida; preserve os avisos exigidos pela licença original
  quando identificar sua edição. A auditoria não verificou essa permissão externamente.
- **Geist:** Copyright 2024 The Geist Project Authors. SIL Open Font License 1.1.
  Texto completo em [OFL.txt](ui/public/fonts/geist/OFL.txt).
- **Glass Fold:** shaders adaptados do componente de Meerbahadin no
  [21st.dev](https://21st.dev/?qt=background&preview=%2F%40meerbahadin10%2Fcomponents%2Fglass-fold),
  fornecido pelo mantenedor. Referência do autor: [GradFlow](https://gradflow.meerbahadin.dev).
  O trecho recebido não contém uma licença específica; a MIT deste projeto não
  altera os direitos do autor sobre esse material.
- **Trove:** marca, nomes e recortes da interface do jogo pertencem a seus titulares.
  `assets/skill-bar-reference.png` e `tests/fixtures/skill-bar-cooldown.png` são referências
  de reconhecimento visual e testes; a licença MIT não concede direitos sobre o jogo.
  Projeto independente, sem afiliação com o Trove.

Dependências principais: Next.js, React, Tailwind CSS e Lucide (MIT/ISC, conforme o
pacote); pywebview (BSD-3-Clause), NumPy (BSD-3-Clause), OpenCV (Apache-2.0), MSS
(MIT), pynput (LGPL-3.0), pythonnet (MIT), Bottle (MIT). Consulte os metadados e
licenças das versões instaladas para a cadeia completa. PyInstaller permite
distribuição de executáveis pela sua exceção de bootloader.

O código-fonte e o lockfile permitem reconstruir o aplicativo. Ao redistribuir
binários, inclua os textos de licença das dependências e cumpra as obrigações
aplicáveis, em especial as do pynput. `build_release.py` inclui os textos encontrados
nos metadados dos pacotes instalados em `_internal/licenses/`.
