"""Confere forma e propostas da autoria sem banco, credencial ou repositório privado adicional."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

COLECOES = {"oficinas": "oficina", "bancadas": "bancada", "estudios": "estudio", "escritorios": "escritorio",
            "agencias": "agencia", "bibliotecas": "biblioteca", "empresas": "empresa", "pessoas": "pessoa"}


def canonico(objeto):
    # Mesmos bytes do armazém de autoria do núcleo (`bff/armazem.py`): ordem das chaves preservada.
    return (json.dumps(objeto, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def sem_duplicatas(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError("chave JSON duplicada")
        resultado[chave] = valor
    return resultado


def ler(path):
    raw = path.read_bytes()
    objeto = json.loads(raw, object_pairs_hook=sem_duplicatas)
    if raw != canonico(objeto):
        raise ValueError("JSON não canônico")
    return objeto


def relativo(valor):
    if not isinstance(valor, str) or not valor or "\\" in valor:
        raise ValueError("caminho inválido no índice")
    if any(ord(char) < 32 or ord(char) == 127 for char in valor):
        raise ValueError("caractere de controle no caminho")
    path = PurePosixPath(valor)
    if path.is_absolute() or any(p in {".", "..", ""} for p in valor.split("/")):
        raise ValueError("caminho fora do espelho")
    return valor


class BaseDePropostaInvalida(ValueError):
    """Erro estático, seguro para o log do CI."""


def conferir_base(repo, ref):
    arvore = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--end-of-options", f"{ref}^{{tree}}"],
        check=True, capture_output=True,
    ).stdout.decode("ascii").strip()
    for caminho in ("modulo.json", "definicoes/indice.json"):
        anterior = subprocess.run(
            ["git", "-C", str(repo), "show", f"{arvore}:.plataforma/{caminho}"],
            check=True, capture_output=True,
        ).stdout
        if anterior != (repo / ".plataforma" / caminho).read_bytes():
            raise BaseDePropostaInvalida("proposta deve manter o índice-base")


def conferir(repo, ref_base=None):
    base = repo / ".plataforma"
    if base.is_symlink() or (base / "definicoes").is_symlink():
        raise ValueError("symlink na raiz do espelho")
    for path in base.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink no espelho")
    modulo = ler(base / "modulo.json")
    if modulo.get("schema") != "nxt.plataforma.modulo.v1":
        raise ValueError("schema de módulo inválido")
    casa = relativo(modulo["id"])
    partes = casa.split("/")
    if len(partes) == 3 and partes[0] == "desenvolvimento" and partes[1] not in {"empresas", "pessoas"}:
        colecao = partes[1]
    elif len(partes) == 2 and partes[0] in {"empresas", "pessoas"}:
        colecao = partes[0]
    else:
        raise ValueError("id não é casa")
    # `colecao` é o nome da coleção (plural, como no caminho); o repositório usa o singular.
    if colecao not in COLECOES or modulo.get("colecao") != colecao:
        raise ValueError("coleção não corresponde à casa")
    uuid.UUID(modulo["uid"])
    if modulo.get("repositorio") != f"nex7-com/{COLECOES[colecao]}-{partes[-1]}":
        raise ValueError("repositório não corresponde à casa")
    if not isinstance(modulo.get("dependencias"), list) or not isinstance(modulo.get("plugins"), list):
        raise TypeError("dependências/plugins inválidos")
    if set(modulo.get("compativel_com", {})) != {"nucleo", "design-system"}:
        raise ValueError("compatibilidade ausente")
    indice = ler(base / "definicoes/indice.json")
    if indice.get("schema") != "nxt.plataforma.definicoes.v1" or not isinstance(indice.get("documentos"), list):
        raise ValueError("índice de definições inválido")
    esperados = {}
    for item in indice["documentos"]:
        caminho = relativo(item["caminho"])
        if caminho == "indice.json" or caminho in esperados:
            raise ValueError("caminho reservado ou duplicado")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError("SHA-256 inválido")
        if not isinstance(item.get("tipo"), str) or not item["tipo"]:
            raise TypeError("tipo de definição ausente")
        esperados[caminho] = item
    documentos, hashes = {}, {}
    for arquivo in (base / "definicoes").rglob("*"):
        if not arquivo.is_file():
            continue
        caminho = relativo(arquivo.relative_to(base / "definicoes").as_posix())
        if caminho == "indice.json":
            continue
        documento = ler(arquivo)
        digest = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        item = esperados.get(caminho)
        # A revisão da proposta pode mudar; só o espelho sem alteração deve corresponder ao índice.
        if item and digest == item["sha256"] and documento.get("revisao") != item.get("revisao"):
            raise ValueError("revisão diverge do índice")
        documentos[caminho], hashes[caminho] = documento, digest
    registro = documentos.get("_registro.json", {})
    if registro.get("id") != casa or registro.get("uid") != modulo["uid"]:
        raise ValueError("registro raiz ausente ou divergente do módulo")
    propostas = {
        "alteradas": sorted(p for p in documentos.keys() & esperados.keys() if hashes[p] != esperados[p]["sha256"]),
        "novas": sorted(documentos.keys() - esperados.keys()),
        "removidas": sorted(esperados.keys() - documentos.keys()),
    }
    if ref_base is not None and any(propostas.values()):
        conferir_base(repo, ref_base)
    return {"ok": True, "documentos": len(documentos), "offline": True, "propostas": propostas}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--base", help="ref Git da base do PR; propostas preservam módulo e índice-base")
    args = parser.parse_args()
    try:
        print(json.dumps(conferir(args.repo, args.base)))
        return 0
    except BaseDePropostaInvalida:
        print("Espelho inválido: proposta deve manter o índice-base.", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError):
        # Não ecoa conteúdo de definições privadas no log público de ferramentas.
        print("Espelho inválido: confira módulo, índice, JSON canônico, definições e ref da base.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
