"""Política central de segredos: cada exceção cobre só um formato que nunca é segredo.

Os valores são gerados na hora (semente fixa) para que este arquivo não carregue nada com cara de segredo.
"""
import json
import random
import shutil
import string
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

POLITICA = Path(__file__).resolve().parents[1] / "ferramentas/gitleaks.toml"
GITLEAKS = shutil.which("gitleaks")


def aleatorio(sorteio, alfabeto, tamanho):
    return "".join(sorteio.choice(alfabeto) for _ in range(tamanho))


def formatos_da_casa(sorteio):
    """Falsos positivos reais das casas (03/11/2026): a regra padrão acusa, a política central aceita."""
    hexa = string.digits + "abcdef"
    return {
        "agente/agent.md": 'kit_sugerido: ["desenvolvimento/oficinas/python", "desenvolvimento/oficinas/fastapi", '
                           '"desenvolvimento/oficinas/vitest"]\n',
        "agente/docs/agente.md": "Repositório oficial, API key/OAuth,\nup/down/set/serve/funnel/cert são decisões do dono\n",
        "estudos/e1/manifesto.json": json.dumps({"source_key": str(uuid.UUID(int=sorteio.getrandbits(128), version=4)),
                                                 "nome": "recurso"}, indent=2) + "\n",
        "docs/pesquisa/familias/sdk.json": json.dumps({"spotify-web-api-ts-sdk": aleatorio(sorteio, hexa, 40)}, indent=2),
        "docs/pesquisa/licenca/leitura.json": json.dumps({"sha256_openapi": aleatorio(sorteio, hexa, 64)}, indent=2),
        "instalacoes/r-x/lock/variante.json": json.dumps({"get_email_token1": aleatorio(sorteio, hexa, 64)}, indent=2),
        "docs/metodo.md": "curl -H 'Authorization: Bearer SYNTHETIC-ONLY' http://127.0.0.1:20650/api/v1/servers\n",
        "docs/runtime.md": "`ENABLE=true`, `SECONDARY_LLM_KEY=ANTHROPIC_CLAUDE4.5_SONNET` (ou outro modelo)\n",
        "estudos/e1/quadlets/SHA256SUMS.json": json.dumps({"nxt-casa-api.container": aleatorio(sorteio, hexa, 64)},
                                                          indent=2),
        "ferramentas/cli/x/consultar.py": 'NOMES = {\n    "check_login", "get_email_token1", "tjsp2_autenticar", "check_login2",\n}\n',
    }


def segredos(sorteio):
    """Valores com cara de segredo, inclusive dentro dos lugares e formatos que têm exceção."""
    hexa = string.digits + "abcdef"
    misto = string.ascii_letters + string.digits
    minusculo = string.ascii_lowercase + string.digits
    chave_produto = "-".join(aleatorio(sorteio, string.ascii_uppercase + string.digits, 5) for _ in range(5))
    return {
        "config/app.json": json.dumps({"api_secret": aleatorio(sorteio, hexa, 64)}, indent=2),
        "docs/pesquisa/familias/x.json": json.dumps({"api_token": aleatorio(sorteio, misto, 32)}, indent=2),
        "instalacoes/r-x/lock/outro.json": json.dumps({"api_secret": aleatorio(sorteio, misto, 40)}, indent=2),
        "agente/segredo.md": f'api_key: "{aleatorio(sorteio, minusculo, 28)}"\n',
        "docs/licenca.md": f'license_key = "{chave_produto}"\n',
        "ferramentas/cli/y/cfg.py": f'PAR = ("api_key", "{aleatorio(sorteio, minusculo, 24)}")\n',
    }


@unittest.skipUnless(GITLEAKS, "gitleaks ausente (o CI instala a versão fixada antes dos testes)")
class TestPoliticaCentral(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.padrao = self.raiz / "padrao.toml"
        self.padrao.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")

    def acusados(self, arquivos, politica, nome):
        arvore = self.raiz / nome
        for rel, conteudo in arquivos.items():
            (arvore / rel).parent.mkdir(parents=True, exist_ok=True)
            (arvore / rel).write_text(conteudo, encoding="utf-8")
        relatorio = self.raiz / (nome + ".json")
        resultado = subprocess.run([GITLEAKS, "dir", str(arvore), "--config", str(politica), "--no-banner", "--redact",
                                    "--exit-code", "7", "--report-format", "json", "--report-path", str(relatorio)],
                                   capture_output=True, text=True)
        self.assertIn(resultado.returncode, (0, 7), resultado.stderr)
        return {str(Path(achado["File"]).relative_to(arvore)) for achado in json.loads(relatorio.read_text())}

    def test_formatos_da_casa_passam_e_cada_excecao_e_necessaria(self):
        formatos = formatos_da_casa(random.Random(20261103))
        self.assertEqual(self.acusados(formatos, self.padrao, "sem-excecoes"), set(formatos))
        self.assertEqual(self.acusados(formatos, POLITICA, "central"), set())

    def test_segredos_continuam_recusados_mesmo_nos_lugares_com_excecao(self):
        valores = segredos(random.Random(20261103))
        self.assertEqual(self.acusados(valores, POLITICA, "central"), set(valores))


if __name__ == "__main__":
    unittest.main()
