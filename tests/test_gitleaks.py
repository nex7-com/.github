"""Política central de segredos: cada exceção cobre só um formato que nunca é segredo.

Os valores são gerados na hora (semente fixa) para que este arquivo não carregue nada com cara de segredo.
"""
import base64
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
# Literais montados em partes: o código-fonte deste teste não pode ter a forma que a regra padrão acusa.
IDENTIFICADOR = "fixture" + "_identifier"
ATALHO = "Shift+" + "Escape"
SENHA_FIXA = "senha-forte-" + "123"


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


def formatos_lote7(sorteio):
    hexa = string.digits + "abcdef"
    sufixo = aleatorio(sorteio, string.ascii_lowercase, 24)
    fixture = base64.b64encode(("fixture:" + sufixo).encode()).decode()
    return {
        "instalacoes/cutter/docs/instalacao.md": f'API GitHub e conferido: `{aleatorio(sorteio, hexa, 64)}`\n',
        "instalacoes/rizin/docs/release.md": f'api_secret = "{aleatorio(sorteio, hexa, 64)}"\n',
        "projetos/x/tests/synthetic.test.mjs": f'const api_key = "synthetic-{sufixo}";\n',
        "projetos/x/tests/wechat.test.mjs": f'const api_key = "wx-synthetic-{sufixo}";\n',
        "projetos/x/tests/automation.test.mjs": f'const key = "{base64.b64encode(bytes([7] * 32)).decode()}";\n',
        "tests/Feature/OrigemCadastroTest.php": f'$password = "senha-forte-{sorteio.randrange(100, 1000)}";\n',
        "publicacao_obsidian/smoke_regressoes.py": f'caso = ("password", "api_key={IDENTIFICADOR}")\n',
        "projetos/x/publicacao_obsidian/smoke_regressoes.py": f'password = "{fixture}"\n',
        "docs/RELATORIO.md": f'Atributo ARIA `aria-keyshortcuts="{ATALHO}"`.\n',
    }


def controles_lote7(sorteio):
    misto = string.ascii_letters + string.digits
    hexa = string.digits + "abcdef"
    senha = aleatorio(sorteio, misto, 28)
    basic = base64.b64encode(("service:" + senha).encode()).decode()
    return {
        "instalacoes/cutter/docs/instalacao.md": f'api_secret = "{aleatorio(sorteio, misto, 40)}"\n',
        "docs/instalacao.md": f'api_secret = "{aleatorio(sorteio, hexa, 64)}"\n',
        "tests/synthetic.test.mjs": f'const api_key = "live-{aleatorio(sorteio, misto, 32)}";\n',
        "tests/wechat.test.mjs": f'const api_key = "wx-live-{aleatorio(sorteio, misto, 32)}";\n',
        "tests/automation.test.mjs": f'const key = "{base64.b64encode(bytes(sorteio.randrange(256) for _ in range(32))).decode()}";\n',
        "tests/Feature/OrigemCadastroTest.php": f'$password = "senha-forte-{aleatorio(sorteio, misto, 20)}";\n',
        "publicacao_obsidian/smoke_regressoes.py": f'caso = ("password", "api_key={aleatorio(sorteio, misto, 32)}")\n',
        "projetos/x/publicacao_obsidian/smoke_regressoes.py": f'password = "{basic}"\n',
        "docs/RELATORIO.md": f'aria-keyshortcuts="{aleatorio(sorteio, misto, 32)}"\n',
        "config/OrigemCadastro.php": f'$password = "{SENHA_FIXA}";\n',
        "config/smoke.py": f'caso = ("password", "api_key={IDENTIFICADOR}")\n',
        "config/aria.js": f'aria-keyshortcuts="{ATALHO}"\n',
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
                                   check=False, capture_output=True, text=True)
        self.assertIn(resultado.returncode, (0, 7), resultado.stderr)
        return {str(Path(achado["File"]).relative_to(arvore)) for achado in json.loads(relatorio.read_text())}

    def test_formatos_da_casa_passam_e_cada_excecao_e_necessaria(self):
        formatos = formatos_da_casa(random.Random(20261103))
        self.assertEqual(self.acusados(formatos, self.padrao, "sem-excecoes"), set(formatos))
        self.assertEqual(self.acusados(formatos, POLITICA, "central"), set())

    def test_segredos_continuam_recusados_mesmo_nos_lugares_com_excecao(self):
        valores = segredos(random.Random(20261103))
        self.assertEqual(self.acusados(valores, POLITICA, "central"), set(valores))

    def test_formatos_lote7_passam_e_excecoes_detectaveis_sao_necessarias(self):
        formatos = formatos_lote7(random.Random(20261103))
        # Marcadores explícitos e bytes repetidos já ficam abaixo da heurística/entropia padrão.
        ja_inofensivos = {f"projetos/x/tests/{nome}.test.mjs" for nome in ("synthetic", "wechat", "automation")}
        self.assertEqual(self.acusados(formatos, self.padrao, "lote7-padrao"), set(formatos) - ja_inofensivos)
        self.assertEqual(self.acusados(formatos, POLITICA, "lote7-central"), set())

    def test_controles_parecidos_lote7_continuam_acusados(self):
        controles = controles_lote7(random.Random(20261103))
        self.assertEqual(self.acusados(controles, POLITICA, "lote7-controles"), set(controles))

    def test_vetor_publico_wecom_so_valor_exato_e_so_no_teste(self):
        # Fixture publicada no documento oficial 90968; reconstruída sem literal de credencial.
        vetor = bytes.fromhex(
            "6a576d596d377172356e4d6f4155775a526a477442786d7a334b4131746b416a33796b6b52367132423243"
        ).decode()
        caminho = "projetos/wecom/tests/automation.test.mjs"
        arquivos = {caminho: f'const key = "{vetor}";\n'}
        self.assertEqual(self.acusados(arquivos, self.padrao, "wecom-padrao"), {caminho})
        self.assertEqual(self.acusados(arquivos, POLITICA, "wecom-central"), set())
        controles = {
            caminho: f'const key = "{vetor[:-1]}D";\n',
            "config/automation.mjs": arquivos[caminho],
        }
        self.assertEqual(self.acusados(controles, POLITICA, "wecom-controles"), set(controles))


if __name__ == "__main__":
    unittest.main()
