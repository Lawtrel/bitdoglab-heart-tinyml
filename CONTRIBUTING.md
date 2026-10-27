# Como contribuir

Use Python 3.12 e execute os testes antes de enviar alterações:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

O modelo, a normalização e o limiar embarcados estão congelados. Uma mudança nesses recursos exige outra versão, nova calibração/avaliação e atualização das evidências. Não ajuste pelo teste concluído.

A aplicação usa contratos Predictor, AudioDecoder e BoardGateway. Adicione outro runtime ou transporte como adapter e conecte-o em bootstrap.py. Os casos de uso não devem importar HTTP, serial ou LiteRT.

O pacote research preserva o pipeline científico e tem seus próprios testes. Testes sintéticos não são resultados científicos. Uma alteração na demonstração não valida a aquisição pelo microfone.

Não envie dataset completo, ambientes virtuais, SDKs, credenciais, portas locais ou recibos com caminhos pessoais. Relatórios publicáveis devem informar origem, unidade de agregação e condições de medição.
