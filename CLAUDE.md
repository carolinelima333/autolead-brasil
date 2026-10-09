# AutoLead Brasil — instruções para o Claude

## Varredura de segurança e qualidade (obrigatória)
Sempre que houver alteração no código, antes de commitar/subir:

1. Rode `python scripts/security_check.py` (também roda sozinho no pre-commit via `.githooks/`).
2. Revise o diff como um Sonar, além do que o script cobre:
   - **XSS**: todo dado externo (Google, bases de CNPJ, campos digitados) que vai para `innerHTML` passa por `escH()`; argumentos em `onclick="fn('...')"` usam `escJs()`; links externos usam `linkBtn()`/`safeUrl()`.
   - **Backend**: rota nova em `api/index.py` chama `_require_user()` (ou `_require_admin()`), e também é registrada no `api_dispatch` (Vercel); nada de `str(exc)` em resposta; validar e limitar parâmetros.
   - **Custo**: a usuária não quer gastar com a Google API — não aumentar chamadas pagas (Text Search / Place Details) sem perguntar.
   - **Segredos**: chaves só no `.env` e nas variáveis da Vercel; nunca em código, docs ou commits.
   - **Banco**: tabela nova com RLS; mudanças no Supabase de produção só com confirmação.
   - **Qualidade**: código morto, duplicação, tratamento de erro, mensagens claras para o usuário.
3. Informe à usuária o resultado da varredura (o que foi encontrado e corrigido) junto com o resumo da alteração.
