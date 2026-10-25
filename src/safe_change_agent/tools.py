import fnmatch
import re
from pathlib import Path

from minsearch import Index

from safe_change_agent.data import (
    CODE_EXTENSIONS,
    DEFAULT_REPO_DIR,
    build_docs_index,
    is_skipped,
    load_docs,
)


class CodebaseTools:
    """Read-only tools for investigating a codebase."""

    def __init__(self, repo_dir: Path, docs_index: Index, max_results: int = 50, max_lines: int = 200):
        self.repo_dir = repo_dir.resolve()
        self.docs_index = docs_index
        self.max_results = max_results
        self.max_lines = max_lines

    def _resolve(self, path: str) -> Path:
        full = (self.repo_dir / path).resolve()
        if not full.is_relative_to(self.repo_dir):
            raise ValueError(f"path outside the repo: {path}")
        return full

    def _code_files(self, root: Path):
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(self.repo_dir)
            if path.is_file() and not is_skipped(rel) and path.suffix in CODE_EXTENSIONS:
                yield path, rel

    def list_files(self, directory: str = ".", pattern: str | None = None) -> list[str]:
        """
        List files in the repo under a directory. Call this first to see which
        services exist and where their infrastructure (infra/) and handler (app/) code lives.

        Args:
            directory: Directory relative to the repo root, e.g. "lib/services/claims".
            pattern: Optional glob on the file name, e.g. "*.ts".

        Returns:
            Relative file paths (max 200).
        """
        try:
            root = self._resolve(directory)
        except ValueError as e:
            return [f"Error: {e}"]
        if not root.is_dir():
            return [f"Error: directory {directory} does not exist"]

        files = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(self.repo_dir)
            if not path.is_file() or is_skipped(rel):
                continue
            if pattern and not fnmatch.fnmatch(path.name, pattern):
                continue
            files.append(str(rel))
        return files[:200]

    def search_code(self, pattern: str, path_glob: str | None = None) -> list[str]:
        """
        Search the code with a case-insensitive regex. Use it to find where an
        event, field, table, type or function is defined or used. Event names
        appear in different forms in code, so search variations, e.g.
        "Claim.?Accepted|CLAIM_ACCEPTED".

        Args:
            pattern: Python regular expression.
            path_glob: Optional glob on the relative path, e.g. "lib/services/claims/*".

        Returns:
            Matches as "file:line: text" (max 50).
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return [f"Error: invalid regex: {e}"]

        matches = []
        searched = 0
        for path, rel in self._code_files(self.repo_dir):
            if path_glob and not fnmatch.fnmatch(str(rel), path_glob):
                continue
            searched += 1
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(lines, start=1):
                if regex.search(line):
                    matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                    if len(matches) >= self.max_results:
                        matches.append("... more matches, narrow the pattern or path_glob")
                        return matches
        if path_glob and searched == 0:
            return [f"Error: no files match path_glob {path_glob}, check the path with list_files"]
        return matches

    def read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """
        Read lines from a file, prefixed with line numbers. Use it after
        search_code or list_files to read the actual code before making claims,
        and cite what you read as file:line.

        Args:
            path: File path relative to the repo root.
            start_line: First line to read (1-based).
            end_line: Last line to read. At most 200 lines are returned per call.

        Returns:
            Numbered lines, or an error message.
        """
        try:
            full = self._resolve(path)
        except ValueError as e:
            return f"Error: {e}"
        if not full.is_file():
            return f"Error: file {path} does not exist"

        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(start_line, 1)
        end = min(end_line or len(lines), start + self.max_lines - 1, len(lines))

        numbered = [f"{i}: {lines[i - 1]}" for i in range(start, end + 1)]
        if end < len(lines):
            numbered.append(f"... file has {len(lines)} lines, read more with start_line={end + 1}")
        return "\n".join(numbered)

    def search_docs(self, query: str) -> list[dict]:
        """
        Search the repo's documentation (READMEs and EventCatalog pages for events
        and services, with their producers and consumers). Use it to see what the
        docs claim, then verify those claims in the code - docs can be outdated.

        Args:
            query: Natural language search query.

        Returns:
            Matching doc chunks with filename, start_line, producers, consumers and content.
        """
        results = self.docs_index.search(
            query,
            boost_dict={"title": 2.0, "producers": 1.5, "consumers": 1.5},
            num_results=5,
        )
        return [
            {k: r[k] for k in ["filename", "start_line", "title", "producers", "consumers", "content"]}
            for r in results
        ]



def create_codebase_tools(repo_dir: Path = DEFAULT_REPO_DIR) -> CodebaseTools:
    if not repo_dir.is_dir():
        raise FileNotFoundError(f"{repo_dir} not found, run `make targets` first")
    docs_index = build_docs_index(load_docs(repo_dir))
    return CodebaseTools(repo_dir, docs_index)
