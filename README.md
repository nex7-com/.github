# Contratos compartilhados da NEX7

Este repositório é público: contém somente ferramentas e instruções genéricas. Nunca contém definições reais,
nomes de titulares, conteúdo de repositórios privados ou credenciais.

## CI de módulo

`.github/workflows/modulo.yml` é um workflow reutilizável com `workflow_call`, sem inputs obrigatórios.
A casa recebe o modelo em `modelos/ci.yml`, fixado por SHA completo, e `.github/CODEOWNERS` com
`* @nex7-com/donos`. O workflow opera com `permissions: contents: read`, sem secrets herdados,
sem consultar a estação nem outro repositório privado. Não use `pull_request_target` no chamador.

O checkout do chamador não persiste credenciais e inclui o histórico para o gitleaks. As ferramentas públicas
são obtidas de um commit imutável deste repositório, separado do checkout do chamador. Gitleaks 8.30.1 e
actionlint 1.7.12 têm SHA-256 de release conferido; zizmor 1.31.1 instala num venv efêmero do runner.
O gitleaks usa configuração padrão versionada aqui, não uma configuração fornecida pelo PR do chamador.
Actionlint e zizmor analisam os workflows do chamador quando presentes, sem rede na análise do zizmor.

O verificador `ferramentas/conferir_modulo.py` é Python 3, só biblioteca padrão. Confere:

- `.plataforma/modulo.json` (`nxt.plataforma.modulo.v1`): casa, coleção, UID, repositório e compatibilidade;
- `.plataforma/definicoes/indice.json` (`nxt.plataforma.definicoes.v1`): cobertura exata, unicidade, revisão e SHA-256 dos bytes;
- registro raiz com o mesmo UID/id do módulo; JSON canônico (`sort_keys=True`, `indent=2`, UTF-8, newline);
- ausência de symlinks e caminhos absolutos/traversal; recusa de arquivos extras ou ausentes.

Não compara com o banco da estação. A conferência online `plataforma modulos exportar <casa> --conferir` continua
necessária antes da adoção/merge. A conferência offline prova a integridade interna do espelho, não sua atualidade.
Não executa código da casa, testes de linguagem ou migrações.

## Desenvolvimento

```sh
python3 -m unittest discover -s tests -v
python3 ferramentas/conferir_modulo.py /caminho/do/clone-da-casa
python3 ferramentas/conferir_workflows.py
```

O terceiro comando exige actionlint e zizmor no PATH. O instalador de CI exige `RUNNER_TEMP` e `GITHUB_PATH`:
é para runners Linux x86_64, não para instalar ferramentas globalmente na estação.
