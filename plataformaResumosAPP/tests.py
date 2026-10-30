import tempfile
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Usuario, Semestre, Turma, Projeto


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
        with patch('plataformaResumosAPP.views.to_pdf', return_value=pdf.name):
            return self.client.get(reverse('pdf_resumo', args=[self.projeto.id]))

    def test_coordenador_baixa_resumo_aprovado(self):
        resposta = self._baixar_pdf()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('attachment', resposta['Content-Disposition'])

    def test_coordenador_nao_baixa_resumo_nao_aprovado(self):
        for status in (0, 1, 3):
            self.projeto.status_projeto = status
            self.projeto.save()
            self.assertEqual(self._baixar_pdf().status_code, 404)
