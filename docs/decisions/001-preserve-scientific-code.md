# ADR 001: separar aplicação didática e pipeline científico

Estado: adotado em 27/10/2026.

## Contexto

O workspace misturava scripts de máquina, versões da demonstração, dependências, dados e resultados. Os experimentos encerrados têm fontes e hashes congelados, que não podem ser silenciosamente substituídos por uma refatoração.

## Decisão

Criar um pacote instalável `heart_tinyml` para a aplicação atual, manter `research/pcg` como pipeline histórico separado e organizar os programas C++ sob um único CMake. Copiar somente os recursos necessários e evidências curadas ao repositório publicável.

## Consequências

A aplicação pode evoluir com contratos, adapters e testes de unidade. A semântica dos exemplos foi conferida por escores congelados. A rotina MFE histórica permanece no pipeline científico, com duplicação pequena e delimitada, para conservar o mecanismo de snapshots e retomada.

Não se misturam diários antigos com novas fontes. Alterações no protocolo de pesquisa exigem novo experimento. Um novo build ou teste físico deve ser identificado separadamente das medidas históricas.
