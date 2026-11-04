# Plataforma-de-resumos-estruturados
Projeto de TCC

## Instalacao das dependencias

O projeto requer Python 3.12. Para instalar as dependencias em um ambiente virtual no Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O arquivo `requirements.txt` fixa as versoes das dependencias Python registradas em `Pipfile.lock`.
Como alternativa, para instalar diretamente pelo Pipenv usando o lockfile:

```powershell
python -m pip install pipenv
pipenv sync
```

Para apenas baixar os pacotes, sem instala-los:

```powershell
python -m pip download -r requirements.txt -d pacotes
```

Dependencias do sistema usadas na geracao de PDFs (como LaTeX e wkhtmltopdf) nao sao instaladas pelo
`requirements.txt`; elas estao configuradas no `Dockerfile`.
Os PDFs sao montados em diretorios temporarios isolados por requisicao, removidos quando o download
termina, e a compilacao do LaTeX tem limite de 60 segundos.
