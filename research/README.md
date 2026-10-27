# Pipeline científico preservado

O pipeline original fica neste pacote separado para conservar a organização e a lógica de snapshots dos experimentos. A aplicação didática da raiz tem instalação leve e não importa TensorFlow.

Para novos experimentos, use Python 3.12 e um ambiente separado. Não modifique uma execução já encerrada. GPU: Linux/Arch WSL, conforme o ambiente efetivamente usado no estudo.

```sh
# Na raiz do repositório, com o ambiente de pesquisa ativado:
python -m pip install -e ".[research-gpu]" -e ./research
pcg doctor
pcg --help
```

Para CPU, use o extra `research` em vez de `research-gpu`. Não selecione os dois extras simultaneamente. Instalação e treino GPU dependem de driver/WSL compatíveis e de espaço em disco; não são executados por abrir o painel.

Fluxo explícito para uma NOVA execução:

```sh
pcg download --dest data/circor-1.0.3
pcg inventory data/circor-1.0.3 --out runs/new/inventory.json
pcg split runs/new/inventory.json --out runs/new/split
pcg prepare runs/new/split/manifest.json --out runs/new/prepared
pcg train runs/new/prepared --out runs/new/model --device gpu
pcg export runs/new/model
pcg evaluate runs/new/model
```

Os parâmetros padrões estão em config.json. O split é por identidades/grupos vinculados, Unknown é excluído e estatísticas são aprendidas só no treino. Seleção e limiar usam validação. Não ajuste pelo teste.

O protocolo completo de placa usa `scripts/evaluate-test-usb.py --help` e requer os artefatos congelados da execução e o firmware benchmark. Não use o firmware de demonstração para produzir essas métricas.

Testes unitários sem treinar e sem GPU:

```sh
python -m unittest discover -s research/tests -v
```

As rotinas científicas foram copiadas sem alteração de semântica. Os testes de integração que exigem TensorFlow são opcionais e não foram confundidos com resultados reais do CirCor. O repositório não contém o dataset nem diários brutos com caminhos pessoais.
