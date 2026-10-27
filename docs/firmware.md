# Firmware RP2040

Existem dois programas com propósitos distintos, sob um único projeto CMake:

| Programa | Uso |
|---|---|
| `demo` | OLED, LEDs, avisos sonoros, exemplos A, microfone B e comparação pelo painel USB |
| `benchmark` | Replay digital controlado do protocolo científico, sem interface didática |

## Dependências

Consulte os commits em `firmware/DEPENDENCIES.json`. São necessários Pico SDK 2.1.0, pico-tflmicro, toolchain Arm GNU, CMake e Ninja no PATH. SDKs e toolchains não são versionados.

Exemplo de preparação manual, em diretórios externos ou `third_party/` ignorado:

```sh
git clone https://github.com/raspberrypi/pico-sdk.git third_party/pico-sdk
git -C third_party/pico-sdk checkout 95ea6acad131124694cda1c162c52cd30e0aece0
git -C third_party/pico-sdk submodule update --init lib/tinyusb
git clone https://github.com/raspberrypi/pico-tflmicro.git third_party/pico-tflmicro
git -C third_party/pico-tflmicro checkout dfea53b977f131dc50d7060568ad4fd355d4d71e
```

Defina `PICO_SDK_PATH` e `PICO_TFLMICRO_PATH` para os caminhos desses diretórios. Os headers e pesos congelados já estão em `firmware/generated`. Não é necessário novo treinamento.

## Compilar

```sh
cmake -S firmware -B build/demo -G Ninja -DPCG_APP=demo -DPICO_BOARD=pico_w
cmake --build build/demo --parallel
```

Para o programa científico, use outra pasta e `-DPCG_APP=benchmark`. O CMake do SDK pode precisar construir ferramentas de host; configure-as conforme a instalação local do Pico SDK.

O layout foi reorganizado a partir das fontes já usadas no projeto. O build histórico da V3 tinha SHA256 de UF2 `2215829d1676412c81d22e838abd384369c7dd9258ad64e3a97990a514877196`. Isso não prova que um novo build seja idêntico nem transfere suas métricas para o novo binário.

## Verificar e gravar

```sh
python tools/verify_uf2.py build/demo/pcg_bitdoglab.uf2
```

Coloque a placa em BOOTSEL e identifique a unidade RPI-RP2. A gravação substitui o programa atual. No Windows, com a letra real da unidade:

```powershell
python tools/flash_firmware.py build/demo/pcg_bitdoglab.uf2 --drive E:\
```

O verificador exige família RP2040, blocos coerentes e o modelo congelado presente uma única vez. O gravador confere INFO_UF2.TXT. Nenhum desses testes substitui ensaio físico.

## Interface da placa

- A alterna os dois trechos gravados. Verde/um bipe e vermelho/três bipes representam a saída do modelo.
- B capta três segundos e mostra classificação experimental, azul e com interrogação.
- O painel PC envia a mesma janela via PCG1 para inferência ou solicita captura real pelo microfone.

Não pressione A/B durante uma transação do painel. O buzzer é silenciado durante a captura. GP21 é usado no buzzer e GP28/ADC2 no microfone. A revisão física exata deve ser conferida na unidade usada.

O firmware demo preserva o identificador de protocolo `tinyml_aula_v3` para compatibilidade com a demonstração anterior. Isso é um detalhe de transporte e não significa validação física da versão reorganizada.
