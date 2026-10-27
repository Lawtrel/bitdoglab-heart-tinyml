"""Auditoria de conteúdo versionado, sem ler segredos de outros diretórios."""
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".venv", "__pycache__", "build", "dist", "work", "third_party", "runs", "data"}
BANNED_EXTENSIONS = {".exe", ".dll", ".uf2", ".elf", ".pem", ".key", ".pyc"}
PATTERNS = {
    "private_windows_path": re.compile(r"[A-Za-z]:[/\\]Users[/\\]"),
    "private_linux_path": re.compile(r"/home/(?!runner(?:/|$))[A-Za-z0-9_-]+/"),
    "github_token": re.compile(r"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "aws_access_key": re.compile(r"AKIA[A-Z0-9]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

def candidates():
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if result.returncode == 0 and result.stdout:
        return [ROOT / name for name in result.stdout.decode().split("\0") if name]
    return [file for file in ROOT.rglob("*") if file.is_file() and not EXCLUDED.intersection(file.relative_to(ROOT).parts)]

def main():
    findings = []
    files = candidates()
    for file in files:
        relative = file.relative_to(ROOT).as_posix()
        if file.suffix.lower() in BANNED_EXTENSIONS or file.name.startswith(".env") or EXCLUDED.intersection(file.relative_to(ROOT).parts):
            findings.append({"file": relative, "rule": "machine_or_secret_file"})
            continue
        if file.stat().st_size > 5_000_000:
            findings.append({"file": relative, "rule": "unexpected_large_file"})
        try:
            text = file.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append({"file": relative, "rule": name})
    print(json.dumps({"checked_files": len(files), "findings": findings}, indent=2))
    return bool(findings)

if __name__ == "__main__":
    sys.exit(main())
