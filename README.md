# django-docker-starter

[![CI](https://github.com/Rafaelcarvalho320/django-docker-starter/actions/workflows/ci.yml/badge.svg)](https://github.com/Rafaelcarvalho320/django-docker-starter/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2-092E20)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Um ponto de partida Django + DRF + PostgreSQL + Docker com as decisões chatas
já tomadas: `check --deploy` limpo, logs em JSON com id de requisição,
liveness e readiness separados, imagem multi-stage rodando como não-root, CI
que verifica tudo isso a cada push.

> *[English summary below](#english-summary)*

## Por que mais um template

A maioria dos boilerplates entrega estrutura de arquivos. O trabalho de verdade
não é criar as pastas — é descobrir, uma dor de cada vez, que:

- `SECRET_KEY` com valor padrão vaza para produção;
- `manage.py check --deploy` reclama de oito coisas e ninguém roda;
- liveness que consulta o banco faz o orquestrador matar todos os containers
  durante uma instabilidade do banco;
- log em texto livre exige um padrão de parsing por serviço, para sempre;
- sem id de requisição, um erro em produção é uma linha de log órfã;
- `CompressedManifestStaticFilesStorage` quebra os testes de quem não rodou
  `collectstatic`.

Aqui cada um desses já está resolvido, **com o motivo escrito ao lado**.

## Começando

```bash
git clone https://github.com/Rafaelcarvalho320/django-docker-starter.git meu-projeto
cd meu-projeto
cp .env.example .env

docker compose up --build      # banco + app, com hot reload
```

Ou sem Docker — em SQLite, sem configurar nada:

```bash
python -m venv .venv && source .venv/Scripts/activate   # Linux/macOS: .venv/bin/activate
make install
make test
make run
```

`make` sozinho lista os alvos disponíveis.

## O que já vem resolvido

| Área | O que está feito |
| --- | --- |
| **Configuração** | Um único `settings.py` dirigido por variáveis de ambiente. Sem pacote `settings/` com base/dev/prod |
| **Segredos** | O processo **recusa iniciar** sem `DJANGO_SECRET_KEY` quando `DEBUG=false` |
| **Segurança** | `check --deploy` passa com zero avisos, e a CI garante que continue passando |
| **Observabilidade** | Logs JSON em produção, texto legível localmente, id de requisição em toda linha |
| **Saúde** | `/health/live/` e `/health/ready/`, que respondem perguntas diferentes |
| **Imagem** | Multi-stage, usuário não-root, `collectstatic` em build time, healthcheck |
| **Banco** | `DATABASE_URL`, conexões reaproveitadas com health check, fallback para SQLite |
| **API** | DRF fechado por padrão, com filtro, busca, ordenação e paginação ligados |
| **Qualidade** | ruff, mypy strict com django-stubs, pytest, pre-commit |
| **CI** | Lint, tipos, `check --deploy`, migrations em dia, testes em SQLite **e** PostgreSQL, build da imagem e stack de pé |

## As decisões e o porquê

**Um `settings.py`, não um pacote `settings/`.** Separar por ambiente produz
com precisão um arquivo de produção que ninguém roda localmente e, portanto,
ninguém testa. Aqui todo ambiente roda o mesmo código e difere só nas
variáveis — que é o que a regra dos doze fatores realmente diz.

**Sem `SECRET_KEY`, o processo não sobe.** Uma chave padrão que funciona em
produção é uma chave padrão que chega em produção. Com `DEBUG=true` você ganha
uma chave descartável; com `DEBUG=false`, um erro que explica como gerar uma.

**Liveness não toca o banco.** Liveness pergunta "esse processo travou?";
readiness pergunta "mando tráfego para cá agora?". Se a liveness consultasse o
banco, uma instabilidade momentânea reprovaria a sonda de todos os containers,
o orquestrador mataria todos, e uma falha recuperável deixaria de ser
recuperável. Confundir as duas é uma das formas mais comuns de transformar um
problema pequeno em um grande.

**A readiness registra o motivo no log, não na resposta.** Endpoint de sonda
costuma ser acessível; nome de host e string de conexão não vão no corpo.

**O id de requisição não é limpo na saída do middleware.** Isso é deliberado e
contraintuitivo. O Django registra todo 4xx e 5xx a partir de
`BaseHandler.get_response`, que roda **depois** de toda a cadeia de middleware.
Limpar na saída tiraria o id exatamente das linhas que alguém vai procurar:
`Not Found: /x` e `Internal Server Error: /y`. O custo é uma linha de log
emitida entre requisições carregar o id da anterior — janela ociosa, sempre
sobrescrita pela requisição seguinte. Sem id em todo erro é pior.

**O header `X-Request-ID` de entrada é validado.** Ele vem de fora e vai parar
em toda linha de log. Sem limite de tamanho é uma forma de inundar o log; com
caractere de controle é uma forma de forjar entradas.

**`collectstatic` roda no build, não no boot.** O resultado é o mesmo toda vez;
fazer por container só deixaria todo deploy mais lento e criaria o risco de
duas réplicas discordarem sobre os hashes.

**O manifesto de estáticos é uma chave de ambiente.** O
`CompressedManifestStaticFilesStorage` recusa servir qualquer arquivo fora do
manifesto, então só funciona depois do `collectstatic` — que a imagem faz e um
clone recém-baixado não. `DJANGO_STATIC_MANIFEST` controla isso, ligado por
padrão onde `DEBUG` está desligado. A suíte roda com ele desligado; o job de
Docker na CI verifica o caminho de produção abrindo o admin numa imagem real.

**A suíte roda com `DEBUG=false`.** Testar com uma configuração mais permissiva
que a de produção é testar outro sistema.

**mypy tem um módulo de settings só dele.** O plugin do django-stubs importa os
settings para conhecer os modelos, e os settings reais recusam importar sem
`SECRET_KEY`. `config/settings_typecheck.py` fornece um valor descartável e
importa os settings de verdade sem alterá-los — assim `mypy` funciona num clone
limpo e o guard de produção continua intacto.

**O `entrypoint.sh` usa `exec`.** Sem isso o shell fica como PID 1 e o
`SIGTERM` do orquestrador nunca chega ao gunicorn, transformando todo deploy
numa espera até o timeout e uma morte forçada.

**Migrations no boot têm um interruptor.** Serve para um serviço único. Com
várias réplicas subindo juntas, `DJANGO_MIGRATE_ON_START=false` e migração como
passo separado do deploy — senão duas réplicas competem aplicando a mesma.

## Estrutura

```
config/
    settings.py             tudo por variável de ambiente
    settings_typecheck.py   entrada só para análise estática
    logging.py              formatador JSON + filtro de request id
core/
    middleware.py           propagação do id de requisição
    health.py               liveness e readiness
items/                      app de exemplo: model, serializer, viewset, admin
tests/                      56 testes
Dockerfile                  multi-stage, não-root, collectstatic no build
entrypoint.sh               espera o banco, migra, exec
gunicorn.conf.py            workers, timeouts e o porquê de cada número
Makefile                    make para descobrir o resto
```

Apague o app `items` quando o seu domínio existir. Ele está aí para o template
entregar algo que **roda de ponta a ponta** — migration, admin, endpoint
filtrado e testes — não porque alguém precise de um Item.

## Configuração

Tudo em `.env.example`, com comentários. Os que mais importam:

| Variável | Padrão | Observação |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | — | Obrigatória quando `DEBUG=false` |
| `DJANGO_DEBUG` | `false` | Ligar muda segurança, logs e renderers |
| `DATABASE_URL` | SQLite | `postgres://user:pass@host:5432/db` |
| `DJANGO_LOG_FORMAT` | `json` fora de debug | `console` para ler no terminal |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | `false` | Só ligue se algo na frente encerra TLS de verdade |
| `DJANGO_MIGRATE_ON_START` | `true` | Desligue com múltiplas réplicas |
| `SENTRY_DSN` | vazio | Vazio desliga o Sentry por completo |

## English summary

A Django + DRF + PostgreSQL + Docker starting point with the boring decisions
already made and the reasoning written next to each one.

What is actually handled:

- **One settings module driven by environment variables**, not a base/dev/prod
  package — splitting by environment reliably produces a production file nobody
  runs locally and therefore nobody tests.
- **The process refuses to boot without a secret key** when DEBUG is off. A
  default that works in production is a default that reaches production.
- **`manage.py check --deploy` passes with zero warnings**, and CI keeps it that
  way.
- **Liveness and readiness are separate.** Liveness never touches the database;
  if it did, a database blip would fail every container's probe and the
  orchestrator would turn a recoverable outage into an unrecoverable one.
- **JSON logs carrying a request id**, deliberately *not* cleared on the way out
  of the middleware, because Django logs every 4xx and 5xx after the middleware
  chain has already returned — clearing it would strip the id from exactly the
  lines anyone greps for.
- **Multi-stage image, non-root, collectstatic at build time**, entrypoint that
  waits for the database and `exec`s so signals reach the server.
- **56 tests**, run against both SQLite and real PostgreSQL in CI, which also
  builds the image, brings the stack up and checks the logs really are JSON.

Code and docstrings are in English; the sections above are in Portuguese.

## Licença

MIT. Veja [LICENSE](LICENSE).
