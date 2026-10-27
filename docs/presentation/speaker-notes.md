# Roteiro de fala — TinyML na BitDogLab

Proposta: 15 a 18 minutos, com ensaio da demonstração antes da aula. Apresentador: Leandro. As notas também estão nos slides.

## 1. TinyML na BitDogLab

Tempo sugerido: 0:30

Hoje vou mostrar como uma rede neural treinada no computador pode executar em uma BitDogLab. O caso de estudo é classificar gravações com rótulos de sopro presente ou ausente. Vamos entender o caminho do áudio, comparar os resultados e demonstrar a execução. O objetivo científico é medir a viabilidade e os limites em um microcontrolador. Não apresento a placa como um exame médico.

Fontes: Artigo local main.tex; David et al., MLSys 2021

## 2. Treinamento e inferência

Tempo sugerido: 1:00

Treinar é ajustar os pesos usando exemplos rotulados. Essa etapa ocorreu no computador, com apoio da GPU. Inferir é usar os pesos já aprendidos para analisar uma entrada. Essa etapa pode rodar na placa, sem internet. Neste projeto a placa não treina. No benchmark que vou mostrar, a execução do PC foi medida na CPU, com uma thread, e não na RTX. A finalidade é comparar implementações do modelo congelado.

Fontes: David et al. https://proceedings.mlsys.org/paper_files/paper/2021/hash/6c44dc73014d66ba49b28d483a8f8b0d-Abstract.html; training.json; reports/pc_validation_benchmark.json

## 3. O que a rede classifica

Tempo sugerido: 0:55

Sopro é um som adicional percebido na ausculta. Existem sopros inocentes e sopros associados a alterações cardíacas. Por isso não vou usar as expressões coração saudável ou coração doente para as duas classes. Quando o OLED mostra sem sopro, ele está apresentando a previsão da rede para aquele trecho. A rede também não foi treinada para medir os batimentos por minuto. Como só há duas classes, fala e ruído podem receber uma delas.

Fontes: American Heart Association, Heart Murmurs, revisão 17/03/2026: https://www.heart.org/en/health-topics/heart-murmurs

## 4. Dados e divisão por grupo

Tempo sugerido: 0:55

Usamos o CirCor DigiScope. Depois dos critérios do estudo, são 812 grupos vinculados e 2.976 gravações. Há várias gravações por pessoa e possíveis vínculos entre registros. Dividir os WAVs aleatoriamente poderia colocar a mesma identidade nos dois lados e inflar o resultado. A divisão foi feita antes do treinamento, preservando os grupos. A validação serviu para seleção e limiar; o teste final ficou separado. Não alteramos o limiar depois de examinar o teste.

Fontes: split-manifest.json; artigo local Materials and Methods; Oliveira et al. 2022, DOI 10.1109/JBHI.2021.3137048; PhysioNet CirCor 1.0.3 https://physionet.org/content/circor-heart-sound/1.0.3/

## 5. O áudio vira uma representação MFE

Tempo sugerido: 0:55

Aqui estão a forma de onda e a representação MFE calculadas de um dos áudios de demonstração. Cada coluna do mapa corresponde a um intervalo curto e cada linha a um filtro mel. A cor representa log-energia. Essa transformação organiza os padrões do áudio para a rede. São três segundos a 4 kHz, com 12 mil amostras. O mapa tem 186 posições de tempo e 24 filtros. As estatísticas de normalização foram aprendidas apenas no treino. Este exemplo é da validação, não uma nova medição clínica.

Fontes: engine.py; pcg/features.py; demo_samples.h, gravação 49627_AV da validação; figura original gerada dos mesmos dados PCM

## 6. Uma CNN pequena para o RP2040

Tempo sugerido: 0:50

A CNN usa duas camadas convolucionais pequenas, com oito e dezesseis filtros, e operações de redução espacial. Depois há média global e uma camada com duas saídas. No total são 1.282 parâmetros. Parâmetros são os números aprendidos no treinamento. Não programamos manualmente uma lista de batimentos. A execução usa operações matemáticas sobre o áudio transformado, e por isso é possível receber uma entrada diferente dos exemplos embutidos.

Fontes: Artigo local, arquitetura; model/model_int8.tflite; training.json

## 7. Quantização e implantação

Tempo sugerido: 0:50

Quantizar muda a representação numérica. Em vez de armazenar cada valor como ponto flutuante de 32 bits, usamos inteiros de oito bits com escala e ponto zero. O arquivo final tem 5.264 bytes. A relação quatro para um descreve um número isolado, não garante que todo firmware ou toda memória caia quatro vezes. A exportação foi calibrada com dados do treino e testada. Em seguida o TFLite Micro executa esse modelo no RP2040.

Fontes: export.json; https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/g3doc/performance/quantization_spec.md; David et al. 2021

## 8. Como o experimento foi avaliado

Tempo sugerido: 0:45

A avaliação completa na placa processou 6.512 janelas de 471 gravações. As métricas finais são por grupo, totalizando 122 grupos. Isso é diferente de apertar A e observar uma classificação de três segundos. A demonstração ilustra a execução, enquanto o experimento estima o desempenho no conjunto separado. O replay digital permite controlar quais amostras chegam à placa e comparar com o computador. A aquisição pelo microfone não fazia parte desse teste.

Fontes: runs/board-test-circor-20261023/session.json e reports; protocolo congelado

## 9. Desempenho no PC e na placa

Tempo sugerido: 0:55

Esta tabela mostra o resultado científico. Float no PC, INT8 de referência e INT8 na placa tiveram as mesmas decisões por grupo. O host otimizado teve um falso positivo a mais. Isso não significa que a placa deixou a rede mais inteligente. Há diferenças numéricas entre implementações e o limiar pode transformar uma pequena diferença em outra decisão. Mantivemos esse resultado no artigo. Recall, ou sensibilidade, diz quantos positivos foram identificados. F1 combina precisão e recall.

Fontes: model/reports/float_cnn_metrics.json; int8_host_metrics.json; board-test-circor-20261023/reports/runtime_comparison.json

## 10. Os erros também fazem parte do resultado

Tempo sugerido: 0:55

A matriz torna os erros concretos. Entre os 24 grupos com sopro, identificamos 17 e perdemos sete. Entre os 98 sem sopro, houve oito falsos positivos e noventa negativos corretos. Acurácia sozinha pode parecer boa porque há mais negativos. Classificar todos como ausentes já acertaria 98 de 122, cerca de 80,3%, mas não identificaria nenhum positivo. Por isso mostro F1, recall e a matriz, sem apresentar 87,7% como prova de uso clínico.

Fontes: int8_rp2040_metrics.json; majority_baseline_metrics.json; contagens do teste preservado

## 11. F1 entre implementações

Tempo sugerido: 0:35

O gráfico facilita comparar as implementações. F1 mais alto indica melhor combinação de precisão e recall neste conjunto. A diferença do host otimizado é pequena, e o intervalo da placa é amplo: de 0,526 a 0,829. São apenas 24 grupos positivos no teste. Não há base para afirmar superioridade estatística da placa ou generalização clínica. As barras mostram os valores pontuais; o intervalo citado abaixo pertence à placa.

Fontes: Métricas reais de teste; bootstrap 2.000 replicações, seed 2026, agrupado por paciente

## 12. Tempo no PC e na BitDogLab

Tempo sugerido: 0:55

Este é um ensaio suplementar de latência, separado das métricas do teste. Foram usadas as mesmas cem primeiras janelas de três segundos do benchmark de validação já medido na placa. O PC teve dez aquecimentos excluídos, LiteRT de referência em uma thread e bibliotecas NumPy para o MFE. A placa usa C++ e TFLite Micro. Por isso a diferença inclui implementação e ambiente. Os tempos da placa são históricos e os do PC foram coletados nesta preparação. Não é uma comparação com a RTX, nem uma medida isolada da vantagem do INT8.

Fontes: reports/pc_validation_benchmark.json; pc_validation_timings.csv; board-validation-20261023-114223/timings.csv; exclui I/O, aquisição, USB, OLED, cópia do tensor e gráficos

## 13. Tempo combinado no PC e na placa

Tempo sugerido: 0:45

O gráfico compara o tempo combinado para as mesmas cem janelas de validação. A barra do PC é muito pequena nesta escala porque a mediana foi 2,687 milissegundos, enquanto a placa levou 1.318,421 milissegundos. Há diferenças de implementação e ambiente: NumPy e LiteRT no PC, C++ e TFLite Micro na placa. Não é possível atribuir essa razão apenas ao processador ou ao INT8. O ponto científico é que a placa conseguiu executar localmente com um custo medido. No teste completo, a mediana da placa foi 1,318 segundo. A maior parte do tempo na placa está no MFE, como mostra a tabela anterior.

Fontes: reports/pc_validation_benchmark.json; mesmos cem WAVs de validação, dez aquecimentos excluídos; medidas históricas da placa, não simultâneas

## 14. Recursos do firmware científico

Tempo sugerido: 0:40

O modelo é pequeno, mas o programa completo também precisa de código de processamento, buffers e memória para os tensores. A imagem flash do firmware científico tem 189.408 bytes. O espaço estático principal de SRAM é 186.224 bytes. Isso não é pico medido de RAM, e a arena já está dentro dessas reservas; não devemos somá-la de novo. A demonstração visual contém áudios embutidos e outros recursos, por isso usa mais flash e não substitui estes números do artigo.

Fontes: outputs/firmware-bitdoglab/build-usbfix-20261023-113636/resource-report.json e build-audit.json; fontes científicas preservadas

## 15. Demonstração com o mesmo arquivo

Tempo sugerido: 2:00, incluindo interação

Abra ABRIR_AULA_TINYML.cmd antes da aula e confirme o painel. Escolha Exemplo 1, reproduza o trecho e clique Analisar no PC. Aponte a onda, o MFE e o escore. Se a V3 tiver sido compilada, gravada e ensaiada, clique Comparar com a placa. Os mesmos dados PCM seguem pela USB e a placa calcula sua própria saída. Repita com Exemplo 2. Se houver problema de USB, use A na V2 como alternativa já conferida: explique que a entrada vem da memória da placa, não do alto-falante. Não afirme que a V3 foi testada antes do ensaio real.

Fontes: app.py; engine.py; board_link.py; firmware-aula/main.cpp; A na V2 confirmado manualmente pelo usuário em 24/10/2026

## 16. Microfone: um novo experimento

Tempo sugerido: 1:15, incluindo interação

Este ensaio mostra uma entrada acústica. Prepare um celular com uma gravação de origem conhecida. Pressione B, aguarde o aviso e reproduza o som durante os três segundos de captura. Na V3 o painel também pode comandar a captura e analisar no PC o mesmo PCM recebido da placa. O resultado pode mudar porque alto-falante, sala, distância e microfone mudam o sinal. O LED azul e a interrogação identificam o caráter experimental. Fala e ruído também podem receber uma classe. Se a captura falhar, mostre a limitação e siga, sem escolher apenas acertos para alegar desempenho. Não encoste a placa no peito prometendo detectar sopro.

Fontes: firmware-aula/microphone.h; protocolo didático separado; aquisição original CirCor por ausculta eletrônica, https://physionet.org/content/circor-heart-sound/1.0.3/

## 17. O que este projeto demonstrou

Tempo sugerido: 0:35

A contribuição é mostrar que uma rede pequena pode executar no RP2040, quantificar o custo e comparar as decisões com o computador. A rede errou, e esses erros fazem parte do resultado. O experimento digital está concluído. A interface ajuda a comunicar o funcionamento. O microfone abre uma investigação nova, que precisa de avaliação própria. O próximo passo científico seria estudar aquisição e robustez, com protocolo separado, sem ajustar o modelo pelo teste que já foi encerrado.

Fontes: Resultados e limitações do artigo; evidências locais preservadas

## 18. Referências e dados do experimento

Tempo sugerido: Consulta após a fala

Referências completas e URLs: Oliveira et al., IEEE JBHI 2022, DOI 10.1109/JBHI.2021.3137048. Dataset CirCor DigiScope 1.0.3, DOI 10.13026/tshs-mw03, https://physionet.org/content/circor-heart-sound/1.0.3/. David et al., MLSys 2021, https://proceedings.mlsys.org/paper_files/paper/2021/hash/6c44dc73014d66ba49b28d483a8f8b0d-Abstract.html. AHA, https://www.heart.org/en/health-topics/heart-murmurs. Hardware BitDogLab: https://github.com/BitDogLab/BitDogLab. RP2040: https://www.raspberrypi.com/documentation/microcontrollers/microcontroller-chips.html. Resultados científicos: runs/board-test-circor-20261023/reports. Comparação suplementar PC: tinyml-aula/reports. A fonte PhysioNet teve falha de acesso nesta sessão; metadados e métodos foram mantidos do material previamente conferido, sem inventar nova consulta.

Fontes: Fontes primárias e relatórios originais do projeto
