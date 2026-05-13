import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


from dateutil import parser as date_parser
from github import Github

# 14 dias fixos
SPRINT_DAYS = 14


@dataclass(frozen=True)
class SprintBucket:
    name: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD


def to_iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_github_datetime(value: str) -> datetime:
    # GitHub retorna timestamps ISO 8601
    dt = date_parser.isoparse(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def first_commit_datetime(commits) -> Optional[datetime]:
    # Ordenação: a API de commits retorna ordem do mais recente para o mais antigo
    # Ao iterar, o último visto tende a ser o mais antigo.
    # Como temos paginação, capturamos o mínimo no final do processamento.
    return commits


def compute_sprint_bucket(commit_dt: datetime, start_base: datetime, sprint_index: int) -> SprintBucket:
    start = start_base + sprint_index * timedelta_days(SPRINT_DAYS)
    end = start + timedelta_days(SPRINT_DAYS) - timedelta_seconds(1)

    # Convertendo para datas locais (YYYY-MM-DD) em UTC
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    start_date = start_utc.date().isoformat()
    end_date = end_utc.date().isoformat()
    return SprintBucket(name=f"Sprint {sprint_index + 1}", start_date=start_date, end_date=end_date)


def timedelta_days(days: int):
    from datetime import timedelta
    return timedelta(days=days)


def timedelta_seconds(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=seconds)


def get_sprint_index(commit_dt: datetime, base_dt: datetime) -> int:
    # Index baseado em buckets de 14 dias iniciando em base_dt (UTC)
    delta_days = (commit_dt - base_dt).total_seconds() / 86400.0
    if delta_days < 0:
        return 0
    return int(delta_days // SPRINT_DAYS)


def fetch_all_commits(repo, token: str) -> List[dict]:
    """Busca todos os commits via API de commits.

    Observações:
    - A API de commits tem paginação; PyGithub abstrai com paginação.
    - Não usamos search commits para evitar limites e complexidade.
    """
    all_commits = []

    # Para repositórios grandes, a listagem completa pode ser custosa.
    # Tentamos buscar o máximo possível dentro de limites da API.
    # Mesmo assim, manteremos um tratamento de erro básico.
    try:
        commits = repo.get_commits(all=True)
        for c in commits:
            all_commits.append(c)
    except Exception as e:
        raise RuntimeError(f"Falha ao buscar commits via API: {e}") from e

    return all_commits


def is_merge_commit(commit) -> bool:
    # Heurística: commits de merge frequentemente possuem message iniciando com 'Merge'
    # e/ou dois parents.
    try:
        msg = (commit.commit.message or "").lower()
        parents = getattr(commit, "parents", [])
        parent_count = len(parents)
        return msg.startswith("merge") or parent_count >= 2
    except Exception:
        return False


def author_login(commit) -> str:
    # GitHub commit.author pode ser None; fallback para committer
    author = getattr(commit, "author", None)
    if author is not None and getattr(author, "login", None):
        return author.login

    # fallback: name
    try:
        return commit.commit.author.name
    except Exception:
        return "unknown"


def main() -> int:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Variável de ambiente GITHUB_TOKEN não definida.", file=sys.stderr)
        return 2

    repo_full_name = os.getenv("GITHUB_REPOSITORY")
    if not repo_full_name or "/" not in repo_full_name:
        print("Variável de ambiente GITHUB_REPOSITORY inválida.", file=sys.stderr)
        return 2

    # Inicializa cliente
    g = Github(token)
    owner, repo_name = repo_full_name.split("/", 1)
    repo = g.get_repo(repo_full_name)

    output_path = os.getenv("OUTPUT_JSON", "metrics/commits_by_sprint.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Buscando commits do repositório: {repo_full_name}")
    commits = fetch_all_commits(repo, token)

    if not commits:
        data = {
            "generated_at": to_iso_utc(datetime.now(timezone.utc)),
            "repository": repo_full_name,
            "sprints": [],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Nenhum commit encontrado.")
        return 0

    # Determinar a base de start dos sprints: primeiro commit (mais antigo) em UTC truncado ao dia.
    # Precisamos do mais antigo, então ordenamos por commit date.
    commit_dates: List[datetime] = []
    for c in commits:
        commit_dates.append(parse_github_datetime(c.commit.author.date))

    min_dt = min(commit_dates)
    base_dt = datetime(min_dt.year, min_dt.month, min_dt.day, tzinfo=timezone.utc)

    # Agregação
    sprints_map = {}
    total_commits_per_sprint = Counter()
    merge_commits_per_sprint = Counter()
    authors_per_sprint: Dict[int, Counter] = defaultdict(Counter)

    for c in commits:
        dt = parse_github_datetime(c.commit.author.date)
        idx = get_sprint_index(dt, base_dt)

        if idx not in sprints_map:
            bucket = compute_sprint_bucket(dt, base_dt, idx)
            sprints_map[idx] = bucket

        total_commits_per_sprint[idx] += 1
        if is_merge_commit(c):
            merge_commits_per_sprint[idx] += 1

        authors_per_sprint[idx][author_login(c)] += 1

    # Ordenar sprints por idx
    sprint_list = []
    for idx in sorted(sprints_map.keys()):
        bucket = sprints_map[idx]
        authors_counter = authors_per_sprint.get(idx, Counter())
        authors_dict = dict(authors_counter.most_common())

        sprint_list.append(
            {
                "sprint": bucket.name,
                "start_date": bucket.start_date,
                "end_date": bucket.end_date,
                "total_commits": int(total_commits_per_sprint[idx]),
                "merge_commits": int(merge_commits_per_sprint[idx]),
                "authors": authors_dict,
            }
        )

    result = {
        "generated_at": to_iso_utc(datetime.now(timezone.utc)),
        "repository": repo_full_name,
        "sprints": sprint_list,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"JSON gerado em: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

