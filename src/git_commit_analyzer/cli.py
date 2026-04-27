import json
import os
import sys
from pathlib import Path

import click

from .config import AppConfig
from .download import download_model
from .models import GitCommit
from .parser import get_commits
from .rules import CommitRuleResult, Ruleset, load_configs


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


@click.group()
@click.option(
    "--color/--no-color",
    default=None,
    help="Force enable or disable ANSI colors. Also respects FORCE_COLOR env var.",
)
@click.pass_context
def main(ctx: click.Context, color: bool | None) -> None:
    """Git commit analyzer for CI pipelines."""
    if color is not None:
        ctx.color = color
    elif os.environ.get("FORCE_COLOR"):
        ctx.color = True


@main.command("analyze")
@click.pass_context
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
    "--config",
    "-c",
    "config_paths",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="YAML config file. Repeat to load multiple files; rules are concatenated and configs merged (last wins).",
)
@click.option(
    "--top-n",
    "-n",
    "top_n",
    default=None,
    type=click.IntRange(min=1),
    help="Limit analysis to the N most recent commits.",
)
def analyze(
    ctx: click.Context,
    repo_path: Path,
    base_ref: str | None,
    head_ref: str,
    output_format: str,
    no_merges: bool,
    config_paths: tuple[Path, ...],
    top_n: int | None,
) -> None:
    """Analyze git commits in REPO_PATH.

    Without --base-ref, shows the single commit at HEAD.
    With --base-ref, shows all commits in the range BASE_REF..HEAD_REF —
    suitable for MR/PR analysis in CI.

    \b
    Examples:
      gca analyze .
      gca analyze . --base-ref main
      gca analyze . --base-ref origin/main --head-ref feature-branch
      gca analyze . --base-ref $CI_MERGE_REQUEST_DIFF_BASE_SHA --format json
      gca analyze . --base-ref main --config rules.yml
      gca analyze . --base-ref main --top-n 10
    """
    try:
        commits = get_commits(repo_path, base_ref=base_ref, head_ref=head_ref)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if no_merges:
        commits = [c for c in commits if not c.is_merge]

    if top_n is not None:
        commits = commits[:top_n]

    if not commits:
        click.echo("No commits found.", err=True)
        sys.exit(0)

    if config_paths:
        try:
            config_file = load_configs(list(config_paths))
        except Exception as exc:
            click.echo(f"Error loading config: {exc}", err=True)
            sys.exit(1)
        if config_file.config.debug:
            click.echo(
                f"[debug] Loaded {len(config_file.ruleset.rules)} rule(s) "
                f"from {len(config_paths)} file(s). "
                f"Checking {len(commits)} commit(s).",
                err=True,
            )
        _run_config(
            commits,
            config_file.ruleset,
            output_format,
            config_file.config,
            color=ctx.color,
        )
    elif output_format == "json":
        click.echo(json.dumps([_serialize_commit(c) for c in commits], indent=2))
    else:
        _print_text(commits)


@main.command("download-model")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="YAML config file to read repo_id and filename from.",
)
@click.option("--repo-id", default=None, help="Hugging Face repository ID.")
@click.option(
    "--filename", default=None, help="Filename glob pattern, e.g. '*q4.gguf'."
)
def download_model_cmd(
    config_path: Path | None,
    repo_id: str | None,
    filename: str | None,
) -> None:
    """Download an LLM model file from Hugging Face into the local cache.

    Reads repo_id and filename from --config if not supplied directly.

    \b
    Examples:
      gca download-model --config llm-config.yml
      gca download-model --repo-id Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF --filename '*q4_k_m.gguf'
    """
    if config_path is not None:
        from .rules import load_config

        cf = load_config(config_path)
        if cf.config.llm is None:
            click.echo("Error: config file has no 'config.llm' section.", err=True)
            sys.exit(1)
        repo_id = repo_id or cf.config.llm.repo_id
        filename = filename or cf.config.llm.filename

    if not repo_id or not filename:
        click.echo(
            "Error: --repo-id and --filename are required when --config is not provided.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Downloading {filename!r} from {repo_id!r} ...")
    try:
        path = download_model(repo_id, filename)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Saved to: {path}")


def _run_config(
    commits: list[GitCommit],
    ruleset: Ruleset,
    output_format: str,
    config: AppConfig | None = None,
    color: bool | None = None,
) -> None:
    if config is None:
        config = AppConfig()

    total = len(commits)

    if output_format == "json":
        failures = list(ruleset.iter_check_commits(commits))
        click.echo(json.dumps([_serialize_rule_result(r) for r in failures], indent=2))
        if failures:
            sys.exit(config.exit_code_on_failure)
        return

    failure_count = 0
    for result in ruleset.iter_check_commits(commits):
        failure_count += 1
        sha = click.style(result.commit.short_sha, fg="yellow")
        subject = click.style(result.commit.subject, bold=True)
        click.echo(
            click.style("✗ ", fg="red", bold=True) + f"{sha}  {subject}", color=color
        )
        click.echo(
            f"  {'rule:':<10}" + click.style(result.rule_name, fg="cyan"), color=color
        )
        for checker_name, message in result.failures:
            label = click.style(f"  {checker_name + ': ':<10}", dim=True)
            click.echo(label + message, color=color)
        click.echo()

    if failure_count:
        summary = click.style(f"{failure_count} failure(s)", fg="red", bold=True)
        click.echo(f"{summary} across {total} commit(s).", color=color)
        sys.exit(config.exit_code_on_failure)
    else:
        click.echo(
            click.style(f"✓ All {total} commit(s) passed.", fg="green", bold=True),
            color=color,
        )


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
