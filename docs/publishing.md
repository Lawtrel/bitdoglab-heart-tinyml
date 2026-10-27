# Publicação do repositório

O repositório público previsto é https://github.com/Lawtrel/bitdoglab-heart-tinyml. O código de autoria do projeto usa MIT; recursos de terceiros mantêm suas licenças.

O primeiro envio pode ser feito por `PUBLICAR_GITHUB.cmd`, na raiz, ou por `git push -u origin main`. O iniciador verifica origin, branch e ausência de mudanças sem commit. Ele não adiciona arquivos nem faz envio forçado. A autenticação pertence ao Git do computador.

Antes de novos envios:

```sh
python tools/check_publication.py
python -m unittest discover -s tests -v
git status
```

Revise o diff e crie seu commit explicitamente. Não envie dataset, ambientes, chaves, SDKs ou diários com caminhos pessoais.

O CI executa no GitHub após o push. Uma configuração de CI no repositório não prova sucesso de uma execução: confira o estado e os logs da rodada correspondente ao commit.
