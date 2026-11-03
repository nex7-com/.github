"""Aplica actionlint e zizmor somente aos workflows do chamador, sem descoberta em dependências."""
import subprocess
from pathlib import Path


def main():
    arquivos = sorted(str(p) for p in Path(".github/workflows").glob("*") if p.suffix in {".yml", ".yaml"})
    if arquivos:
        subprocess.run(["actionlint", *arquivos], check=True)
        subprocess.run(["zizmor", "--offline", "--no-progress", "--format", "plain", *arquivos], check=True)
    else:
        print("Sem workflows no repositório chamador.")


if __name__ == "__main__":
    main()
