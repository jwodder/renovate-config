#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.10"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

"""
Collect all "Awaiting Schedule" items from Renovate dashboards for your GitHub
repositories and write them to ``awaiting.md``

This script requires a GitHub access token with appropriate permissions in
order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
environment variable (possibly in an `.env` file), by storing a token with
the `gh` or `hub` command, or by setting the `hub.oauthtoken` Git config
option in your `~/.gitconfig` file.
"""

from __future__ import annotations
from collections.abc import Iterator
import logging
import re
import ghreq
from ghreq import PrettyHTTPError
from ghtoken import get_ghtoken

RENOVATE_CONFIG_PATH = ".github/renovate.json5"
RENOVATE_DASHBOARD_LABEL = "dashboard"


class Client(ghreq.Client):
    def get_my_repos(self) -> Iterator[str]:
        for r in self.paginate("/user/repos"):
            if not r["archived"] and not r["fork"]:
                yield r["full_name"]

    def path_exists(self, repo: str, path: str) -> bool:
        try:
            self.request(
                "HEAD",
                f"/repos/{repo}/contents/{path}",
                raw=True,
            )
        except PrettyHTTPError as e:
            if e.response.status_code == 404:
                return False
            else:
                raise e
        else:
            return True

    def get_dashboard_issue(self, repo: str) -> int | None:
        p = self.paginate(f"/repos/{repo}/issues", params={"labels": "dashboard"})
        if (issue := next(p, None)) is not None:
            n = issue["number"]
            assert isinstance(n, int)
            return n
        else:
            return None

    def get_issue_body(self, repo: str, issue: int) -> str:
        s = self.get(f"/repos/{repo}/issues/{issue}")["body"]
        assert isinstance(s, str)
        return s


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG,
    )
    for h in logging.getLogger().handlers:
        h.addFilter(nodebug_urllib3)
    with open("awaiting.md", "w", encoding="utf-8") as fp:
        with Client(token=get_ghtoken()) as client:
            for repo in client.get_my_repos():
                if client.path_exists(repo, RENOVATE_CONFIG_PATH):
                    print(repo, file=fp)
                    print("=" * len(repo), file=fp)
                    print(file=fp)
                    if (dashboard := client.get_dashboard_issue(repo)) is not None:
                        print(
                            f"<https://github.com/{repo}/issues/{dashboard}>", file=fp
                        )
                        print(file=fp)
                        body = client.get_issue_body(repo, dashboard)
                        if awaiting := get_awaiting_from_dashboard_body(body):
                            for a in awaiting:
                                print(f"- {a}", file=fp)
                        else:
                            print("Nothing awaiting schedule", file=fp)
                    else:
                        print("No dashboard", file=fp)
                    print(file=fp)


def nodebug_urllib3(record: logging.LogRecord) -> bool:
    if record.name == "urllib3" or record.name.startswith("urllib3."):
        return record.levelno > logging.DEBUG
    else:
        return True


def get_awaiting_from_dashboard_body(body: str) -> list[str]:
    awaiting = []
    in_awaiting = False
    for line in body.splitlines():
        if line == "## Awaiting Schedule":
            in_awaiting = True
        elif in_awaiting and line.startswith("## "):
            in_awaiting = False
        if in_awaiting and (
            (
                m := re.fullmatch(
                    r"\s*-\s*(?P<check>\[[ x]\])\s*(?:<!-- .*? -->)?(?P<text>.+)", line
                )
            )
            is not None
        ):
            if m["check"] == "[x]":
                s = f"[x] {m['text']}"
            else:
                s = m["text"]
            awaiting.append(s)
    return awaiting


if __name__ == "__main__":
    main()
