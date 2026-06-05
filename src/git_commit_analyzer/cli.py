import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import AppConfig
from .download import download_model
from .models import GitCommit
from .parser import get_commits
from .rules import CommitRuleResult, Ruleset, load_configs


def _make_console(color: bool | None) -> Console:
    """Build a :class:`rich.console.Console` honoring the CLI color preference.

    ``color`` is ``True`` to force ANSI on (e.g. in CI via FORCE_COLOR),
    ``False`` to force it off, or ``None`` to let rich auto-detect.
    """
    if color is True:
        return Console(force_terminal=True)
    if color is False:
        return Console(no_color=True)
    return Console()


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


def _commit_panel(commit: GitCommit) -> Panel:
    """Build a bordered panel showing the commit data that checkers see."""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="right", style="cyan", no_wrap=True)
    grid.add_column(overflow="fold")

    grid.add_row("subject", Text(commit.subject, style="bold"))
    if commit.description:
        grid.add_row("description", commit.description)
    grid.add_row(
        "files",
        "\n".join(commit.changed_files)
        if commit.changed_files
        else "[dim](none)[/dim]",
    )
    if commit.trailers:
        grid.add_row("trailers", "\n".join(str(t) for t in commit.trailers))

    flags = []
    if commit.is_fixup:
        flags.append("fixup")
    if commit.is_squash:
        flags.append("squash")
    if commit.is_amend:
        flags.append("amend")
    if commit.is_merge:
        flags.append("merge")
    if commit.is_revert:
        flags.append("revert")
    if flags:
        grid.add_row("flags", Text(", ".join(flags), style="magenta"))

    grid.add_row("author", f"{commit.author_name} <{commit.author_email}>")

    return Panel(grid, title="commit", title_align="left", border_style="blue")


def _check_line(console: Console, name: str, status: Text, dot_style: str) -> Text:
    """Build a ``  name ........ status`` line with a dotted leader.

    The leader fills the console width so the status column lines up regardless
    of how long each checker name is, and is colored (``dot_style``) to match
    the pass/fail status.
    """
    indent = 2
    # 2 = the single space on each side of the dot leader.
    dots = max(3, console.width - indent - len(name) - status.cell_len - 2)
    line = Text(" " * indent)
    line.append(name, style="bold")
    line.append(" ")
    line.append("." * dots, style=dot_style)
    line.append(" ")
    line.append_text(status)
    return line


def _render_commit(
    console: Console, commit: GitCommit, results: list[CommitRuleResult]
) -> int:
    """Render the analysis block for one commit. Returns its failing-rule count."""
    console.rule(style="dim")
    console.print(
        Text.assemble(
            ("Analyzing: ", "bold"),
            (commit.short_sha, "bold yellow"),
            ("  ", ""),
            (commit.subject, "bold"),
        )
    )
    console.print(_commit_panel(commit))
    console.print()

    failing = 0
    if not results:
        console.print("  [dim](no rules apply to this commit)[/dim]")
    for result in results:
        if not result.passed:
            failing += 1
        console.print(Text.assemble(("rule: ", "dim"), (result.rule_name, "cyan")))
        for check in result.checks:
            if check.passed:
                status = Text("✓ PASS", style="green")
                dot_style = "green dim"
            else:
                status = Text("✗ FAIL", style="bold red")
                dot_style = "red dim"
            console.print(_check_line(console, check.checker_name, status, dot_style))
            if not check.passed:
                # Pad the whole message block so wrapped continuation lines stay
                # indented under the first line rather than falling back to col 0.
                console.print(Padding(Text(check.message, style="red"), (0, 0, 0, 6)))
        console.print()

    commit_passed = all(r.passed for r in results)
    if commit_passed:
        console.rule("PASSED", style="green", characters="=")
    else:
        console.rule("FAILED", style="bold red", characters="=")
    console.print()
    return failing


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

    console = _make_console(color)

    failure_count = 0
    for commit, results in ruleset.iter_commit_results(commits):
        failure_count += _render_commit(console, commit, results)

    if failure_count:
        console.print(
            Text.assemble(
                (f"{failure_count} failure(s)", "bold red"),
                (f" across {total} commit(s).", ""),
            )
        )
        sys.exit(config.exit_code_on_failure)
    else:
        console.print(Text(f"✓ All {total} commit(s) passed.", style="bold green"))


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
