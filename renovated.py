#!/usr/bin/env -S pipx run
# /// script
# requires-python = ">=3.10"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

"""
Output a CSV listing your GitHub repositories and whether they contain a
``.github/renovate.json5`` file.

This script requires a GitHub access token with appropriate permissions in
order to run.  Specify the token via the `GH_TOKEN` or `GITHUB_TOKEN`
environment variable (possibly in an `.env` file), by storing a token with
the `gh` or `hub` command, or by setting the `hub.oauthtoken` Git config
option in your `~/.gitconfig` file.
"""

from __future__ import annotations
from collections.abc import Iterator
import csv
import sys
import ghreq
from ghreq import PrettyHTTPError
from ghtoken import get_ghtoken

RENOVATE_CONFIG_PATH = ".github/renovate.json5"


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


def main() -> None:
    out = csv.DictWriter(sys.stdout, ["repo", "renovated"])
    out.writeheader()
    with Client(token=get_ghtoken()) as client:
        for repo in client.get_my_repos():
            renovated = client.path_exists(repo, RENOVATE_CONFIG_PATH)
            out.writerow({"repo": repo, "renovated": "t" if renovated else "f"})


if __name__ == "__main__":
    main()
