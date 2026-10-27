# Resultados e limites de evidência

Este projeto é desenvolvido nas aulas de **Introdução à Inteligência Artificial**. A investigação originou um artigo curto em desenvolvimento para o SBMSB. Demonstração didática, teste de software e resultado científico são evidências diferentes.

## Teste digital completo

Modelo INT8 SHA256 `3b7e258e26ca124d9e973ba8b4ac5744c87c3ed1d41f501192d2ca7a0b185454`. Limiar congelado: 0,7346754807692307. CirCor DigiScope 1.0.3, classes Present/Absent, Unknown excluído, split por identidades/grupos vinculados.

6.512 janelas, 471 gravações, 122 grupos, com 24 positivos e 98 negativos. Métricas agregadas por grupo:

| Execução | F1 | Recall | Accuracy | TP/FN/FP/TN |
|---|---:|---:|---:|---|
| PC float | 0,694 | 0,708 | 0,877 | 17/7/8/90 |
| PC INT8 otimizado | 0,680 | 0,708 | 0,869 | 17/7/9/89 |
| PC INT8 referência | 0,694 | 0,708 | 0,877 | 17/7/8/90 |
| RP2040 INT8 | 0,694 | 0,708 | 0,877 | 17/7/8/90 |

F1 IC95%: 0,526–0,829, bootstrap por grupo, 2.000 replicações, seed 2026. A coorte positiva é pequena e a incerteza é ampla.

As decisões da placa coincidiram com a referência nos 122 grupos. Houve 86 janelas com CRC de features diferente e 160 com probabilidade diferente, máximo de 0,0078125 contra a referência. Os tensores completos dessas 86 janelas não foram retidos. Não há alegação de paridade bit a bit nem de melhoria do modelo pela placa.

## Tempo

No teste completo do RP2040, medianas em ms: MFE 1.006,536; inferência 311,868; combinado 1.318,405. Exclui aquisição, USB, CRC, display e inicialização.

Um ensaio suplementar de CPU usou as mesmas 100 janelas de validação de um benchmark histórico da placa:

| Etapa | PC mediana (ms) | Placa mediana (ms) |
|---|---:|---:|
| MFE | 0,237 | 1.006,545 |
| Inferência | 2,425 | 311,868 |
| Combinado | 2,687 | 1.318,421 |

PC: LiteRT BUILTIN_REF, CPU, uma thread, MFE NumPy. Placa: TFLite Micro, C++, RP2040 a 133 MHz. Medidas não simultâneas e implementações diferentes. Não é speedup isolado de hardware/quantização e não usa a RTX.

A reorganização do aplicativo não repetiu nem substituiu esses benchmarks. Os testes de regressão conferem compatibilidade dos exemplos, sem gerar novas métricas de coorte ou tempo.

## Recursos do firmware científico histórico

Modelo: 5.264 bytes. Imagem flash: 189.408 bytes. Espaço estático principal de SRAM: 186.224 bytes. Arena já incluída na reserva, sem soma dupla. Pico de RAM e watermark de pilha desconhecidos.

Demo V3 histórica: imagem flash 255.512 bytes; compilada e auditada, confirmação física USB pendente nos registros. O novo layout CMake exige build novo. Os recursos da demonstração não substituem os do firmware científico.

## Proveniência publicável

As cópias curadas em `src/heart_tinyml/resources/evidence` conservam as métricas e identificadores. O relatório suplementar teve caminhos locais omitidos e registra o SHA256 do relatório original. Diários brutos, diretórios de máquina e a base completa permanecem fora deste repositório.

Os originais locais foram preservados durante a migração. Não foi refeito treinamento, retunado limiar ou reescrito um diário científico.

## O que permanece pendente

Validação acústica do microfone, aquisição contínua, pico de RAM, robustez a ruídos/entradas não cardíacas, avaliação clínica e confirmação física da versão reorganizada. A prévia de um escore não é uma probabilidade clínica calibrada.
