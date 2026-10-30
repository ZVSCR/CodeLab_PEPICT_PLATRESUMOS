import os
import shutil
import subprocess
import tempfile
from unittest import skipUnless
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from . import topdf
from .models import Usuario, Semestre, Turma, Projeto, Revista, ProjetoRevista
from .views import gera_capitulos

CONTEUDO_REVISTA = os.path.join(os.path.dirname(topdf.__file__), 'arquivos_temp', 'conteudo_revista.txt')
TEXTO_ESPECIAL = r'50% a_b [x] "q" #1 & $2 ~ ^ {c} \input{/etc/passwd}'


def preserva_conteudo_revista(test):
    """gera_capitulos escreve no conteudo_revista.txt versionado: restaura no fim do teste."""
    # Em bytes: o arquivo versionado tem fim de linha CRLF
    with open(CONTEUDO_REVISTA, 'rb') as arquivo:
        original = arquivo.read()

    def restaura():
        with open(CONTEUDO_REVISTA, 'wb') as arquivo:
            arquivo.write(original)

    test.addCleanup(restaura)


def remove_se_existe(*caminhos):
    for caminho in caminhos:
        if os.path.exists(caminho):
            os.remove(caminho)


class PdfResumoCoordenadorTest(TestCase):
    """Issue #15: o coordenador baixa o PDF de qualquer resumo aprovado."""

    def setUp(self):
        self.coordenador = Usuario.objects.create_user('coord', password='x', tipo_usuario=3)
        professor = Usuario.objects.create_user('prof', password='x', tipo_usuario=2)
        aluno = Usuario.objects.create_user('aluno', password='x', tipo_usuario=1)

        semestre = Semestre.objects.create(ano=2026, semestre=2, coordenador=self.coordenador)
        turma = Turma.objects.create(
            responsavel=professor, semestre=semestre, nome_turma='T1',
            codigo_acesso='ABC123', disciplina='Disciplina', curso='Curso',
        )
        self.projeto = Projeto.objects.create(
            aluno=aluno, turma=turma, titulo_projeto='Resumo', nome_autores='Aluno',
            objetivos_trabalho='o', metodologia_projeto='m', resultados_projeto='r',
            justificativa_ods='j', reflexao_projeto='rf', status_projeto=2,
        )
        self.client.force_login(self.coordenador)

    def _baixar_pdf(self):
        # Evita depender do pdflatex: to_pdf devolve um arquivo qualquer
        pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        pdf.write(b'%PDF-1.4')
        pdf.close()
        self.addCleanup(remove_se_existe, pdf.name)
        with patch('plataformaResumosAPP.views.to_pdf', return_value=pdf.name) as to_pdf:
            resposta = self.client.get(reverse('pdf_resumo', args=[self.projeto.id]))
        resposta.dados = to_pdf.call_args.args[0] if to_pdf.called else None
        return resposta

    def test_coordenador_baixa_resumo_aprovado(self):
        resposta = self._baixar_pdf()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('attachment', resposta['Content-Disposition'])

    def test_coordenador_nao_baixa_resumo_nao_aprovado(self):
        for status in (0, 1, 3):
            self.projeto.status_projeto = status
            self.projeto.save()
            self.assertEqual(self._baixar_pdf().status_code, 404)

    def test_escapa_texto_do_resumo(self):
        self.projeto.objetivos_trabalho = TEXTO_ESPECIAL
        self.projeto.save()

        dados = self._baixar_pdf().dados
        self.assertEqual(dados['objetivos'], topdf.escapa_latex(TEXTO_ESPECIAL))
        self.assertNotIn(r'\input', dados['objetivos'])

    def test_falha_sem_referer_volta_ao_painel_do_coordenador(self):
        with patch('plataformaResumosAPP.views.to_pdf', side_effect=RuntimeError('pdflatex falhou')):
            resposta = self.client.get(reverse('pdf_resumo', args=[self.projeto.id]))
        self.assertRedirects(resposta, reverse('dashboard_coordenador'))

    @skipUnless(shutil.which('pdflatex') and shutil.which('pdftotext'), 'precisa do pdflatex e do pdftotext')
    def test_pdf_real_com_caracteres_especiais(self):
        dados = {chave: '' for chave in (
            'titulo_resumo', 'autores', 'disciplina', 'pepict', 'metodologia',
            'resultados', 'ods', 'reflexao', 'referencias',
        )}
        dados.update(document_type='resumo', objetivos=topdf.escapa_latex(TEXTO_ESPECIAL))

        pdf = topdf.to_pdf(dados)
        self.addCleanup(remove_se_existe, pdf, pdf.replace('.pdf', '.tex'))
        texto = subprocess.run(['pdftotext', pdf, '-'], capture_output=True, text=True).stdout
        self.assertIn(TEXTO_ESPECIAL, texto)


class CadernoRevistaTest(TestCase):
    """Issue #16: o caderno só traz os resumos incluídos, com o texto escapado."""

    def setUp(self):
        coordenador = Usuario.objects.create_user('coord', password='x', tipo_usuario=3)
        professor = Usuario.objects.create_user('prof', password='x', tipo_usuario=2)
        semestre = Semestre.objects.create(ano=2026, semestre=2, coordenador=coordenador)
        self.turma = Turma.objects.create(
            responsavel=professor, semestre=semestre, nome_turma='T1',
            codigo_acesso='ABC123', disciplina='Disciplina', curso='Curso',
        )
        self.revista = Revista.objects.create(titulo='Caderno', semestre=semestre)
        preserva_conteudo_revista(self)

    def _projeto(self, titulo, status=2, na_revista=True, **campos):
        aluno = Usuario.objects.create_user(titulo, password='x', tipo_usuario=1)
        dados = dict(
            nome_autores='Aluno', objetivos_trabalho='o', metodologia_projeto='m',
            resultados_projeto='r', justificativa_ods='j', reflexao_projeto='rf',
        )
        dados.update(campos)
        projeto = Projeto.objects.create(
            aluno=aluno, turma=self.turma, titulo_projeto=titulo, status_projeto=status, **dados,
        )
        if na_revista:
            ProjetoRevista.objects.create(revista=self.revista, projeto=projeto)
        return projeto

    def _conteudo(self):
        gera_capitulos(self.revista.id)
        with open(CONTEUDO_REVISTA, encoding='utf-8') as arquivo:
            return arquivo.read()

    def test_inclui_so_resumos_marcados(self):
        self._projeto('incluido')
        self._projeto('fora', na_revista=False)
        self._projeto('rascunho', status=0, na_revista=False)

        conteudo = self._conteudo()
        self.assertIn(r'\section{incluido}', conteudo)
        self.assertNotIn('fora', conteudo)
        self.assertNotIn('rascunho', conteudo)

    def test_turma_sem_resumo_aprovado_nao_vira_capitulo(self):
        self._projeto('incluido')
        # Projeto não aprovado que ficou na revista (ex.: dado antigo ou criado pelo admin)
        outra = Turma.objects.create(
            responsavel=self.turma.responsavel, semestre=self.turma.semestre, nome_turma='T2',
            codigo_acesso='XYZ789', disciplina='Outra disciplina', curso='Curso',
        )
        aluno = Usuario.objects.create_user('a2', password='x', tipo_usuario=1)
        projeto = Projeto.objects.create(
            aluno=aluno, turma=outra, titulo_projeto='em analise', status_projeto=1,
            nome_autores='A', objetivos_trabalho='o', metodologia_projeto='m',
            resultados_projeto='r', justificativa_ods='j', reflexao_projeto='rf',
        )
        ProjetoRevista.objects.create(revista=self.revista, projeto=projeto)

        conteudo = self._conteudo()
        self.assertEqual(conteudo.count(r'\chapter'), 1)
        self.assertNotIn('Outra disciplina', conteudo)

    def test_escapa_texto_do_aluno(self):
        self._projeto('a_b', objetivos_trabalho=TEXTO_ESPECIAL)

        conteudo = self._conteudo()
        self.assertIn(r'\section{a\_b}', conteudo)
        self.assertIn(topdf.escapa_latex(TEXTO_ESPECIAL), conteudo)
        self.assertIn(r'{[}x{]} \textquotedbl{}q\textquotedbl{}', conteudo)
        self.assertNotIn(r'\input', conteudo)
