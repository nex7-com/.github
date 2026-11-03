"""Confere o espelho da autoria sem banco, credencial ou repositório privado adicional."""
import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path, PurePosixPath

COLECOES = {"oficinas": "oficina", "bancadas": "bancada", "estudios": "estudio", "escritorios": "escritorio",
            "agencias": "agencia", "bibliotecas": "biblioteca", "empresas": "empresa", "pessoas": "pessoa"}


def canonico(objeto):
    return (json.dumps(objeto, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


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
    path = PurePosixPath(valor)
    if path.is_absolute() or any(p in {".", "..", ""} for p in valor.split("/")):
        raise ValueError("caminho fora do espelho")
    return valor


def conferir(repo):
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
        colecao = COLECOES.get(partes[1])
    elif len(partes) == 2 and partes[0] in {"empresas", "pessoas"}:
        colecao = COLECOES[partes[0]]
    else:
        raise ValueError("id não é casa")
    if not colecao or modulo.get("colecao") != colecao:
        raise ValueError("coleção não corresponde à casa")
    uuid.UUID(modulo["uid"])
    if modulo.get("repositorio") != f"nex7-com/{colecao}-{partes[-1]}":
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
            raise ValueError("tipo de definição ausente")
        arquivo = base / "definicoes" / caminho
        documento = ler(arquivo)
        if hashlib.sha256(arquivo.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("SHA-256 diverge do índice")
        if documento.get("revisao") != item.get("revisao"):
            raise ValueError("revisão diverge do índice")
        esperados[caminho] = documento
    encontrados = {p.relative_to(base / "definicoes").as_posix() for p in (base / "definicoes").rglob("*") if p.is_file()}
    if encontrados != set(esperados) | {"indice.json"}:
        raise ValueError("índice não cobre exatamente os arquivos de definições")
    registro = esperados.get("_registro.json", {})
    if registro.get("id") != casa or registro.get("uid") != modulo["uid"]:
        raise ValueError("registro raiz e módulo divergem")
    return {"ok": True, "documentos": len(esperados), "offline": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        print(json.dumps(conferir(args.repo)))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Não ecoa conteúdo de definições privadas no log público de ferramentas.
        print("Espelho inválido: confira módulo, índice, JSON canônico e SHA-256 das definições.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
