import json
import sys
from pathlib import Path

import click

from .config import AppConfig
from .models import GitCommit
from .parser import get_commits
from .rules import CommitRuleResult, Ruleset, load_ruleset


def _serialize_commit(commit: GitCommit) -> dict:
    return {
        "sha": commit.sha,
        "short_sha": commit.short_sha,
        "subject": commit.subject,
        "description": commit.description,
        "body": commit.body,
        "trailers": [{"token": t.token, "value": t.value} for t in commit.trailers],
        "parent_shas": commit.parent_shas,
        "changed_files": commit.changed_files,
        "is_fixup": commit.is_fixup,
        "is_squash": commit.is_squash,
        "is_amend": commit.is_amend,
        "is_merge": commit.is_merge,
        "is_revert": commit.is_revert,
        "author_name": commit.author_name,
        "author_email": commit.author_email,
        "author_date": commit.author_date.isoformat(),
        "committer_name": commit.committer_name,
        "committer_email": commit.committer_email,
        "committer_date": commit.committer_date.isoformat(),
    }


def _print_text(commits: list[GitCommit]) -> None:
    for commit in commits:
        flags = []
        if commit.is_fixup:
            flags.append("fixup")
        if commit.is_squash:
            flags.append("squash")
        if commit.is_merge:
            flags.append("merge")
        if commit.is_revert:
            flags.append("revert")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""

        click.echo(f"{commit.short_sha}  {commit.subject}{flag_str}")
        if commit.description:
            for line in commit.description.splitlines():
                click.echo(f"            {line}")
        if commit.trailers:
            for trailer in commit.trailers:
                click.echo(f"            {trailer}")
        click.echo()


@click.command()
@click.argument(
    "repo_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--base-ref",
    "-b",
    default=None,
    help=(
        "Base ref for range (e.g. 'main', 'origin/main'). "
        "In GitLab CI use $CI_MERGE_REQUEST_DIFF_BASE_SHA."
    ),
)
@click.option(
    "--head-ref",
    "-H",
    default="HEAD",
    show_default=True,
    help="Head ref to analyze.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    default="text",
    show_default=True,
    type=click.Choice(["text", "json"]),
    help="Output format.",
)
@click.option(
    "--no-merges",
    is_flag=True,
    default=False,
    help="Exclude merge commits from output.",
)
@click.option(
    "--ruleset",
    "-r",
    "ruleset_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="YAML ruleset file. When provided, commits are checked and a non-zero exit code is returned on any failure.",
)
def main(
    repo_path: Path,
    base_ref: str | None,
    head_ref: str,
    output_format: str,
    no_merges: bool,
    ruleset_path: Path | None,
) -> None:
    """Analyze git commits in REPO_PATH.

    Without --base-ref, shows the single commit at HEAD.
    With --base-ref, shows all commits in the range BASE_REF..HEAD_REF —
    suitable for MR/PR analysis in CI.

    \b
    Examples:
      git-commit-analyzer .
      git-commit-analyzer . --base-ref main
      git-commit-analyzer . --base-ref origin/main --head-ref feature-branch
      git-commit-analyzer . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --format json
      git-commit-analyzer . --base-ref main --ruleset rules.yml
    """
    try:
        commits = get_commits(repo_path, base_ref=base_ref, head_ref=head_ref)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if no_merges:
        commits = [c for c in commits if not c.is_merge]

    if not commits:
        click.echo("No commits found.", err=True)
        sys.exit(0)

    if ruleset_path is not None:
        try:
            ruleset_file = load_ruleset(ruleset_path)
        except Exception as exc:
            click.echo(f"Error loading ruleset: {exc}", err=True)
            sys.exit(1)
        if ruleset_file.config.debug:
            click.echo(
                f"[debug] Loaded {len(ruleset_file.ruleset.rules)} rule(s). "
                f"Checking {len(commits)} commit(s).",
                err=True,
            )
        _run_ruleset(commits, ruleset_file.ruleset, output_format, ruleset_file.config)
    elif output_format == "json":
        click.echo(json.dumps([_serialize_commit(c) for c in commits], indent=2))
    else:
        _print_text(commits)


def _run_ruleset(
    commits: list[GitCommit],
    ruleset: Ruleset,
    output_format: str,
    config: AppConfig | None = None,
) -> None:
    if config is None:
        config = AppConfig()

    failures = ruleset.check_commits(commits)

    if output_format == "json":
        click.echo(json.dumps([_serialize_rule_result(r) for r in failures], indent=2))
    else:
        for result in failures:
            click.echo(f"FAIL  {result.commit.short_sha}  {result.commit.subject}")
            click.echo(f"      rule: {result.rule_name}")
            for checker_name, message in result.failures:
                click.echo(f"      {checker_name}: {message}")
            click.echo()

        total = len(commits)
        if failures:
            click.echo(f"{len(failures)} failure(s) across {total} commit(s).")
            sys.exit(config.exit_code_on_failure)
        else:
            click.echo(f"All {total} commit(s) passed.")


def _serialize_rule_result(result: CommitRuleResult) -> dict:
    return {
        "sha": result.commit.sha,
        "short_sha": result.commit.short_sha,
        "subject": result.commit.subject,
        "rule": result.rule_name,
        "failures": [
            {"checker": name, "message": msg} for name, msg in result.failures
        ],
    }
