from pathlib import Path

import frontmatter
from gitsource import chunk_documents
from minsearch import Index

SKIP_DIRS = {"node_modules", ".git", "cdk.out", ".github"}
DOC_EXTENSIONS = {".md", ".mdx"}
CODE_EXTENSIONS = {".ts", ".py", ".js", ".java", ".json", ".yaml", ".yml"}

DEFAULT_REPO_DIR = Path(__file__).resolve().parents[2] / "targets" / "insurance-claims"


def is_skipped(rel_path: Path) -> bool:
    return any(part in SKIP_DIRS for part in rel_path.parts)


def as_text(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value) if value else ""


def load_docs(repo_dir: Path) -> list[dict]:
    documents = []
    for path in sorted(repo_dir.rglob("*")):
        rel = path.relative_to(repo_dir)
        if not path.is_file() or is_skipped(rel) or path.suffix not in DOC_EXTENSIONS:
            continue
        post = frontmatter.load(path)
        documents.append({
            "filename": str(rel),
            "title": as_text(post.metadata.get("name") or post.metadata.get("title") or path.parent.name),
            "summary": as_text(post.metadata.get("summary")),
            "producers": as_text(post.metadata.get("producers")),
            "consumers": as_text(post.metadata.get("consumers")),
            "content": post.content,
        })
    return documents


def build_docs_index(documents: list[dict]) -> Index:
    contents = {d["filename"]: d["content"] for d in documents}
    chunks = chunk_documents(documents, size=2000, step=1000)
    for chunk in chunks:
        chunk["start_line"] = contents[chunk["filename"]][:chunk["start"]].count("\n") + 1

    index = Index(
        text_fields=["title", "summary", "producers", "consumers", "content", "filename"],
        keyword_fields=["filename"],
    )
    index.fit(chunks)
    return index
