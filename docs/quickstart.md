# Início rápido

## Preparação

Instale Python 3.12. Python 3.15 não é o ambiente fixado deste projeto. Clone o repositório e abra um terminal na raiz.

No Windows, execute `SETUP_WINDOWS.cmd`. Se o iniciador não encontrar o Python certo, use:

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup.ps1 -Python "caminho/para/python.exe"
```

No Linux/Arch WSL:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

A demonstração usa NumPy, LiteRT e pyserial. O treinamento e suas dependências são uma instalação opcional separada.

## Uso diário

Windows: `START_WINDOWS.cmd`.

Qualquer sistema com o ambiente ativado:

```sh
heart-tinyml serve
```

Abra o endereço local mostrado, escolha Áudio 1 e clique Analisar no PC. Não é necessário BOOTSEL ou placa para essa etapa. Feche o terminal ou pressione Ctrl+C para encerrar.

Para usar outra porta local: `heart-tinyml serve --port 8767`. Para não abrir automaticamente o navegador: `heart-tinyml serve --no-browser`.

## Comparar com a placa

1. Use uma BitDogLab RP2040 com o programa `demo` descrito em [firmware.md](firmware.md).
2. Feche outros monitores seriais.
3. Clique Conectar placa. O painel verifica o identificador do programa e o hash do modelo.
4. Selecione um áudio e use Comparar o mesmo áudio por USB.

A comparação não requer treinar novamente. O modo PC continua disponível se a USB falhar. A mesma janela PCM16 segue aos dois dispositivos, embora suas implementações possam apresentar diferenças numéricas.

## Testar o microfone

Depois da conexão, abra Microfone experimental e clique Capturar na placa. Aguarde o aviso e reproduza uma gravação de origem conhecida perto do microfone durante três segundos. O áudio volta pela USB e pode ser ouvido no painel.

O sinal pode ser rejeitado por volume baixo ou saturação. Mesmo um sinal aceito pode conter ruído/fala e ser classificado indevidamente. Não faça uma apresentação como exame de colegas nem prometa captação cardíaca direta no peito.

## Diagnóstico

```sh
heart-tinyml doctor
heart-tinyml verify-model
```

- Porta ocupada no PC: use outra `--port` ou encerre uma instância anterior.
- USB indisponível: feche monitores seriais, reconecte e clique Conectar placa.
- Firmware incompatível: use o programa `demo`; o firmware `benchmark` pertence ao protocolo científico.
- Modelo/normalização diferentes: restaure os recursos versionados, sem alterar limiar para forçar um acerto.
- WAV inválido: use PCM16 sem compressão, mono/estéreo, entre 4 e 96 kHz. A conversão didática é informada no painel e não substitui o protocolo de reamostragem do estudo.
