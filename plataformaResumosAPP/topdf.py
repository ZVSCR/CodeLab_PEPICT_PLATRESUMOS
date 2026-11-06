import subprocess
import os
import re
import unicodedata
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


# --- Unicode (issue #32) ---
# O pdflatex (inputenc utf8 + fontenc T1) só conhece parte do Unicode: um único caractere
# desconhecido (ex.: ≥, α, CO₂, emoji) derruba a compilação do PDF inteiro.
# Faixas que o pdflatex aceita com os nossos templates (conferidas compilando cada uma):
# Latin-1, Latin Extended-A (menos alguns), pontuação tipográfica, € ™ № e setas simples.
_FAIXAS_ACEITAS = (
    (0x20, 0x7E), (0xA0, 0xAC), (0xAE, 0x125), (0x128, 0x137), (0x139, 0x13E),
    (0x141, 0x148), (0x14A, 0x165), (0x168, 0x17E), (0x2010, 0x2016), (0x2018, 0x201A),
    (0x201C, 0x201E), (0x2020, 0x2022), (0x2026, 0x2026), (0x2030, 0x2030),
    (0x2039, 0x203A), (0x20AC, 0x20AC), (0x2116, 0x2116), (0x2122, 0x2122), (0x2190, 0x2193),
)
ACEITOS_PDFLATEX = frozenset(
    chr(c) for inicio, fim in _FAIXAS_ACEITAS for c in range(inicio, fim + 1)
) | {'\n', '\r', '\t'}

_MATEMATICA = {
    '≥': r'\geq', '≤': r'\leq', '≠': r'\neq', '≈': r'\approx', '≡': r'\equiv',
    '∞': r'\infty', '√': r'\surd', '∑': r'\sum', '∏': r'\prod', '∂': r'\partial',
    '∆': r'\Delta', '∇': r'\nabla', '∈': r'\in', '∉': r'\notin', '∩': r'\cap',
    '∪': r'\cup', '⊂': r'\subset', '⊃': r'\supset', '∀': r'\forall', '∃': r'\exists',
    '∝': r'\propto', '∠': r'\angle', '−': '-', '∓': r'\mp', '∗': '*', '∘': r'\circ',
    '⇒': r'\Rightarrow', '⇐': r'\Leftarrow', '⇔': r'\Leftrightarrow', '↔': r'\leftrightarrow',
    '′': "'", '″': "''",
}
_GREGO = dict(zip(
    'αβγδεζηθικλμνξπρςστυφχψω',
    'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi '
    'rho varsigma sigma tau upsilon phi chi psi omega'.split(),
))
_GREGO.update({'Γ': 'Gamma', 'Δ': 'Delta', 'Θ': 'Theta', 'Λ': 'Lambda', 'Ξ': 'Xi', 'Π': 'Pi',
               'Σ': 'Sigma', 'Υ': 'Upsilon', 'Φ': 'Phi', 'Ψ': 'Psi', 'Ω': 'Omega'})
# Maiúsculas gregas iguais às latinas e o ômicron saem como letra comum
_GREGO_COMO_LATINO = dict(zip('ΑΒΕΖΗΙΚΜΝΟΡΤΧο', 'ABEZHIKMNOPTXo'))
_SOBRESCRITO = dict(zip('⁰⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ', '0456789+-=()ni'))
_SUBSCRITO = dict(zip('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎', '0123456789+-=()'))
# Espaços especiais viram espaço comum; caracteres invisíveis somem
_ESPACOS = set('\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\u2028\u2029')
_INVISIVEIS = set('\u00ad\u200b\u200c\u200d\u2060\ufeff')

UNICODE_LATEX = {}
UNICODE_LATEX.update({c: r'\ensuremath{%s}' % cmd for c, cmd in _MATEMATICA.items()})
UNICODE_LATEX.update({c: r'\ensuremath{\%s}' % nome for c, nome in _GREGO.items()})
UNICODE_LATEX.update(_GREGO_COMO_LATINO)
UNICODE_LATEX.update({c: r'\textsuperscript{%s}' % v for c, v in _SOBRESCRITO.items()})
UNICODE_LATEX.update({c: r'\textsubscript{%s}' % v for c, v in _SUBSCRITO.items()})
UNICODE_LATEX.update({c: ' ' for c in _ESPACOS})
UNICODE_LATEX.update({c: '' for c in _INVISIVEIS})


def _escapa_caractere(c):
    if c in LATEX_ESPECIAIS:
        return LATEX_ESPECIAIS[c]
    if c in UNICODE_LATEX:
        return UNICODE_LATEX[c]
    if c in ACEITOS_PDFLATEX:
        return c
    # Letra com acentos demais (ex.: ễ, do vietnamita): tira um acento por vez até
    # sobrar uma letra que o pdflatex conhece (ễ -> ê)
    decomposto = unicodedata.normalize('NFD', c)
    while len(decomposto) > 1 and unicodedata.combining(decomposto[-1]):
        decomposto = decomposto[:-1]
        reduzido = unicodedata.normalize('NFC', decomposto)
        if reduzido in ACEITOS_PDFLATEX:
            return reduzido
    # Tenta a forma "simples" do caractere (ﬁ -> fi, ① -> 1, ệ -> e) e tira os acentos
    # que o pdflatex não conhece. O que sobrar (emoji, outros alfabetos) é removido:
    # perder um símbolo é melhor do que o PDF não sair.
    simples = unicodedata.normalize('NFKD', c)
    if simples != c:
        return ''.join(
            _escapa_caractere(parte) for parte in simples if not unicodedata.combining(parte)
        )
    return ''


def escapa_latex(texto):
    """
    Prepara o texto do usuário para o LaTeX: escapa os caracteres especiais (para sair
    literal e não virar comando) e troca ou remove o Unicode que o pdflatex não suporta.
    """
    # NFC junta letra + acento separado (comum em texto colado do Mac/PDF) num caractere só
    texto = unicodedata.normalize('NFC', str(texto or ''))
    return ''.join(_escapa_caractere(c) for c in texto)


def _linhas(texto):
    return [linha.strip() for linha in str(texto or '').splitlines() if linha.strip()]


def escapa_latex_linhas(texto):
    """Campo com um nome por linha: cada linha sai numa linha do PDF."""
    return ' \\\\\n'.join(escapa_latex(linha) for linha in _linhas(texto))


def escapa_latex_paragrafos(texto):
    """Texto livre (introdução): cada linha preenchida vira um parágrafo."""
    return '\n\n'.join(escapa_latex(linha) for linha in _linhas(texto))


class LatexPronto(str):
    """
    Texto que já é LaTeX montado pelo sistema (ex.: os capítulos do caderno).
    O to_tex insere como está, sem escapar. Texto digitado pelo usuário nunca deve usar isto.
    """


def _formata(valor, formatador=escapa_latex):
    """Escapa o valor para o template, a não ser que ele já seja LaTeX pronto."""
    if isinstance(valor, LatexPronto):
        return str(valor)
    return formatador(valor)


# Placeholder do template -> (chave em dados, como formatar o texto)
CAMPOS_RESUMO = {
    '_TITULO_RESUMO_':   ('titulo_resumo', escapa_latex),
    '_AUTORES_':         ('autores', escapa_latex),
    '_DISCIPLINA_':      ('disciplina', escapa_latex),
    '_PROGRAMA_PEPICT_': ('pepict', escapa_latex),
    '_OBJETIVOS_':       ('objetivos', escapa_latex),
    '_METODOLOGIA_':     ('metodologia', escapa_latex),
    '_RESULTADOS_':      ('resultados', escapa_latex),
    '_ODS_':             ('ods', escapa_latex),
    '_REFLEXAO_':        ('reflexao', escapa_latex),
    '_REFERENCIAS_':     ('referencias', escapa_latex),
}

CAMPOS_REVISTA = {
    'NOME_DA_REVISTA': ('titulo_revista', escapa_latex),
    'ANO_PUBLICACAO':  ('data', escapa_latex),
    # Expediente: um nome por linha; o que estiver em branco sai vazio
    'NOME_COORDENADOR_GERAL_PEPICT': ('coordenador_geral', escapa_latex_linhas),
    'NOME_COORDENADOR_EDITORIAL':    ('coordenador_editorial', escapa_latex_linhas),
    'NOME_COMISSAO':                 ('comissao', escapa_latex_linhas),
    'NOME_REVISAO':                  ('revisao', escapa_latex_linhas),
    'NOME_DIAGRAMACAO':              ('diagramacao', escapa_latex_linhas),
    'ORGANIZADORES':                 ('organizadores', escapa_latex_linhas),
    '_INTRODUCAO_REVISTA_':          ('introducao', escapa_latex_paragrafos),
    # Montado pelo sistema (gera_capitulos devolve LatexPronto)
    '_CONTEUDO_REVISTA_':            ('capitulos', escapa_latex),
}

TEMPLATES = {
    'resumo': ('resumo.tex', CAMPOS_RESUMO),
    'revista': ('revista.tex', CAMPOS_REVISTA),
}


def _open_template(template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
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
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(conteudo)


def to_tex(dados, output_dir):
    """
    Gera o arquivo .tex preenchido com os dados fornecidos e retorna o caminho dele.

    Os valores de dados são o texto puro, como está no banco: o escape para o LaTeX
    acontece só aqui, para todo campo (exceto o que vier como LatexPronto).
    """
    document_type = dados.get('document_type')
    if document_type not in TEMPLATES:
        raise ValueError(f"Tipo de documento desconhecido: {document_type}")

    nome_template, campos = TEMPLATES[document_type]
    template = _open_template(os.path.join(BASE_DIR, 'arquivosTEX', nome_template))
    valores = {
        placeholder: _formata(dados.get(chave, ''), formatador)
        for placeholder, (chave, formatador) in campos.items()
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.tex")
    _salva_arquivo(output_path, _preenche(template, valores))
    return output_path


def to_pdf(dados, output_dir):
    """
    Compila o .tex gerado por to_tex e retorna o caminho do PDF.
    """
    tex_path = to_tex(dados, output_dir)
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