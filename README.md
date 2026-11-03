# Contratos compartilhados da NEX7

Este repositório é público: contém somente ferramentas e instruções genéricas. Nunca contém definições reais,
nomes de titulares, conteúdo de repositórios privados ou credenciais.

## CI de módulo

`.github/workflows/modulo.yml` é um workflow reutilizável com `workflow_call`, sem inputs obrigatórios.
A casa recebe o modelo em `modelos/ci.yml`, fixado por SHA completo, e `.github/CODEOWNERS` com
`* @nex7-com/donos`. O workflow opera com `permissions: contents: read`, sem secrets herdados,
sem consultar a estação nem outro repositório privado. Não use `pull_request_target` no chamador.

O checkout do chamador não persiste credenciais e inclui todo o histórico (`fetch-depth: 0`) para o gitleaks
e para consultar a base do PR. As ferramentas públicas são obtidas de um commit imutável deste repositório,
separado do checkout do chamador. Gitleaks 8.30.1 e actionlint 1.7.12 têm SHA-256 de release conferido;
zizmor 1.31.1 instala num venv efêmero do runner.
O gitleaks usa configuração padrão versionada aqui, não uma configuração fornecida pelo PR do chamador.
Actionlint e zizmor analisam os workflows do chamador quando presentes, sem rede na análise do zizmor.

O verificador `ferramentas/conferir_modulo.py` é Python 3, só biblioteca padrão. Confere:

- `.plataforma/modulo.json` (`nxt.plataforma.modulo.v1`): casa, coleção, UID, repositório e compatibilidade;
- `.plataforma/definicoes/indice.json` (`nxt.plataforma.definicoes.v1`): base CAS, caminhos únicos, tipos e SHA-256 válidos;
- registro raiz presente com o mesmo UID/id do módulo; todo arquivo presente deve ser JSON canônico
  (`indent=2`, UTF-8, newline, ordem de inserção das chaves preservada), sem chave duplicada;
- ausência de symlinks e caminhos absolutos/traversal.

Arquivos diferentes do SHA do índice são propostas de alteração; arquivos fora do índice são novos; entradas
sem arquivo são remoções. `_registro.json` não pode ser removido. A saída JSON inclui apenas caminhos nas listas
`propostas.alteradas`, `propostas.novas` e `propostas.removidas`, nunca o conteúdo dos documentos.

Interface: `python3 ferramentas/conferir_modulo.py [repo] [--base REF]`.
Sem `--base`, confere somente a forma e lista as propostas (inclusive no push em `main`).
Em `pull_request`, o workflow passa `--base` com o SHA da base: se houver propostas,
`modulo.json` e `definicoes/indice.json` devem ter exatamente os mesmos bytes da base.
Isso preserva o CAS; a mensagem de recusa é “proposta deve manter o índice-base”.
Sem propostas, um índice novo válido é aceito: é a reexportação depois de aplicar o merge.

Não compara com o banco da estação. Depois do merge, o rito `plataforma modulos aplicar <casa>` verifica o CAS
contra o banco, recusa o lote inteiro em caso de conflito e reexporta. A conferência online
`plataforma modulos exportar <casa> --conferir` é para o espelho já sincronizado, não para invalidar propostas
intencionais do PR. A CI offline não comprova a atualidade do banco nem resolve conflitos.
Não executa código da casa, testes de linguagem ou migrações.

## Desenvolvimento

```sh
python3 -m unittest discover -s tests -v
python3 ferramentas/conferir_modulo.py /caminho/do/clone-da-casa
python3 ferramentas/conferir_workflows.py
```

O terceiro comando exige actionlint e zizmor no PATH. O instalador de CI exige `RUNNER_TEMP` e `GITHUB_PATH`:
é para runners Linux x86_64, não para instalar ferramentas globalmente na estação.

## Política central de segredos

`ferramentas/gitleaks.toml` estende as regras padrão sem aceitar configuração, ignore ou `gitleaks:allow`
do chamador. Exceções por caminho exigem também um formato exato (`condition = "AND"` na regra).
Incluem SHA-256 em documentação Markdown de instalação, marcadores sintéticos em testes, bytes repetidos
de uma fixture determinística, placeholders de senha de teste, fixtures explícitas do smoke de detecção
e a citação do atributo ARIA de atalho. O vetor público de envelope WeCom só é aceito pelo valor exato
publicado no documento oficial 90968, restrito a `tests/automation.test.mjs`; a política registra os digests
da chave e do cifrado para conferir a procedência. Nenhuma exceção libera todos os arquivos de `tests/`
ou de documentação.
Os testes geram os valores e exercitam também controles parecidos que continuam acusados.

Formatos adicionais cobertos pela mesma política: digests OCI de imagens `localhost/` em definições e payload
gerados; identificadores de superfície `comfy-<uuid>` e `estoque-galpao-<id>` nos campos/comparações do laboratório
de janela; digests de documentos `SRC-*` nos validadores de requisitos; a lista exata de três sentinelas
minúsculas do redator Rust. A última exceção não aceita corpo PEM entre os marcadores, nem letras maiúsculas,
nem outro arquivo. Os testes cobrem também esses limites. O fonte dos próprios testes deve passar em
`gitleaks dir . --config ferramentas/gitleaks.toml --redact`: monte fixtures em tempo de execução, não grave
no teste um literal com forma de segredo e não libere todo o diretório de testes.
