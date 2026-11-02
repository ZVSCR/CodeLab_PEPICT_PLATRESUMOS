import subprocess
import os
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _open_template(template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def _salva_arquivo(output_path, conteudo):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(conteudo)


def to_tex(dados, output_dir):
    """
    Gera o arquivo .tex preenchido com os dados fornecidos.
    Retorna o caminho do arquivo .tex gerado.
    """
    document_type = dados.get('document_type')

    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.tex")

    if document_type == 'resumo':
        template_path = os.path.join(BASE_DIR, 'arquivosTEX', 'resumo.tex')

        
        doc_gerado = _open_template(template_path)
        doc_gerado = doc_gerado.replace('_TITULO_RESUMO_',  dados.get('titulo_resumo', ''))
        doc_gerado = doc_gerado.replace('_AUTORES_',        dados.get('autores', ''))
        doc_gerado = doc_gerado.replace('_DISCIPLINA_',     dados.get('disciplina', ''))
        doc_gerado = doc_gerado.replace('_PROGRAMA_PEPICT_',dados.get('pepict', ''))
        doc_gerado = doc_gerado.replace('_OBJETIVOS_',      dados.get('objetivos', ''))
        doc_gerado = doc_gerado.replace('_METODOLOGIA_',    dados.get('metodologia', ''))
        doc_gerado = doc_gerado.replace('_RESULTADOS_',     dados.get('resultados', ''))
        doc_gerado = doc_gerado.replace('_ODS_',            dados.get('ods', ''))
        doc_gerado = doc_gerado.replace('_REFLEXAO_',       dados.get('reflexao', ''))
        doc_gerado = doc_gerado.replace('_REFERENCIAS_',    dados.get('referencias', ''))

        _salva_arquivo(output_path, doc_gerado)

    elif document_type == 'revista':

        template_path = os.path.join(BASE_DIR, 'arquivosTEX', 'revista.tex')
        caminho_temp_capitulos = os.path.join(output_dir, 'conteudo_revista.txt')

        # pega conteudo dos capitulos
        with open(caminho_temp_capitulos, "r", encoding="utf-8") as arquivo:
            capitulos = arquivo.read()

        doc_gerado = _open_template(template_path)
        doc_gerado = doc_gerado.replace('NOME_DA_REVISTA',  dados.get('titulo_revista', 'titulo da revista'))
        doc_gerado = doc_gerado.replace('ANO_PUBLICACAO',  str(dados.get('data', 'DATA'))) # Forçado para string caso venha objeto datetime
        doc_gerado = doc_gerado.replace('_CONTEUDO_REVISTA_', capitulos )

        _salva_arquivo(output_path, doc_gerado)
        
    else:
        raise ValueError(f"Tipo de documento desconhecido: {document_type}")

    return output_path


def to_pdf(dados, output_dir):
    """
    Compila o .tex gerado por to_tex e retorna o caminho do PDF.
    """
    tex_path = to_tex(dados, output_dir)
    pdf_path = tex_path.replace('.tex', '.pdf')

    try:
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', output_dir, tex_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            "A geração do PDF excedeu o limite de 60 segundos."
        ) from e
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.decode(errors='replace') if isinstance(e.stdout, bytes) else e.stdout or ''
        stderr = e.stderr.decode(errors='replace') if isinstance(e.stderr, bytes) else e.stderr or ''
        raise RuntimeError(
            f"pdflatex falhou:\nstdout: {stdout}\nstderr: {stderr}"
        ) from e

    if not os.path.exists(pdf_path):
        raise FileNotFoundError("O arquivo PDF não foi gerado. Verifique o .tex e o log.")

    return pdf_path