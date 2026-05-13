# TODO - GitHub Action: Commit Metrics by Sprint

- [x] Criar `requirements.txt` com dependência PyGithub.
- [x] Criar `scripts/collect_sprint_metrics.py` (API GitHub -> agrupar por sprints de 14 dias -> gerar JSON).
- [x] Criar workflow `.github/workflows/commit-metrics.yml` com gatilhos (push main, workflow_dispatch, cron opcional).
- [x] Garantir boas práticas no workflow (permissões, checkout, instalar deps, salvar JSON em `metrics/commits_by_sprint.json`).
- [x] Evitar loop infinito (skip se commit final foi do `github-actions[bot]`, e commit apenas se arquivo mudou).
- [ ] (Opcional) Rodar validação local do script (com token real) e checar formato do JSON.

