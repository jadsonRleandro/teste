# TODO - Correção 403 PyGithub + workflow

- [x] Atualizar `teste/scripts/collect_productivity_metrics.py` para:
  - [x] Validar existência/format do `GITHUB_TOKEN` e `GITHUB_REPOSITORY` antes de inicializar o cliente
  - [x] Trocar `Github(token)` (deprecated) por `Auth.Token(token)` conforme solicitado
  - [x] Tratar exceções da API (PyGithub) com mensagens curtas e sem traceback gigante

  - [x] Adicionar comentários explicando por que ocorria 403 e por que `Auth.Token` é necessário
  - [x] Garantir compatibilidade com repositórios públicos e privados
  - [x] Procurar outras chamadas depreciadas no projeto e atualizar

- [x] Criar workflow `.github/workflows/productivity-metrics.yml` (pois não existe no repo atual) com:
  - [x] `permissions:` adequadas: `contents: read`, `issues: read`, `pull-requests: read`
  - [x] `schedule` semanal e `workflow_dispatch` (conforme padrão)
  - [x] Setup de Python e instalação de dependência `PyGithub`
  - [x] Execução do script apontando para o path correto

- [x] (Após edições) Rodar `python -m py_compile` no script e/ou um passo de lint simples.
- [x] Atualizar `metrics.json` local (fallback vazio quando não há token).



