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

    def gravar_espelho(self):
        self.indice["documentos"][0]["sha256"] = hashlib.sha256(verificador.canonico(self.registro)).hexdigest()
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/_registro.json", self.registro)
        self.gravar("definicoes/indice.json", self.indice)

    def produto(self):
        self.registro.update(id="desenvolvimento/oficinas/zebra/produtos/zt231",
                             tipo="entidade", natureza="produto", familia="oficina",
                             repositorio="nex7-com/oficina-zebra-zt231")
        self.modulo.update(id=self.registro["id"], repositorio=self.registro["repositorio"])
        self.gravar_espelho()

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

    def test_produto_registrado_com_repositorio_proprio(self):
        self.produto()
        self.assertEqual(verificador.conferir(self.repo), {
            "ok": True, "documentos": 1, "offline": True,
            "propostas": {"alteradas": [], "novas": [], "removidas": []},
        })

    def test_casa_renomeada_conserva_repositorio(self):
        self.registro.update(id="desenvolvimento/oficinas/canon",
                             repositorio="nex7-com/oficina-canon-eos-rebel-t7")
        self.modulo.update(id=self.registro["id"], repositorio=self.registro["repositorio"])
        self.gravar_espelho()
        self.assertTrue(verificador.conferir(self.repo)["ok"])

    def test_casa_v1_sem_identidade_persistida_conserva_regra_nominal(self):
        self.modulo["repositorio"] = "nex7-com/oficina-outro"
        self.gravar("modulo.json", self.modulo)
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_repositorio_recalculado_pelo_slug_recusado(self):
        self.produto()
        self.modulo["repositorio"] = "nex7-com/oficina-zt231"
        self.gravar("modulo.json", self.modulo)
        with self.assertRaisesRegex(ValueError, "repositório não corresponde ao registro"):
            verificador.conferir(self.repo)

    def test_produto_repositorio_e_uid_divergentes(self):
        self.produto()
        for campo, valor in (("repositorio", "nex7-com/oficina-outra"),
                             ("uid", "00000000-0000-4000-8000-000000000002"),
                             ("id", "desenvolvimento/oficinas/zebra/produtos/outro")):
            with self.subTest(campo=campo):
                self.modulo[campo] = valor
                self.gravar("modulo.json", self.modulo)
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)
                self.modulo[campo] = self.registro[campo]

    def test_produto_sem_repositorio_proprio_recusado(self):
        self.produto()
        del self.registro["repositorio"]
        # Nem o nome legado derivado, nem o repositório herdado autorizam outro módulo.
        for repositorio in ("nex7-com/oficina-zt231", "nex7-com/oficina-zebra"):
            with self.subTest(repositorio=repositorio):
                self.modulo["repositorio"] = repositorio
                self.gravar_espelho()
                with self.assertRaisesRegex(ValueError, "produto sem repositório próprio"):
                    verificador.conferir(self.repo)

    def test_posicao_de_produto_exige_registro_de_produto(self):
        self.produto()
        for campo, valor in (("tipo", "casa"), ("natureza", "entidade"), ("natureza", None)):
            with self.subTest(campo=campo, valor=valor):
                anterior = self.registro[campo]
                self.registro[campo] = valor
                self.gravar_espelho()
                with self.assertRaisesRegex(ValueError, "registro raiz não é produto"):
                    verificador.conferir(self.repo)
                self.registro[campo] = anterior

    def test_formas_de_id_nao_autorizadas(self):
        self.produto()
        for ident in ("desenvolvimento/bancadas/zebra/produtos/zt231",
                      "desenvolvimento/oficinas/zebra/produtos",
                      "desenvolvimento/oficinas/zebra/produtos/zt231/extra",
                      "desenvolvimento/oficinas/zebra/outros/zt231",
                      "desenvolvimento/empresas/teste",
                      "empresas/teste/produtos/zt231",
                      "desenvolvimento/oficinas/zebra/produtos/../zt231"):
            with self.subTest(ident=ident):
                self.registro["id"] = self.modulo["id"] = ident
                self.gravar_espelho()
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)

    def test_identidade_persistida_em_cada_colecao_e_titular(self):
        for colecao, singular in verificador.COLECOES.items():
            ident = (f"{colecao}/novo" if colecao in {"empresas", "pessoas"}
                     else f"desenvolvimento/{colecao}/novo")
            with self.subTest(colecao=colecao):
                self.registro.update(id=ident, repositorio=f"nex7-com/{singular}-nome-antigo")
                self.modulo.update(id=ident, colecao=colecao, repositorio=self.registro["repositorio"])
                self.gravar_espelho()
                self.assertTrue(verificador.conferir(self.repo)["ok"])

    def test_repositorio_persistido_invalido_mesmo_igual_no_modulo(self):
        self.produto()
        for repositorio in ("outra-org/oficina-teste", "nex7-com/bancada-teste",
                            "nex7-com/oficina-", "nex7-com/oficina-.teste",
                            "nex7-com/oficina-Teste", "nex7-com/oficina-teste/extra",
                            "nex7-com/oficina-teste\n", "nex7-com/oficina-" + "a" * 92,
                            "", None, 42):
            with self.subTest(repositorio=repositorio):
                self.registro["repositorio"] = self.modulo["repositorio"] = repositorio
                self.gravar_espelho()
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)

    def test_nome_valido_e_limite_do_schema_de_repositorio(self):
        self.produto()
        for repositorio in ("nex7-com/oficina-nome_antigo.v1", "nex7-com/oficina-" + "a" * 91):
            with self.subTest(repositorio=repositorio):
                self.registro["repositorio"] = self.modulo["repositorio"] = repositorio
                self.gravar_espelho()
                self.assertTrue(verificador.conferir(self.repo)["ok"])

    def test_produto_proposta_preserva_base(self):
        self.produto()
        ref = self.base_git()
        self.registro["revisao"] = 2
        self.gravar("definicoes/_registro.json", self.registro)
        self.assertEqual(verificador.conferir(self.repo, ref)["propostas"]["alteradas"], ["_registro.json"])
        self.indice["documentos"][0]["revisao"] = 2
        self.gravar_espelho()
        self.gravar("definicoes/extra.json", {})
        with self.assertRaises(verificador.BaseDePropostaInvalida):
            verificador.conferir(self.repo, ref)

    def test_produto_proposta_nao_troca_modulo(self):
        self.produto()
        ref = self.base_git()
        self.registro["repositorio"] = self.modulo["repositorio"] = "nex7-com/oficina-outra"
        self.gravar("modulo.json", self.modulo)
        self.gravar("definicoes/_registro.json", self.registro)
        with self.assertRaises(verificador.BaseDePropostaInvalida):
            verificador.conferir(self.repo, ref)

    def test_produto_nao_relaxa_symlink(self):
        self.produto()
        (self.base / "definicoes/link.json").symlink_to(self.base / "modulo.json")
        with self.assertRaises(ValueError):
            verificador.conferir(self.repo)

    def test_produto_nao_relaxa_json_canonico_ou_duplicatas(self):
        self.produto()
        for conteudo in (json.dumps(self.registro), '{\n  "id": 1,\n  "id": 2\n}\n'):
            with self.subTest(conteudo=conteudo):
                (self.base / "definicoes/_registro.json").write_text(conteudo)
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)

    def test_produto_nao_relaxa_schema_modulo_ou_indice(self):
        self.produto()
        for caminho, objeto in (("modulo.json", self.modulo), ("definicoes/indice.json", self.indice)):
            with self.subTest(caminho=caminho):
                self.gravar(caminho, {**objeto, "schema": "invalido"})
                with self.assertRaises(ValueError):
                    verificador.conferir(self.repo)
                self.gravar(caminho, objeto)

    def test_erro_de_identidade_cli_nao_ecoa_valores(self):
        self.produto()
        marcador = "CONTEUDO_PRIVADO_NAO_ECOAR"
        for campo in ("repositorio", "uid", "id"):
            with self.subTest(campo=campo):
                anterior = self.registro[campo]
                self.registro[campo] = marcador
                self.gravar_espelho()
                resultado = self.cli()
                self.assertEqual(resultado.returncode, 1)
                self.assertEqual(resultado.stdout, "")
                self.assertEqual(resultado.stderr, "Espelho inválido: confira módulo, índice, JSON canônico, definições e ref da base.\n")
                self.assertNotIn(marcador, resultado.stderr)
                self.registro[campo] = anterior

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
