import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

try:
    # PyGithub v2+ separates authentication in `Auth`.
    # Using `Github(token)` is deprecated and can lead to auth/permission issues.
    from github import Github, Auth, GithubException  # type: ignore
except ModuleNotFoundError:
    # Local execution without PyGithub installed. In GitHub Actions it will exist.
    Github = None  # type: ignore
    Auth = None  # type: ignore
    GithubException = Exception  # type: ignore


COAUTHOR_RE = re.compile(
    r"^\s*Co-authored-by:\s*(?P<name>[^<]+)<(?P<email>[^>]+)>\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def utc_iso_week_bucket(dt: datetime) -> str:
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def bucket_for_commit_len(n: int) -> str:
    if 0 <= n <= 20:
        return "0-20"
    if 21 <= n <= 50:
        return "21-50"
    if 51 <= n <= 100:
        return "51-100"
    if 101 <= n <= 200:
        return "101-200"
    return "200+"


def empty_metrics() -> Dict[str, Any]:
    return {
        "issues_per_week": {"weeks": [], "opened": [], "closed": []},
        "commit_message_histogram": {
            "bins": ["0-20", "21-50", "51-100", "101-200", "200+"],
            "counts": [0, 0, 0, 0, 0],
        },
        "coauthors_per_week": {"weeks": [], "counts": []},
        "commit_heatmap": {
            "days": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
            "hours": list(range(24)),
            "matrix": [[0] * 24 for _ in range(7)],
        },
        "top_committers": {"rows": []},
        "top_pr_authors": {"rows": []},
        "top_issue_contributors": {"rows": []},
    }


def _safe_username(login: str | None) -> str:
    return login or "ghost"


def _write_fallback_metrics() -> None:
    out_path = os.path.join("docs", "productivity", "metrics.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(empty_metrics(), f, ensure_ascii=False, indent=2)


def main() -> None:
    out_path = os.path.join("docs", "productivity", "metrics.json")

    if Github is None:
        # Avoid failing local runs; keep JSON shape valid.
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(empty_metrics(), f, ensure_ascii=False, indent=2)
        return

    token = os.environ.get("GITHUB_TOKEN")
    repo_full_name = os.environ.get("GITHUB_REPOSITORY")

    # Validate before creating the client:
    # - prevents confusing 403 errors that are actually caused by missing/invalid token
    # - keeps the script behavior deterministic in CI
    if not token:
        raise RuntimeError(
            "Missing GITHUB_TOKEN (required to avoid 403 in private repos and to ensure proper API access)."
        )
    if not repo_full_name or "/" not in repo_full_name:
        raise RuntimeError("Missing/invalid GITHUB_REPOSITORY. Expected format: owner/repo")

    # Why 403 happened:
    # - The workflow token may exist, but the client initialized with the deprecated auth style
    #   can fail to send the right Authorization header depending on PyGithub version.
    # - Additionally, GitHub Actions has workflow-level `permissions` that must allow reading.
    #
    # Why Auth.Token is necessary:
    # - New PyGithub versions use an explicit auth object (`Auth.Token`) instead of `Github(token)`.
    # - This is the recommended/forward-compatible method.
    if Auth is None:
        raise RuntimeError("PyGithub Auth is not available in this environment.")

    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo(repo_full_name)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(weeks=52)

    # Fetch issues (exclude PRs)
    issues_per_week_opened: Dict[str, int] = defaultdict(int)
    issues_per_week_closed: Dict[str, int] = defaultdict(int)

    issue_contrib: Dict[str, Dict[str, int]] = defaultdict(lambda: {"opened": 0, "closed": 0})

    # GitHub API: issues endpoint includes PRs; we filter by `pull_request` presence.
    issues = repo.get_issues(state="all", sort="created", direction="desc")
    for iss in issues:
        if iss.pull_request is not None:
            continue
        created_at = iss.created_at
        if created_at < window_start:
            continue

        week = utc_iso_week_bucket(created_at)
        user = _safe_username(getattr(iss.user, "login", None))
        issues_per_week_opened[week] += 1
        issue_contrib[user]["opened"] += 1

        if iss.state == "closed":
            closed_at = iss.closed_at
            if closed_at and closed_at >= window_start:
                week_c = utc_iso_week_bucket(closed_at)
                issues_per_week_closed[week_c] += 1
                issue_contrib[user]["closed"] += 1

    # Commits + message histogram + heatmap + coauthors
    commit_hist: Dict[str, int] = {"0-20": 0, "21-50": 0, "51-100": 0, "101-200": 0, "200+": 0}
    heat_matrix = [[0] * 24 for _ in range(7)]
    # Coauthors per week (counts of matching lines)
    coauthors_per_week: Dict[str, int] = defaultdict(int)

    top_committers: Dict[str, int] = defaultdict(int)

    # Commits iterable: use `since` to reduce volume.
    commits = repo.get_commits(since=window_start)
    for c in commits:
        # Note: committer may be None
        committer = getattr(c, "committer", None)
        commit_date = getattr(committer, "date", None) or getattr(c.author, "date", None)  # type: ignore
        if not commit_date:
            continue
        week = utc_iso_week_bucket(commit_date)

        msg = (
            getattr(c, "commit", None).get("message")
            if isinstance(getattr(c, "commit", None), dict)
            else getattr(c.commit, "message", "")
        )
        if not isinstance(msg, str):
            msg = ""

        msg_len = len(msg) if msg else 0
        bin_name = bucket_for_commit_len(msg_len)
        commit_hist[bin_name] += 1

        hour = commit_date.astimezone(timezone.utc).hour
        day_idx = commit_date.astimezone(timezone.utc).weekday()
        heat_matrix[day_idx][hour] += 1

        # coauthors lines
        for _m in COAUTHOR_RE.finditer(msg or ""):
            coauthors_per_week[week] += 1

        author_login = None
        author = getattr(c, "author", None)
        if author and getattr(author, "login", None):
            author_login = author.login
        else:
            author_login = None
        user = _safe_username(author_login)
        top_committers[user] += 1

    # PR authors (currently open PRs)
    top_pr_authors_counts: Dict[str, int] = defaultdict(int)
    prs = repo.get_pulls(state="open", sort="created", direction="desc")
    for pr in prs:
        user = _safe_username(getattr(pr.user, "login", None))
        top_pr_authors_counts[user] += 1

    # Weeks axis: generate buckets from window_start to now.
    # Keeps output stable even when there are no events.

    weeks_axis: List[str] = []
    cur = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cur <= now:
        weeks_axis.append(utc_iso_week_bucket(cur))
        cur = cur + timedelta(weeks=1)

    issues_open_series = [issues_per_week_opened.get(w, 0) for w in weeks_axis]
    issues_closed_series = [issues_per_week_closed.get(w, 0) for w in weeks_axis]
    coauthors_series = [coauthors_per_week.get(w, 0) for w in weeks_axis]

    def top_rows(d: Dict[str, int], limit: int = 10) -> List[Dict[str, Any]]:
        items = sorted(d.items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"rank": i + 1, "username": user, "total": total}
            for i, (user, total) in enumerate(items[:limit])
        ]

    top_committers_rows = top_rows(top_committers, 10)
    top_pr_authors_rows = top_rows(top_pr_authors_counts, 10)

    issue_totals: Dict[str, int] = {u: v["opened"] + v["closed"] for u, v in issue_contrib.items()}
    sorted_users = sorted(issue_totals.items(), key=lambda kv: kv[1], reverse=True)
    limit = 10 if len(sorted_users) >= 10 else len(sorted_users)
    top_issue_rows = []
    for i, (user, total) in enumerate(sorted_users[:limit]):
        opened = issue_contrib[user]["opened"]
        closed = issue_contrib[user]["closed"]
        top_issue_rows.append(
            {"rank": i + 1, "username": user, "opened": opened, "closed": closed, "total": total}
        )

    payload = empty_metrics()
    payload["issues_per_week"]["weeks"] = weeks_axis
    payload["issues_per_week"]["opened"] = issues_open_series
    payload["issues_per_week"]["closed"] = issues_closed_series

    payload["commit_message_histogram"]["counts"] = [
        commit_hist["0-20"],
        commit_hist["21-50"],
        commit_hist["51-100"],
        commit_hist["101-200"],
        commit_hist["200+"],
    ]

    payload["coauthors_per_week"]["weeks"] = weeks_axis
    payload["coauthors_per_week"]["counts"] = coauthors_series

    payload["commit_heatmap"]["matrix"] = heat_matrix

    payload["top_committers"]["rows"] = top_committers_rows
    payload["top_pr_authors"]["rows"] = top_pr_authors_rows
    payload["top_issue_contributors"]["rows"] = top_issue_rows

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Improve error handling:
        # - avoid huge tracebacks when the root cause is permission/auth (403)
        # - keep metrics.json valid so the frontend doesn't break
        err_msg = f"[collect_productivity_metrics] ERROR: {e}"

        try:
            if isinstance(e, GithubException):
                status = getattr(e, "status", None)
                if status == 403:
                    err_msg = (
                        "[collect_productivity_metrics] ERROR: 403 Forbidden from GitHub API. "
                        "Check workflow `permissions` and ensure GITHUB_TOKEN is set and has access."
                    )
                elif status == 401:
                    err_msg = (
                        "[collect_productivity_metrics] ERROR: 401 Unauthorized from GitHub API. "
                        "Check that GITHUB_TOKEN is valid and not empty."
                    )
        except Exception:
            pass

        sys.stderr.write(err_msg + "\n")
        _write_fallback_metrics()
        raise

