# Recursos de terceiros e atribuição

A licença MIT da raiz cobre o código de autoria do projeto. Os itens abaixo mantêm sua atribuição e licenças próprias.

## CirCor DigiScope

Os dois áudios de demonstração são recortes de três segundos da validação, gravações `39043_AV` e `49627_AV`. Origem/hashes: `docs/audio-origin.json`. Rótulos de grupo não são anotações clínicas de cada janela.

A licença distribuída com a cópia oficial da base é ODC Attribution License (ODC-By), preservada em `src/heart_tinyml/resources/audio/LICENSE.txt`. O dataset completo não está incluído. O modelo foi treinado com a base segundo o protocolo documentado; esta nota não substitui a licença da base.

Oliveira et al. The CirCor DigiScope Dataset: From Murmur Detection to Murmur Classification. IEEE JBHI 26(6), 2524–2535, 2022. DOI: 10.1109/JBHI.2021.3137048. Dataset v1.0.3: https://physionet.org/content/circor-heart-sound/1.0.3/.

## Fonte bitmap do OLED

O bitmap usado no OLED deriva de DejaVu Sans Mono. Licença preservada em `firmware/shared/FONT-LICENSE.txt`. Não substituir sua atribuição pela licença MIT da raiz.

## Firmware e runtime

Pico SDK, pico-tflmicro/TensorFlow Lite Micro, TinyUSB, NumPy, LiteRT e pyserial são dependências externas com suas próprias licenças. SDKs e toolchains não são copiados para este repositório. Os commits de firmware utilizados no experimento estão em `firmware/DEPENDENCIES.json`.

## Artigo e apresentação

A classe, os estilos e o logo do template do evento foram preservados nos diretórios do artigo, com seus avisos originais. Não se reivindica autoria desses recursos. Figuras científicas foram geradas dos dados do projeto e citam sua origem. O desenho de chip na capa é esquemático, não fotografia da placa.
