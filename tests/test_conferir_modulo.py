import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
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
        self.assertEqual(verificador.conferir(self.repo), {
            "ok": True, "documentos": 1, "offline": True,
            "propostas": {"alteradas": [], "novas": [], "removidas": []},
        })

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

    def test_alteracao_proposta(self):
        self.registro["revisao"] = 2
        self.gravar("definicoes/_registro.json", self.registro)
        self.assertEqual(verificador.conferir(self.repo)["propostas"],
                         {"alteradas": ["_registro.json"], "novas": [], "removidas": []})

    def test_arquivo_novo_proposto(self):
        self.gravar("definicoes/extra.json", {})
        self.assertEqual(verificador.conferir(self.repo)["propostas"],
                         {"alteradas": [], "novas": ["extra.json"], "removidas": []})

    def test_remocao_proposta(self):
        self.indice["documentos"].append({"caminho": "docs/antigo.json", "tipo": "documento",
                                          "revisao": 1, "sha256": "0" * 64})
        self.gravar("definicoes/indice.json", self.indice)
        self.assertEqual(verificador.conferir(self.repo)["propostas"],
                         {"alteradas": [], "novas": [], "removidas": ["docs/antigo.json"]})

    def test_registro_raiz_nao_pode_ser_removido(self):
        (self.base / "definicoes/_registro.json").unlink()
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_traversal_absoluto_e_duplicado(self):
        for caminho in ["../fora.json", "/etc/passwd", "a/../b", "a//b", "a\\b", "./x", "a\0b", "a\nb"]:
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

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def base_git(self):
        # Snapshot real do índice Git, sem criar commit, ref ou identidade de autor.
        self.git("init", "--quiet")
        self.git("add", ".plataforma")
        return self.git("write-tree")

    def test_proposta_com_base_preservada(self):
        ref = self.base_git()
        self.registro["revisao"] = 2
        self.gravar("definicoes/_registro.json", self.registro)
        self.assertEqual(verificador.conferir(self.repo, ref)["propostas"]["alteradas"], ["_registro.json"])

    def test_indice_alterado_com_proposta_recusado(self):
        ref = self.base_git()
        self.gravar("definicoes/extra.json", {})
        self.indice["documentos"][0]["revisao"] = 2
        self.registro["revisao"] = 2
        self.indice["documentos"][0]["sha256"] = hashlib.sha256(verificador.canonico(self.registro)).hexdigest()
        self.gravar("definicoes/_registro.json", self.registro)
        self.gravar("definicoes/indice.json", self.indice)
        with self.assertRaisesRegex(verificador.BaseDePropostaInvalida, "proposta deve manter o índice-base"):
            verificador.conferir(self.repo, ref)

    def test_modulo_alterado_com_proposta_recusado(self):
        ref = self.base_git()
        self.modulo["versao"] = "0.0.1"
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/extra.json", {})
        with self.assertRaises(verificador.BaseDePropostaInvalida):
            verificador.conferir(self.repo, ref)

    def test_reexportacao_aceita_indice_novo_sem_proposta(self):
        ref = self.base_git()
        self.registro["revisao"] = 2
        self.indice["documentos"][0].update(
            revisao=2, sha256=hashlib.sha256(verificador.canonico(self.registro)).hexdigest())
        self.gravar("definicoes/_registro.json", self.registro)
        self.gravar("definicoes/indice.json", self.indice)
        self.assertFalse(any(verificador.conferir(self.repo, ref)["propostas"].values()))

    def test_novo_e_removido_preservam_base(self):
        self.indice["documentos"].append({"caminho": "antigo.json", "tipo": "documento",
                                         "revisao": 1, "sha256": "0" * 64})
        self.gravar("definicoes/indice.json", self.indice)
        ref = self.base_git()
        self.gravar("definicoes/novo.json", {})
        self.assertEqual(verificador.conferir(self.repo, ref)["propostas"],
                         {"alteradas": [], "novas": ["novo.json"], "removidas": ["antigo.json"]})

    def test_json_nao_canonico_e_duplicado_em_propostas(self):
        for conteudo in ('{"nome":"teste"}', '{\n  "nome": 1,\n  "nome": 2\n}\n'):
            with self.subTest(conteudo=conteudo):
                (self.base / "definicoes/novo.json").write_text(conteudo)
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)

    def test_nome_inseguro_em_arquivo_novo(self):
        self.gravar("definicoes/a\\b.json", {})
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SPEC.origin), str(self.repo), *args],
                              check=False, capture_output=True, text=True)

    def test_saida_cli_so_lista_caminhos(self):
        self.registro["conteudo"] = "CONTEUDO_PRIVADO_NAO_ECOAR"
        self.gravar("definicoes/_registro.json", self.registro)
        resultado = self.cli()
        self.assertEqual(resultado.returncode, 0)
        self.assertNotIn(self.registro["conteudo"], resultado.stdout + resultado.stderr)
        self.assertEqual(json.loads(resultado.stdout)["propostas"]["alteradas"], ["_registro.json"])

    def test_erros_cli_nao_ecoam_conteudo_nem_ref(self):
        marcador = "CONTEUDO_PRIVADO_NAO_ECOAR"
        self.gravar("definicoes/novo.json", {"nome": marcador})
        resultado = self.cli("--base", marcador)
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(marcador, resultado.stdout + resultado.stderr)
        (self.base / "definicoes/novo.json").write_text(marcador)
        resultado = self.cli()
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn(marcador, resultado.stdout + resultado.stderr)

    def test_cli_mensagem_base_alterada(self):
        ref = self.base_git()
        self.modulo["versao"] = "0.0.1"
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/novo.json", {})
        resultado = self.cli("--base", ref)
        self.assertEqual(resultado.returncode, 1)
        self.assertIn("proposta deve manter o índice-base", resultado.stderr)


if __name__ == "__main__":
    unittest.main()
