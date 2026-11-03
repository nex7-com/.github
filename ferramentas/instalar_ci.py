"""Instala ferramentas somente no RUNNER_TEMP, verificando hashes de releases oficiais."""
import hashlib
import io
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ARQUIVOS = {
    "gitleaks": ("https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz",
                 "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"),
    "actionlint": ("https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz",
                   "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"),
}


def main():
    base = Path(os.environ["RUNNER_TEMP"]) / "modulo-ferramentas"
    base.mkdir(exist_ok=True)
    for nome, (url, sha) in ARQUIVOS.items():
        with urllib.request.urlopen(url, timeout=120) as resposta:
            dados = resposta.read()
        if hashlib.sha256(dados).hexdigest() != sha:
            raise ValueError(f"Checksum inválido: {nome}")
        with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as arquivo:
            membro = arquivo.getmember(nome)
            if not membro.isfile():
                raise ValueError("Executável não é arquivo regular")
            origem = arquivo.extractfile(membro)
            if origem is None:
                raise ValueError("Executável ausente no pacote")
            with origem:
                (base / nome).write_bytes(origem.read())
        # Permissão do binário baixado em pasta efêmera do runner, nunca da estação da casa.
        (base / nome).chmod(0o700)
    venv = base / "venv"
    subprocess.run(["python3", "-m", "venv", str(venv)], check=True)
    subprocess.run([str(venv / "bin/pip"), "install", "--disable-pip-version-check", "zizmor==1.31.1"], check=True)
    with Path(os.environ["GITHUB_PATH"]).open("a") as saida:
        saida.write(f"{base}\n{venv / 'bin'}\n")


if __name__ == "__main__":
    main()
