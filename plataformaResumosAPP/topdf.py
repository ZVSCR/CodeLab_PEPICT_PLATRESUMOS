import subprocess
import os
import re
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAX_PASSADAS = 4  # limite de compilações do pdflatex por documento


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
    # Depois de um "\\", "[" e "*" seriam lidos como argumento do comando
    '[': '{[}',
    ']': '{]}',
    '*': '{*}',
    # Aspas retas são atalho do babel [brazil] e sumiriam do texto
    '"': r'\textquotedbl{}',
}


def escapa_latex(texto):
    """Escapa os caracteres especiais do LaTeX para o texto sair literal no PDF."""
    return ''.join(LATEX_ESPECIAIS.get(c, c) for c in str(texto or ''))


def _linhas(texto):
    return [linha.strip() for linha in str(texto or '').splitlines() if linha.strip()]


def escapa_latex_linhas(texto):
    """Campo com um nome por linha: cada linha sai numa linha do PDF."""
    return ' \\\\\n'.join(escapa_latex(linha) for linha in _linhas(texto))


def escapa_latex_paragrafos(texto):
    """Texto livre (introdução): cada linha preenchida vira um parágrafo."""
    return '\n\n'.join(escapa_latex(linha) for linha in _linhas(texto))


def _open_template(template_path):
    with open(template_path, 'r') as f:
        return f.read()


def _preenche(template, valores):
    """
    Troca todos os placeholders numa passada só. Com replace em cadeia, um
    valor já inserido que contivesse outro placeholder (ex.: "ORGANIZADORES"
    digitado pelo coordenador) seria substituído de novo.
    """
    chaves = sorted(valores, key=len, reverse=True)
    padrao = re.compile('|'.join(re.escape(chave) for chave in chaves))
    return padrao.sub(lambda m: valores[m.group(0)], template)


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

        
        doc_gerado = _preenche(_open_template(template_path), {
            '_TITULO_RESUMO_':   dados.get('titulo_resumo', ''),
            '_AUTORES_':         dados.get('autores', ''),
            '_DISCIPLINA_':      dados.get('disciplina', ''),
            '_PROGRAMA_PEPICT_': dados.get('pepict', ''),
            '_OBJETIVOS_':       dados.get('objetivos', ''),
            '_METODOLOGIA_':     dados.get('metodologia', ''),
            '_RESULTADOS_':      dados.get('resultados', ''),
            '_ODS_':             dados.get('ods', ''),
            '_REFLEXAO_':        dados.get('reflexao', ''),
            '_REFERENCIAS_':     dados.get('referencias', ''),
        })

        _salva_arquivo(output_path, doc_gerado)

    elif document_type == 'revista':

        template_path = os.path.join(BASE_DIR, 'arquivosTEX', 'revista.tex')
        caminho_temp_capitulos = os.path.join(BASE_DIR, 'arquivos_temp', 'conteudo_revista.txt')

        # pega conteudo dos capitulos
        with open(caminho_temp_capitulos, "r", encoding="utf-8") as arquivo:
            capitulos = arquivo.read()

        doc_gerado = _preenche(_open_template(template_path), {
            'NOME_DA_REVISTA': dados.get('titulo_revista', 'titulo da revista'),
            'ANO_PUBLICACAO':  str(dados.get('data', 'DATA')), # Forçado para string caso venha objeto datetime
            # Expediente: o que estiver em branco sai vazio (placeholder com "_" faz o pdflatex falhar)
            'NOME_COORDENADOR_GERAL_PEPICT': dados.get('coordenador_geral', ''),
            'NOME_COORDENADOR_EDITORIAL':    dados.get('coordenador_editorial', ''),
            'NOME_COMISSAO':                 dados.get('comissao', ''),
            'NOME_REVISAO':                  dados.get('revisao', ''),
            'NOME_DIAGRAMACAO':              dados.get('diagramacao', ''),
            'ORGANIZADORES':                 dados.get('organizadores', ''),
            '_INTRODUCAO_REVISTA_':          dados.get('introducao', ''),
            '_CONTEUDO_REVISTA_':            capitulos,
        })

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

    # Sumário: a 1ª passada grava o .toc e as seguintes o imprimem. Se o sumário
    # ocupar mais de uma página, os números só se acertam numa 3ª passada, então
    # repete até o .toc parar de mudar. Sem sumário (resumo), uma passada basta.
    toc_path = tex_path.replace('.tex', '.toc')
    toc_anterior = None

    for _ in range(MAX_PASSADAS):
        try:
            subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-output-directory', output_dir, tex_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"pdflatex falhou:\nstdout: {e.stdout.decode()}\nstderr: {e.stderr.decode()}"
            )

        if not os.path.exists(toc_path):
            break
        with open(toc_path, 'rb') as f:
            toc = f.read()
        if toc == toc_anterior:
            break
        toc_anterior = toc

    if not os.path.exists(pdf_path):
        raise FileNotFoundError("O arquivo PDF não foi gerado. Verifique o .tex e o log.")

    # Remove arquivos auxiliares gerados pelo pdflatex
    for ext in ('.aux', '.log', '.out', '.toc'):
        aux = tex_path.replace('.tex', ext)
        if os.path.exists(aux):
            os.remove(aux)

    return pdf_path