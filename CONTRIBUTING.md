# Como contribuir

Vale para todos os repositórios da organização que não tenham o próprio `CONTRIBUTING.md`, para pessoas e para
agentes de IA.

1. Antes de mudar qualquer coisa, leia o `AGENTS.md` do repositório: ele diz como compilar, testar e o que nunca
   fazer.
2. Trabalhe numa branch curta a partir da `main` atualizada: `feat/<tema>`, `fix/<tema>` ou `docs/<tema>`.
3. Escreva os commits no formato `tipo(escopo): resumo`, com `tipo` entre `feat`, `fix`, `docs`, `refactor`, `test`
   e `chore`.
4. Rode os testes e as verificações do repositório antes de abrir o PR.
5. Abra o PR para `main` preenchendo o modelo. O merge é por squash, depois da revisão que o repositório exige.

Nunca entram no repositório: segredos (tokens, senhas, chaves), dados pessoais, arquivos de estado e arquivos grandes.
O GitHub recusa parte disso no push; o resto é barrado na revisão.

Tarefa nova entra pelo formulário **Tarefa para agente** das issues, em que objetivo, critério de aceite e forma de
testar são obrigatórios.
