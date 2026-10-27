# Roteiro — TinyML na BitDogLab

Sugestão: 25 minutos mais demonstração. Português na explicação, termos técnicos em inglês. Pule as contas detalhadas se a aula for mais curta; o guia mantém o desenvolvimento completo.

## 1. Uma rede neural dentro da BitDogLab

Eu queria entender TinyML usando uma placa que já tinha. Escolhi sons cardíacos como caso de estudo. Vou mostrar como preparei os dados, treinei a rede no computador, reduzi o modelo e conferi sua execução na placa. Também vou mostrar os erros que encontrei.

Fontes: Artigo main.tex e relatórios congelados de CirCor 1.0.3; https://github.com/Lawtrel/bitdoglab-heart-tinyml

## 2. Minha pergunta

O PC é muito mais potente. Minha pergunta não é se a placa vai ganhar dele em velocidade. Quero saber se uma rede pequena cabe, executa e mantém um desempenho mensurável. Por isso separo a qualidade das previsões do tempo e da memória.

Fontes: Artigo main.tex e relatórios congelados de CirCor 1.0.3; https://github.com/Lawtrel/bitdoglab-heart-tinyml

## 3. Training e inference

No training, a rede ajusta números internos chamados weights. A RTX ajudou nessa etapa. Na inference, esses números não mudam: o modelo recebe um áudio e calcula scores. A comparação de tempo antiga do PC foi feita na CPU. Ela não é uma medida de RTX inference.

Fontes: David et al., TensorFlow Lite Micro, MLSys 2021; training.json

## 4. Com sopro e sem sopro

Os sons S1 e S2 fazem parte do ciclo cardíaco. Um heart murmur é um som adicional; pode ser inocente ou estar associado a alguma alteração. Não vou chamar as classes de coração saudável e doente. No dataset, o rótulo é do grupo, não de cada trecho de três segundos. Este desenho foi criado apenas para explicar, não é uma gravação nem uma segmentação de paciente.

Fontes: AHA Heart Murmurs https://www.heart.org/en/health-topics/heart-murmurs; CirCor 1.0.3

## 5. Ouvir os exemplos

Neste ponto eu abro o painel e reproduzo os áudios 1 e 2. Primeiro peço que a turma apenas ouça. Depois mostro a inference. Não apresento minha própria escuta como confirmação clínica. Foram escolhidos seis grupos de validation por identificador, antes de ver os scores, sem selecionar os melhores acertos. Os WAVs estão no pacote para usar sem depender da internet.

Fontes: audio-catalog.json; licença ODC-By, CirCor 1.0.3

## 6. Split antes do training

Se a mesma pessoa aparecer no training e no test, a rede pode reconhecer características dessa pessoa e o resultado parecer melhor do que é. Agrupei identidades vinculadas e duplicatas antes do split. As windows de um grupo ficam juntas. Usei training para ajustar a rede, validation para escolher o checkpoint e o threshold, e test para a avaliação final. Os vínculos conhecidos foram preservados; vínculos não anotados continuam sendo uma limitação.

Fontes: Artigo main.tex e relatórios congelados de CirCor 1.0.3; https://github.com/Lawtrel/bitdoglab-heart-tinyml

## 7. Do som aos números

A rede não escuta como nós. Primeiro represento o som por samples. A waveform mostra a amplitude no tempo. No MFE, cada linha corresponde a uma Mel band, cada coluna a um frame e a cor representa log-energy. É uma forma de organizar padrões do áudio para a CNN. O gráfico é do mesmo exemplo que podemos ouvir.

Fontes: pcg/features.py; exemplo 49627_AV, validation

## 8. Contando as entradas

São três segundos a 4 kHz. Isso dá 12 mil samples, ocupando 24 mil bytes em PCM16. Divido a window em frames de 128 samples com hop de 64. Sem centered padding, a fórmula produz 186 frames. Cada frame terá 24 features. São 4.464 valores na entrada da rede. O guia mostra as fórmulas completas.

Fontes: signal.py; frontend_config.h

## 9. Calculando o MFE

Depois de remover a componente DC, aplico uma Hann window e a FFT. Calculo o power spectrum sem duplicar os bins positivos. Cada filtro triangular soma a energia de uma região; depois aplico log e normalization. Os coeficientes de normalization foram aprendidos só no training. Se eu usasse o test para ajustar essas estatísticas, haveria leakage.

Fontes: signal.py; guia matemático, equações 1 a 5

## 10. Tamanho da CNN

Uma Conv2D aprende filtros locais do MFE. Depois de cada Conv2D, há ReLU e MaxPool. Global Average Pooling resume os canais e Dense produz dois logits. A Softmax transforma esses logits em scores. Incluindo bias, a primeira camada tem 80 parâmetros; a segunda 1.168; a saída 34. O total é 1.282. Não fiz architecture search para provar que essa era a melhor rede possível.

Fontes: research/pcg/learning.py build_model

## 11. Curvas do training

Estes são os CSVs salvos no training real. A loss é weighted cross-entropy, com pesos que equilibram classes e a contribuição de cada grupo. Usei Adam, learning rate 0,001 e batch size 32. Treinei três seeds. Early stopping interrompia após dez épocas sem melhora estrita do F1 em validation. Escolhi seed 43, epoch 66. As oscilações não são resultados de test.

Fontes: model/seed_42/history.csv; seed_43/history.csv; seed_44/history.csv; training.json

## 12. O significado de INT8

INT8 é um signed integer de oito bits. Em vez de guardar qualquer número real com Float32, represento uma faixa por 256 códigos. A scale diz quanto vale cada passo e o zero-point representa o zero real. Essa aproximação reduz armazenamento de tensores e permite integer kernels. Não significa que todo o programa virou inteiro: o MFE continua floating point.

Fontes: Google AI Edge LiteRT 8-bit quantization specification

## 13. Exemplo de quantization

A scale mostrada foi lida do próprio arquivo TFLite. Para facilitar a conta, uso uma feature ilustrativa de valor um. O código INT8 é menos quinze; ao reconstruir, obtenho aproximadamente 0,9915. Essa pequena diferença é o custo da aproximação. Isso não é um score de paciente. Na saída Softmax, a scale é 1/256 e o zero-point é menos 128.

Fontes: calculos-verificados.json; modelo INT8 congelado

## 14. Economia e aproximação

Para o mesmo número de elementos, Float32 usa quatro bytes e INT8 usa um. Este gráfico calcula apenas o input tensor: 17.856 contra 4.464 bytes. O arquivo completo tem grafo e metadados; não posso multiplicar 5.264 por quatro para deduzir seu tamanho Float32. Também não posso prometer um speedup só por usar INT8. O novo benchmark mede isso em uma comparação de CPU com o mesmo resolver.

Fontes: calculos-verificados.json; LiteRT quantization spec

## 15. Agregação e threshold

O score de uma única window no painel não é a métrica científica do paciente. Primeiro faço mean das windows de uma recording. Depois tomo o maximum entre recordings do grupo. Comparo com o threshold escolhido em validation. Esse threshold foi congelado antes do test. Não mudei o limiar para deixar a demonstração mais bonita.

Fontes: research/pcg/metrics.py aggregate e select_threshold; export.json

## 16. O experimento na placa

O experimento científico foi digital replay. O PC enviava uma window PCM16 à placa; ela calculava as features e executava o modelo. Registrei a resposta imediatamente. Um timeout interrompeu a primeira sessão depois de 1.293 windows e a coleta foi retomada com o mesmo protocolo. O teste só foi liberado quando as 6.512 respostas foram concluídas e auditadas. Microfone e OLED não entram nesses tempos.

Fontes: board-test-circor-20261023/protocol.json, journal e relatórios; artigo Experimental Setup

## 17. Resultados medidos

Aqui estão as métricas do test completo, não dos seis exemplos. O resultado da placa foi F1 0,694 e Recall 70,8%. A implementação INT8 optimized no PC teve um falso positivo a mais que a reference e a placa. Float32 e placa têm os mesmos counts, mas isso não significa scores idênticos. A tarefa é binária e exclui Unknown; não comparei esses números diretamente com rankings de três classes.

Fontes: Artigo main.tex e relatórios congelados de CirCor 1.0.3; https://github.com/Lawtrel/bitdoglab-heart-tinyml

## 18. Acertos e erros

Quero chamar atenção para os sete false negatives. São grupos rotulados com sopro que o modelo não identificou. Também houve oito false positives. Esses erros são parte do resultado, não detalhes que eu deveria esconder. É por isso que não trato o protótipo como um diagnóstico.

Fontes: int8_rp2040_metrics.json; patient predictions

## 19. Contas das métricas

Recall pergunta quantos positivos a rede encontrou: 17 de 24. Precision é 17 de 25 previsões positivas, ou 68%. F1 equilibra Precision e Recall: 34 dividido por 49. Accuracy divide todos os acertos pelos 122 grupos. Como há 98 negativos, um modelo que nunca detecta sopro já teria 80,3% de Accuracy. Por isso o F1 e o Recall são importantes. O IC95% de F1 foi 0,526 a 0,829, mostrando incerteza grande.

Fontes: Relatórios do teste completo; patient bootstrap 2.000 repetições, seed 2026

## 20. Por que os resultados parecem iguais

O modelo e os dados são os mesmos. É desejável que a classe final seja preservada ao mudar de máquina. A diferença de hardware aparece principalmente no custo para executar. Mesmo com as mesmas decisões por grupo, houve 86 windows com feature CRC diferente e 160 com output score diferente contra reference. A diferença máxima de score foi 0,0078125. Não declarei equivalência bit a bit.

Fontes: Relatórios e auditoria do teste completo; não são três trials independentes

## 21. Tempos históricos

Estas medidas antigas usam as mesmas 100 windows de validation. O PC executou na CPU com uma thread; a RTX não aparece nesta tabela. Na placa, feature extraction consumiu mais tempo que a inference. Há implementações diferentes de FFT e runtime, e as medições não foram simultâneas. USB, reprodução, aquisição e OLED foram excluídos. Não interpreto a diferença como efeito isolado de quantization.

Fontes: pc_validation_benchmark.json e board-validation-20261023-114223/timings.csv

## 22. Novo benchmark completo

Agora há medidas reais de RTX inference. Usei as mesmas 100 windows, dez warm-up calls e três repetições. Float32 CPU/RTX usa TensorFlow e output.numpy para sincronizar; os tempos incluem dispatch e readback. Float32 e INT8 reference usam TFLite 2.21 e uma thread. A placa usa timestamps de MFE e Invoke do firmware V3 a 133 MHz. Os escopos não são perfeitamente idênticos e a ordem dos modos foi fixa; não trato isto como isolamento térmico de hardware. O MFE do modo RTX continua na CPU.

Fontes: benchmark-summary.json; fresh-20261027-111652; auditoria de hashes e 300 respostas por modo

## 23. CPU e RTX

Na sessão medida, a mediana de CPU foi 0,661 ms e a de RTX 0,768 ms. As previsões dos dois modos foram quase iguais: diferença máxima de score de cerca de 0,000000268. Para uma rede tão pequena com batch size um, o custo de dispatch e sincronização é uma explicação possível, mas não foi isolado por este protocolo. Não concluo que a GPU seja pior em geral. Training e throughput de batches maiores são outras perguntas.

Fontes: cpu_float.json e gpu_float.json; benchmark-summary.json

## 24. Float32 e INT8 medidos

A comparação de arquivo agora é entre dois TFLite da mesma arquitetura. Float32 tem 7.984 bytes e INT8 5.264: redução de 34,1%, diferente da conta teórica de quatro vezes para cada tensor. No reference kernel da CPU, INT8 não foi mais rápido. A diferença média absoluta de score foi 0,01454 e a máxima 0,05866. Duas das cem windows mudaram de classe usando o mesmo threshold INT8. Esse é um diagnóstico numérico em validation, não uma nova accuracy clínica. A placa e o CPU INT8 tiveram os mesmos scores nas cem windows.

Fontes: cpu_float_lite.json, cpu_int8.json, board_int8.json; Float32 conversion check max error 4,77e-7; benchmark-summary.json

## 25. Recursos

Não basta dizer que o modelo tem cinco kilobytes. O programa também precisa de buffers de áudio, features, activations e runtime. A imagem flash científica ocupou 189.408 bytes. O span estático principal de SRAM foi 186.224 bytes, incluindo a reserva da arena. Isso não é peak RAM. O uso máximo da pilha não foi instrumentado. São medidas do firmware científico original, não de qualquer nova demo recompilada.

Fontes: Auditoria ELF/UF2 e relatório de recursos do firmware científico

## 26. Demonstração ao vivo

Eu abro o painel pelo START_WINDOWS e escolho um exemplo. Ouço, mostro o MFE, clico em Analisar no PC e explico o threshold. Com firmware compatível, conecto a USB e comparo exatamente o mesmo PCM. O OLED e os bipes comunicam a previsão da janela. Se a placa não responder, mostro os relatórios preservados e explico a falha; não simulo uma medição. O microfone acrescenta acústica e ruído, e ainda não foi validado.

Fontes: README, docs/firmware.md; audio-catalog.json

## 27. Conclusão

O resultado principal é uma execução completa e mensurada no RP2040, com limites explícitos. Eu compreendi o caminho do som ao modelo e pude comparar implementações. A rede perdeu sete positivos e tem incerteza ampla. Microfone, streaming, robustez e peak RAM são trabalhos futuros. O novo benchmark mostrou diferença de tempo e tamanho e também diferenças numéricas. Ele não transforma o protótipo em um diagnóstico.

Fontes: Artigo e guia matemático

## 28. Referências

As referências completas e as contas estão no guia. O repositório reúne código, firmware, fontes do artigo em inglês e português e relatórios curados. Os CSVs e journals científicos originais foram preservados. Não confundir a execução do benchmark com um novo treinamento. Fontes consultadas em 27/10/2026.

Fontes: https://physionet.org/content/circor-heart-sound/1.0.3/; https://doi.org/10.1109/JBHI.2021.3137048; https://doi.org/10.1371/journal.pdig.0000324; https://proceedings.mlsys.org/paper_files/paper/2021/hash/6c44dc73014d66ba49b28d483a8f8b0d-Abstract.html; https://developers.google.com/edge/litert/conversion/tensorflow/quantization/quantization_spec; https://www.heart.org/en/health-topics/heart-murmurs
