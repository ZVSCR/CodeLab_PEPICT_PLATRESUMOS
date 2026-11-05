# Plataforma de resumos estruturados

Plataforma de resumos estruturados do PEPICT (UNIFESP). Os alunos escrevem o resumo do projeto da disciplina, os professores avaliam e o coordenador monta o caderno de resumos em PDF com os aprovados.

Projeto originado de um TCC.

## Rodando localmente

Requisitos: [Docker](https://docs.docker.com/get-docker/) com Docker Compose. O Python, o Postgres e o LaTeX (usado para gerar os PDFs) rodam dentro dos containers, então não é preciso instalar nada disso na máquina.

```bash
cp .env.example .env        # depois edite: DEBUG=True e as credenciais do Postgres local
docker compose up -d --build
```

O app fica em http://localhost:8000. O código do projeto é montado dentro do container: ao salvar um arquivo, o servidor recarrega sozinho.

Comandos úteis:

```bash
docker compose logs -f web                                            # logs do app
docker compose exec web python manage.py test plataformaResumosAPP    # testes
docker compose exec web python manage.py createsuperuser              # qualquer comando do Django
docker compose down                                                   # desliga (os dados do banco continuam no volume)
```

Rode `docker compose up -d --build` de novo quando mudar o `Pipfile` ou o `Dockerfile`.

## Dependências

- **Python:** `Pipfile` e `Pipfile.lock` (Pipenv). Para adicionar um pacote: `pipenv install <pacote>` e reconstrua a imagem.
- **Sistema (LaTeX):** listadas no `Dockerfile`. Se um template em `plataformaResumosAPP/arquivosTEX/` passar a usar um pacote LaTeX novo, adicione-o lá.

## Produção

A produção roda a imagem do `Dockerfile` (etapa `prod`, com gunicorn) pelo `docker-compose.prod.yml`. O banco fica no Neon (PostgreSQL gerenciado).

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

O `.env` do servidor precisa de `DEBUG=False`, uma `SECRET_KEY` própria, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` e a `DATABASE_URL` do Neon. Veja o `.env.example`. O container escuta só em `127.0.0.1:8000`: o acesso externo passa por um proxy com HTTPS (Caddy ou nginx) na frente.

## Geração de PDFs

Os PDFs são montados com `pdflatex` em uma pasta temporária por requisição, apagada quando o download termina ou quando dá erro. A compilação do LaTeX tem limite de 60 segundos por passada.
