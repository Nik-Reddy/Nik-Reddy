from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "activity-overview.svg"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
    }
  }
}
"""


def fetch_contributions(username: str, token: str) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)
    payload = {
        "query": QUERY,
        "variables": {
            "login": username,
            "from": one_year_ago.isoformat(),
            "to": now.isoformat(),
        },
    }
    request = Request(
        GITHUB_GRAPHQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-activity-overview",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub API request failed: {error}") from error

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], indent=2))

    collection = result["data"]["user"]["contributionsCollection"]
    return {
        "commits": int(collection["totalCommitContributions"]),
        "issues": int(collection["totalIssueContributions"]),
        "pull_requests": int(collection["totalPullRequestContributions"]),
        "code_reviews": int(collection["totalPullRequestReviewContributions"]),
    }


def percentages(counts: dict[str, int]) -> dict[str, int]:
    total = sum(counts.values())
    if total == 0:
        return {key: 0 for key in counts}

    raw = {key: counts[key] * 100 / total for key in counts}
    rounded = {key: int(raw[key]) for key in counts}
    remainder = 100 - sum(rounded.values())
    order = sorted(counts, key=lambda key: raw[key] - rounded[key], reverse=True)
    for key in order[:remainder]:
        rounded[key] += 1
    return rounded


def point(center: tuple[int, int], pct: int, direction: tuple[int, int]) -> tuple[float, float]:
    radius = 62
    distance = radius * pct / 100
    return center[0] + direction[0] * distance, center[1] + direction[1] * distance


def render_svg(values: dict[str, int]) -> str:
    center = (180, 108)
    commit = point(center, values["commits"], (-1, 0))
    issue = point(center, values["issues"], (1, 0))
    review = point(center, values["code_reviews"], (0, -1))
    pull = point(center, values["pull_requests"], (0, 1))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="220" viewBox="0 0 360 220" role="img" aria-labelledby="title desc">
  <title id="title">GitHub activity overview</title>
  <desc id="desc">Contribution mix for commits, issues, pull requests, and code reviews.</desc>
  <style>
    .axis {{ stroke: #116329; stroke-width: 2; stroke-linecap: round; }}
    .marker {{ fill: #ffffff; stroke: #116329; stroke-width: 2; }}
    .label {{ fill: #3b3663; font: 12px Arial, sans-serif; }}
  </style>
  <line class="axis" x1="180" y1="38" x2="180" y2="178" />
  <line class="axis" x1="92" y1="108" x2="268" y2="108" />
  <circle class="marker" cx="{review[0]:.1f}" cy="{review[1]:.1f}" r="3.4" />
  <circle class="marker" cx="{issue[0]:.1f}" cy="{issue[1]:.1f}" r="3.4" />
  <circle class="marker" cx="{pull[0]:.1f}" cy="{pull[1]:.1f}" r="3.4" />
  <circle class="marker" cx="{commit[0]:.1f}" cy="{commit[1]:.1f}" r="3.4" />
  <circle class="marker" cx="180" cy="108" r="3.4" />
  <text class="label" x="180" y="18" text-anchor="middle">{values["code_reviews"]}%</text>
  <text class="label" x="180" y="32" text-anchor="middle">Code review</text>
  <text class="label" x="278" y="106" text-anchor="start">{values["issues"]}%</text>
  <text class="label" x="278" y="120" text-anchor="start">Issues</text>
  <text class="label" x="180" y="188" text-anchor="middle">{values["pull_requests"]}%</text>
  <text class="label" x="180" y="202" text-anchor="middle">Pull requests</text>
  <text class="label" x="82" y="106" text-anchor="end">{values["commits"]}%</text>
  <text class="label" x="82" y="120" text-anchor="end">Commits</text>
</svg>
"""


def main() -> int:
    username = os.environ.get("GITHUB_USERNAME", "Nik-Reddy")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GH_TOKEN or GITHUB_TOKEN is required", file=sys.stderr)
        return 1

    counts = fetch_contributions(username, token)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(percentages(counts)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
