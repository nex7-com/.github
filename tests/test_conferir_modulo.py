import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("conferir_modulo", Path(__file__).resolve().parents[1] / "ferramentas/conferir_modulo.py")
verificador = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verificador)


class TestEspelho(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.base = self.repo / ".plataforma"
        (self.base / "definicoes").mkdir(parents=True)
        self.registro = {"id": "desenvolvimento/oficinas/teste", "uid": "00000000-0000-4000-8000-000000000001", "revisao": 1}
        self.modulo = {"schema": "nxt.plataforma.modulo.v1", "id": self.registro["id"], "uid": self.registro["uid"],
                       "colecao": "oficinas", "repositorio": "nex7-com/oficina-teste", "dependencias": [], "plugins": [],
                       "compativel_com": {"nucleo": ">=0", "design-system": ">=0"}}
        self.indice = {"schema": "nxt.plataforma.definicoes.v1", "documentos": [{"caminho": "_registro.json", "tipo": "registro",
                       "revisao": 1, "sha256": hashlib.sha256(verificador.canonico(self.registro)).hexdigest()}]}
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/_registro.json", self.registro)
        self.gravar("definicoes/indice.json", self.indice)

    def gravar(self, caminho, objeto):
        (self.base / caminho).write_bytes(verificador.canonico(objeto))

    def test_valido(self):
        self.assertEqual(verificador.conferir(self.repo), {"ok": True, "documentos": 1, "offline": True})

    def test_titular_valido(self):
        self.registro["id"] = "pessoas/teste"
        self.modulo.update(id="pessoas/teste", colecao="pessoas", repositorio="nex7-com/pessoa-teste")
        self.indice["documentos"][0]["sha256"] = hashlib.sha256(verificador.canonico(self.registro)).hexdigest()
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/_registro.json", self.registro)
        self.gravar("definicoes/indice.json", self.indice)
        self.assertTrue(verificador.conferir(self.repo)["ok"])

    def test_colecao_no_singular_recusada(self):
        self.modulo["colecao"] = "oficina"
        self.gravar("modulo.json", self.modulo)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_ordem_de_chaves_do_armazem(self):
        # O núcleo grava como o armazém: indent 2, UTF-8, ordem de inserção (não ordenada).
        modulo = {"schema": self.modulo["schema"], "uid": self.modulo["uid"], "id": self.modulo["id"],
                  "colecao": "oficinas", "nome": "Teste ç", "repositorio": "nex7-com/oficina-teste",
                  "versao": "0.0.0", "compativel_com": {"nucleo": ">=0", "design-system": ">=0"},
                  "dependencias": [], "plugins": [], "aninhados": []}
        (self.base / "modulo.json").write_text(json.dumps(modulo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.assertTrue(verificador.conferir(self.repo)["ok"])

    def test_adulteracao(self):
        self.registro["revisao"] = 2
        self.gravar("definicoes/_registro.json", self.registro)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_arquivo_extra(self):
        self.gravar("definicoes/extra.json", {})
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_arquivo_ausente(self):
        (self.base / "definicoes/_registro.json").unlink()
        with self.assertRaises(OSError):
            verificador.conferir(self.repo)

    def test_traversal_absoluto_e_duplicado(self):
        for caminho in ["../fora.json", "/etc/passwd", "a/../b", "a//b", "a\\b", "./x"]:
            with self.subTest(caminho=caminho), self.assertRaises(ValueError):
                verificador.relativo(caminho)
        indice = copy.deepcopy(self.indice)
        indice["documentos"] *= 2
        self.gravar("definicoes/indice.json", indice)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_symlink(self):
        (self.base / "definicoes/link.json").symlink_to(self.base / "modulo.json")
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_canonico_e_chave_duplicada(self):
        (self.base / "modulo.json").write_text(json.dumps(self.modulo))
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)
        (self.base / "modulo.json").write_text('{"schema":1,"schema":2}')
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_modulo_divergente(self):
        self.modulo["uid"] = "00000000-0000-4000-8000-000000000002"
        self.gravar("modulo.json", self.modulo)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_revisao_indice_divergente(self):
        self.indice["documentos"][0]["revisao"] = 2
        self.gravar("definicoes/indice.json", self.indice)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)


if __name__ == "__main__":
    unittest.main()
