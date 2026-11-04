# Imagem oficial do Python baseada em Debian (slim)
FROM python:3.12-slim

WORKDIR /app

# Não gera arquivos .pyc e mostra os logs do Python na hora
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# LaTeX para gerar os PDFs (pdflatex + pacotes usados em arquivosTEX/)
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-lang-portuguese \
    texlive-fonts-recommended \
    lmodern \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python, instaladas a partir do Pipfile.lock (versões fixas).
# Fica antes do COPY do código para o Docker reaproveitar esta camada quando só o código muda.
RUN pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock /app/
RUN pipenv install --system --deploy && pip uninstall -y pipenv

# Código do projeto
COPY . /app/

# Junta os arquivos estáticos em /app/static (servidos pelo WhiteNoise).
# SECRET_KEY e DATABASE_URL aqui são só para o comando rodar no build (ele não acessa o banco);
# as de verdade vêm do .env do servidor.
RUN SECRET_KEY=build-only DATABASE_URL=postgresql://build:build@localhost/build \
    python manage.py collectstatic --noinput

# Roda como usuário comum, não como root
RUN useradd --create-home app \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app/plataformaResumosAPP
USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

# Configuração do gunicorn por variáveis que ele mesmo lê:
#  - WEB_CONCURRENCY: número de processos (pode ser trocado no .env)
#  - timeout alto porque a geração do PDF da revista pode demorar
ENV WEB_CONCURRENCY=3 \
    GUNICORN_CMD_ARGS="--bind 0.0.0.0:8000 --timeout 300 --access-logfile -"

# Formato JSON: o gunicorn recebe direto os sinais de parada do Docker e desliga sem cortar requisições
CMD ["gunicorn", "plataformaResumosAPI.wsgi:application"]
