from __future__ import annotations

from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "static",
}

TEXT_EXTS = {
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".env",
    ".js",
    ".ts",
    ".vue",
    ".css",
    ".html",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
    ".make",
}


def is_text_file(path: Path) -> bool:
    if path.name in {"Makefile", "Dockerfile", "AGENTS.md"}:
        return True
    return path.suffix.lower() in TEXT_EXTS


def main() -> int:
    root = Path.cwd()
    violations: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & SKIP_DIRS:
            continue
        if not is_text_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            violations.append(f"{path}: non-utf8")
            continue
        for idx, ch in enumerate(text):
            if ord(ch) > 127:
                line = text.count("\n", 0, idx) + 1
                col = idx - text.rfind("\n", 0, idx)
                violations.append(f"{path}:{line}:{col}: non-ascii U+{ord(ch):04X}")
                break
    if violations:
        print("Non-ASCII check failed:")
        for item in violations:
            print(item)
        return 1
    print("Non-ASCII check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
