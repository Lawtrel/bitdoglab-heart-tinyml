# TinyML na BitDogLab

Projeto desenvolvido por **Leandro Alves dos Santos durante as aulas de Introdução à Inteligência Artificial**. O objetivo é entender o treinamento de uma CNN, sua quantização INT8 e a execução local em um microcontrolador RP2040, usando sons cardíacos como caso de estudo.

O repositório reúne uma demonstração didática, firmware e o pipeline de pesquisa usado no artigo em desenvolvimento para o SBMSB. “Sopro presente/ausente” é uma classificação do modelo, não um diagnóstico nem um detector genérico de batimentos. O modo de microfone é experimental.

[Início rápido](docs/quickstart.md) · [Arquitetura e padrões](docs/architecture.md) · [Firmware](docs/firmware.md) · [Pesquisa e resultados](docs/results.md) · [Apresentação](docs/presentation/README.md) · [English](README.en.md)

## Executar no computador

Use **Python 3.12**. A demonstração não precisa de placa, CUDA ou TensorFlow completo.

```sh
git clone https://github.com/Lawtrel/bitdoglab-heart-tinyml.git
cd bitdoglab-heart-tinyml
python -m venv .venv
```

Ative o ambiente:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```sh
# Linux / Arch WSL
source .venv/bin/activate
```

Instale e abra:

```sh
python -m pip install -e .
heart-tinyml doctor
heart-tinyml serve
```

No Windows, você também pode usar **SETUP_WINDOWS.cmd** uma vez e **START_WINDOWS.cmd** nas próximas execuções. O ambiente deve ser criado nesta pasta; não copie uma `.venv` antiga.

No painel:

1. Escolha **Áudio 1** ou **Áudio 2** e ouça o trecho.
2. Clique em **Analisar no PC** para ver a onda, o MFE e a previsão.
3. Opcionalmente conecte uma placa com o firmware `demo` e use **Comparar o mesmo áudio por USB**.

O servidor atende somente em `127.0.0.1`. O áudio não é enviado a serviços externos. O treino ocorre offline e é separado da inferência.

## Organização

```text
src/heart_tinyml/    Aplicação instalável e painel local
  domain/           Dados, erros e contratos
  application/      Casos de uso de análise e comparação
  adapters/         WAV, LiteRT, arquivos e USB
  web/              HTTP e interface modular
  resources/        Modelo congelado, dois áudios e métricas curadas
firmware/           demo, benchmark, código compartilhado e modelo C++
research/           Pipeline científico e seus testes, preservados separadamente
tests/              Regressão, integridade, USB e limites HTTP da aplicação
docs/               Guias, decisões, artigo em inglês/português e apresentação
tools/              Instalação, build, verificação e gravação explícita
```

Os padrões aplicados são **Ports and Adapters**, **injeção de dependências**, **Repository** e separação **Controller / apresentação**. Cada um tem um propósito concreto, explicado em [architecture.md](docs/architecture.md). Não há hierarquia de classes para cada função numérica.

## Estado das evidências

| Parte | Estado |
|---|---|
| Treinamento e avaliação digital no PC | Concluídos no experimento original |
| Teste digital completo no RP2040 | 6.512 janelas, 471 gravações, 122 grupos |
| Modelo embarcado | INT8, 5.264 bytes, limiar congelado |
| Demonstração A da V2 | Funcionamento confirmado manualmente pelo autor |
| Demo V3 original | Compilada e auditada; confirmação física por USB pendente nos registros |
| Novo layout CMake deste repositório | Fontes reorganizadas; precisa de novo build antes de gravar |
| Microfone / uso clínico / streaming contínuo | Não validados |

Na placa, o teste por grupo apresentou F1 **0,694**, recall **70,8%** e acurácia **87,7%**. Foram identificados 17 de 24 positivos, com sete falsos negativos. O IC95% de F1 foi 0,526–0,829. Esses números não descrevem a precisão do microfone nem a classificação de um único trecho demonstrado.

Os dados e critérios completos estão em [docs/results.md](docs/results.md). As métricas históricas não foram recalculadas ou ajustadas durante a organização do código.

## Testes

```sh
python -m unittest discover -s tests -v
```

Os testes de software não geram resultados científicos. A integração com hardware exige ensaio físico separado. O CI configura os testes da aplicação e os testes unitários da pesquisa sem iniciar treinamento ou download da base.

## Pesquisa, artigo e apresentação

- [Pipeline de pesquisa](research/README.md): download, split por grupo, treino, exportação e avaliação em comandos explícitos.
- [Artigo](docs/article/README.md): fontes em português e inglês. Submissão e revisão final permanecem responsabilidade dos autores.
- [Apresentação](docs/presentation/README.md): PowerPoint, PDF e roteiro. As referências a scripts históricos no roteiro têm equivalentes no guia atual.

Não são versionados o dataset completo, ambientes virtuais, SDKs, compilações, diários com caminhos pessoais ou credenciais. O modelo e os exemplos têm origem e hashes documentados.

## Licença e fontes

Código de autoria do projeto sob [MIT](LICENSE), conforme escolha do autor. Os áudios, a fonte bitmap e as dependências mantêm suas licenças e atribuições próprias: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Consulte as [referências do artigo](docs/article/english/references.bib).
