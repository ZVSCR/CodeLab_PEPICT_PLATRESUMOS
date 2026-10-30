import subprocess
import os
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


LATEX_ESPECIAIS = {
    '\\': r'\textbackslash{}',
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
}


def escapa_latex(texto):
    """Escapa os caracteres especiais do LaTeX para o texto sair literal no PDF."""
    return ''.join(LATEX_ESPECIAIS.get(c, c) for c in str(texto or ''))


def _open_template(template_path):
    with open(template_path, 'r') as f:
        return f.read()


def _salva_arquivo(output_path, conteudo):
    with open(output_path, 'w') as f:
        f.write(conteudo)


def to_tex(dados):
    """
    Gera o arquivo .tex preenchido com os dados fornecidos.
    Retorna o caminho do arquivo .tex gerado.
    """
    document_type = dados.get('document_type')

    temp_dir = os.path.join(BASE_DIR, 'arquivos_temp')
    os.makedirs(temp_dir, exist_ok=True)

    output_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.tex")

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
        caminho_temp_capitulos = os.path.join(BASE_DIR, 'arquivos_temp', 'conteudo_revista.txt')

        # pega conteudo dos capitulos
        with open(caminho_temp_capitulos, "r", encoding="utf-8") as arquivo:
            capitulos = arquivo.read()

        doc_gerado = _open_template(template_path)
        doc_gerado = doc_gerado.replace('NOME_DA_REVISTA',  dados.get('titulo_revista', 'titulo da revista'))
        doc_gerado = doc_gerado.replace('ANO_PUBLICACAO',  str(dados.get('data', 'DATA'))) # Forçado para string caso venha objeto datetime
        # Expediente: o que ainda não tem dado no sistema sai em branco (com "_" o pdflatex falha)
        doc_gerado = doc_gerado.replace('NOME_COORDENADOR_GERAL_PEPICT', dados.get('coordenador_geral', ''))
        doc_gerado = doc_gerado.replace('NOME_COORDENADOR_EDITORIAL', dados.get('coordenador_editorial', ''))
        doc_gerado = doc_gerado.replace('NOME_COMISSAO', dados.get('comissao', ''))
        doc_gerado = doc_gerado.replace('NOME_REVISAO', dados.get('revisao', ''))
        doc_gerado = doc_gerado.replace('NOME_DIAGRAMACAO', dados.get('diagramacao', ''))
        doc_gerado = doc_gerado.replace('ORGANIZADORES', dados.get('organizadores', ''))
        doc_gerado = doc_gerado.replace('_INTRODUCAO_REVISTA_', dados.get('introducao', ''))
        doc_gerado = doc_gerado.replace('_CONTEUDO_REVISTA_', capitulos )

        _salva_arquivo(output_path, doc_gerado)
        
    else:
        raise ValueError(f"Tipo de documento desconhecido: {document_type}")

    return output_path


def to_pdf(dados):
    """
    Compila o .tex gerado por to_tex e retorna o caminho do PDF.
    """
    tex_path = to_tex(dados)
    output_dir = os.path.dirname(tex_path)
    pdf_path = tex_path.replace('.tex', '.pdf')

    try:
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', output_dir, tex_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"pdflatex falhou:\nstdout: {e.stdout.decode()}\nstderr: {e.stderr.decode()}"
        )

    if not os.path.exists(pdf_path):
        raise FileNotFoundError("O arquivo PDF não foi gerado. Verifique o .tex e o log.")

    # Remove arquivos auxiliares gerados pelo pdflatex
    for ext in ('.aux', '.log', '.out'):
        aux = tex_path.replace('.tex', ext)
        if os.path.exists(aux):
            os.remove(aux)

    return pdf_path