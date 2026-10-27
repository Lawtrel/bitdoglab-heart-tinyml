# Novo benchmark: CPU, RTX, Float32 e INT8

Medido em 27/10/2026. Não houve novo training, seleção de threshold ou retuning no test set. O teste científico original permanece separado.

## Protocolo

Mesmas 100 primeiras windows de 3 segundos do benchmark histórico de validation; 10 warm-up calls por modo; 3 repetições com ordens de NumPy seeds 20261027, 20261028 e 20261029; batch size 1. Os modos foram executados em ordem fixa: CPU Float32 TensorFlow, GPU Float32 TensorFlow, CPU Float32 reference, CPU INT8 reference e RP2040 INT8. As 300 chamadas por modo não são 300 pacientes independentes.

TensorFlow 2.21 usa intra/inter threads = 1, TF32 desabilitado e sem silent fallback de GPU. A criação/upload do input é excluída de inference; a chamada do grafo e output.numpy sincronizado entram no timer. O MFE do modo GPU permanece na CPU. O tempo incluindo criação/transferência também foi retido nas linhas individuais. No par de quantization, TFLite 2.21 BUILTIN_REF usa uma thread e mede Invoke; o novo Float32 export passou comparação com o modelo CPU nas 100 entradas (máximo 4,77e-7; atol/rtol 1e-5).

Na placa, a demo V3 compilada em 24/10/2026 foi gravada com UF2 SHA256 2215829d1676412c81d22e838abd384369c7dd9258ad64e3a97990a514877196 e confirmou modelo, ready e clock 133 MHz por USB. Os timestamps de MFE/Invoke excluem USB, aquisição e OLED. O wall time incluindo USB foi retido separadamente. Este é o firmware V3, não o binário científico original de 189.408 bytes. O novo layout CMake ainda precisa de build próprio.

## Resultados

| Execução | Inference mediana (ms) | MFE + network mediana (ms) |
| --- | ---: | ---: |
| CPU Float32 / TensorFlow | 0,661 | 0,836 |
| RTX Float32 / TensorFlow | 0,768 | 0,956 |
| CPU Float32 / reference | 1,347 | 1,509 |
| CPU INT8 / reference | 1,932 | 2,113 |
| RP2040 INT8 / V3 | 312,077 | 1.322,608 |

Os arquivos TFLite Float32/INT8 têm 7.984/5.264 bytes, redução de 34,1%. A diferença média absoluta de window score Float32 reference/INT8 reference foi 0,0145369 (máxima 0,0586636). Houve 98/100 decisões iguais no threshold INT8 comum: é concordância de windows, não accuracy por paciente. CPU e RTX Float32 tiveram diferença máxima de score de 2,6822e-7. CPU INT8 e placa produziram os mesmos scores nas cem windows.

## Interpretação e limites

Nesta sessão, GPU não reduziu a latência em batch size 1 e INT8 não acelerou o reference resolver de CPU. Dispatch/readback é uma explicação possível para a GPU, não um custo isolado pelo protocolo. Os modos têm escopos de timer e kernels diferentes; ordem fixa, caches e variabilidade térmica não foram controlados por desenho cruzado. Não houve medição de energia ou peak RAM. Não atribuir essas diferenças exclusivamente ao hardware ou à quantization.

## Evidência e reprodução

[Relatórios e linhas individuais](evidence/validation-benchmark-20261027/) incluem plan, hashes, 300 respostas por modo e summary. O bundle local preserva os PCM e float.keras, sem duplicar a base no Git. O TFLite Float32 publicado é um export derivado e verificado, distinto do arquivo Keras. O código de execução está em `tools/benchmark_validation.py` e `tools/benchmark-arch.sh`; um novo bundle deve ter plan.json com os hashes dos inputs/source, não reutilizar resultados como se fossem uma nova execução.

O iniciador local NOVO_BENCHMARK_TINYML.cmd prepara uma pasta fresh com timestamp. Após a execução de PC/RTX, RETOMAR_BENCHMARK_PLACA.cmd permite concluir somente USB no mesmo diretório. Não usar BOOTSEL para medir: esse modo serve apenas à gravação do firmware. Nenhum iniciador de benchmark treina um modelo.
