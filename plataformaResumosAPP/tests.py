import os
import re
import shutil
import subprocess
import tempfile
from unittest import skipUnless
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from . import topdf
from .models import Usuario, Semestre, Turma, Projeto, Revista, ProjetoRevista, Inscricao, Submissao, ODS
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


class CriarTurmaSemestreTest(TestCase):
    """Issue #20: a turma nova vai para o semestre mais recente, não para o de menor id."""

    def test_usa_semestre_mais_recente(self):
        coordenador = Usuario.objects.create_user('coord', password='x', tipo_usuario=3)
        professor = Usuario.objects.create_user('prof', password='x', tipo_usuario=2)
        # O antigo é cadastrado primeiro, então fica com o menor id
        Semestre.objects.create(ano=2026, semestre=1, coordenador=coordenador)
        atual = Semestre.objects.create(ano=2026, semestre=2, coordenador=coordenador)

        self.client.force_login(professor)
        self.client.post(reverse('criar_turma'), {
            'nome_turma': 'T1', 'disciplina': 'Disciplina', 'curso': 'Curso',
        })
        self.assertEqual(Turma.objects.get().semestre, atual)


class RascunhoEEnvioTest(TestCase):
    """Issues #17 e #18: rascunho aceita campos vazios; envio salva, valida e só então envia."""

    def setUp(self):
        coordenador = Usuario.objects.create_user('coord', password='x', tipo_usuario=3)
        professor = Usuario.objects.create_user('prof', password='x', tipo_usuario=2)
        self.aluno = Usuario.objects.create_user('aluno', password='x', tipo_usuario=1)
        semestre = Semestre.objects.create(ano=2026, semestre=2, coordenador=coordenador)
        self.turma = Turma.objects.create(
            responsavel=professor, semestre=semestre, nome_turma='T1',
            codigo_acesso='ABC123', disciplina='Disciplina', curso='Curso',
        )
        inscricao = Inscricao.objects.create(aluno=self.aluno, turma=self.turma)
        self.url = reverse('relatorio_projeto', args=[inscricao.id])
        self.client.force_login(self.aluno)
        self.client.get(self.url)  # cria o projeto, os programas e os ODS
        self.projeto = Projeto.objects.get(aluno=self.aluno)

    def _completo(self, **mudancas):
        dados = {
            'titulo_projeto': 'Titulo', 'nome_autores': 'Aluno', 'objetivos_trabalho': 'o',
            'metodologia_projeto': 'm', 'resultados_projeto': 'r', 'justificativa_ods': 'j',
            'reflexao_projeto': 'rf', 'referencia_projeto': '',
            'programa': [self.projeto.programa.first().pk],
            'ods': [ODS.objects.get(numero=4).pk],
        }
        dados.update(mudancas)
        return dados

    def _vazio(self, **campos):
        dados = {campo: '' for campo in (
            'titulo_projeto', 'nome_autores', 'objetivos_trabalho', 'metodologia_projeto',
            'resultados_projeto', 'justificativa_ods', 'reflexao_projeto', 'referencia_projeto',
        )}
        dados.update(campos)
        return dados

    # #17 -------------------------------------------------------------------
    def test_rascunho_salva_com_campos_vazios(self):
        resposta = self.client.post(self.url, self._vazio(objetivos_trabalho='So objetivos', acao='rascunho'))
        self.assertRedirects(resposta, self.url)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.objetivos_trabalho, 'So objetivos')
        self.assertEqual(self.projeto.status_projeto, 0)

    def test_navegador_nao_barra_campos_vazios(self):
        # Os inputs saem com "required"; sem novalidate o navegador bloqueia o rascunho
        html = self.client.get(self.url).content.decode()
        self.assertIn('id="form-relatorio" novalidate', html)

    def test_enter_sem_acao_salva_rascunho(self):
        resposta = self.client.post(self.url, self._vazio(objetivos_trabalho='x'))
        self.assertRedirects(resposta, self.url)
        self.assertFalse(Submissao.objects.exists())

    def test_rascunho_recusa_mais_de_3_ods(self):
        ods = list(ODS.objects.values_list('pk', flat=True)[:4])
        resposta = self.client.post(self.url, self._vazio(objetivos_trabalho='x', ods=ods, acao='rascunho'))
        self.assertContains(resposta, 'Você deve selecionar entre 1 e 3 ODS.')
        self.projeto.refresh_from_db()
        self.assertNotEqual(self.projeto.objetivos_trabalho, 'x')

    # #18 -------------------------------------------------------------------
    def test_enviar_completo_salva_e_envia(self):
        resposta = self.client.post(self.url, self._completo(objetivos_trabalho='Digitado agora', acao='enviar'))
        self.assertRedirects(resposta, reverse('dashboard_aluno'))
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.objetivos_trabalho, 'Digitado agora')  # nada digitado se perde
        self.assertEqual(self.projeto.status_projeto, 1)
        self.assertEqual(Submissao.objects.filter(projeto=self.projeto).count(), 1)

    def test_enviar_incompleto_salva_rascunho_e_mostra_erros(self):
        resposta = self.client.post(self.url, self._completo(metodologia_projeto='', objetivos_trabalho='Novo', acao='enviar'))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Preencha este campo para enviar.')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.objetivos_trabalho, 'Novo')  # rascunho salvo
        self.assertEqual(self.projeto.status_projeto, 0)
        self.assertFalse(Submissao.objects.exists())

    def test_enviar_sem_ods_mostra_erro(self):
        resposta = self.client.post(self.url, self._completo(ods=[], acao='enviar'))
        self.assertContains(resposta, 'Você deve selecionar entre 1 e 3 ODS.')
        self.assertFalse(Submissao.objects.exists())

    def test_rota_de_submissao_recusa_resumo_incompleto(self):
        self.client.post(self.url, self._vazio(objetivos_trabalho='x', acao='rascunho'))
        resposta = self.client.post(reverse('submissao_projeto', args=[self.projeto.id]))
        self.assertRedirects(resposta, self.url)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_projeto, 0)
        self.assertFalse(Submissao.objects.exists())

    def test_rota_de_submissao_envia_resumo_completo_salvo(self):
        self.client.post(self.url, self._completo(acao='rascunho'))
        resposta = self.client.post(reverse('submissao_projeto', args=[self.projeto.id]))
        self.assertRedirects(resposta, reverse('dashboard_aluno'), fetch_redirect_response=False)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_projeto, 1)

    def test_rota_de_submissao_so_aceita_post(self):
        self.assertEqual(self.client.get(reverse('submissao_projeto', args=[self.projeto.id])).status_code, 405)


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


class CadernoEditavelTest(TestCase):
    """Coordenador edita introdução e expediente; o PDF usa o que foi salvo."""

    def setUp(self):
        self.coordenador = Usuario.objects.create_user(
            'coord', password='x', tipo_usuario=3, first_name='Ana', last_name='Coord',
        )
        self.professor = Usuario.objects.create_user('prof', password='x', tipo_usuario=2)
        semestre = Semestre.objects.create(ano=2026, semestre=2, coordenador=self.coordenador)
        self.turma = Turma.objects.create(
            responsavel=self.professor, semestre=semestre, nome_turma='T1',
            codigo_acesso='ABC123', disciplina='Disciplina', curso='Curso',
        )
        self.revista = Revista.objects.create(titulo='Caderno', semestre=semestre)
        self._projeto('Resumo')
        self.client.force_login(self.coordenador)
        preserva_conteudo_revista(self)

    def _projeto(self, titulo, turma=None):
        aluno = Usuario.objects.create_user(f'aluno-{titulo}', password='x', tipo_usuario=1)
        projeto = Projeto.objects.create(
            aluno=aluno, turma=turma or self.turma, titulo_projeto=titulo, nome_autores='Aluno',
            objetivos_trabalho='o', metodologia_projeto='m', resultados_projeto='r',
            justificativa_ods='j', reflexao_projeto='rf', status_projeto=2,
        )
        ProjetoRevista.objects.create(revista=self.revista, projeto=projeto)
        return projeto

    def _tex_gerado(self):
        """Gera o PDF pela view, mas captura o .tex em vez de compilar."""
        capturado = {}

        def falso_to_pdf(dados):
            caminho = topdf.to_tex(dados)
            with open(caminho, encoding='utf-8') as arquivo:
                capturado['tex'] = arquivo.read()
            os.remove(caminho)
            return caminho  # já removido: a view só mostra a mensagem de erro

        with patch('plataformaResumosAPP.views.to_pdf', side_effect=falso_to_pdf):
            self.client.get(reverse('pdf_revista', args=[self.revista.id]))
        return capturado['tex']

    def _pdf_real(self):
        """Gera o PDF da revista com o pdflatex e devolve o texto, página por página."""
        # A view não apaga o PDF nem o .tex gerados em arquivos_temp: o teste apaga
        gerados = []

        def to_pdf_registrando(dados):
            pdf = topdf.to_pdf(dados)
            gerados.append(pdf)
            self.addCleanup(remove_se_existe, pdf, pdf.replace('.pdf', '.tex'))
            return pdf

        with patch('plataformaResumosAPP.views.to_pdf', side_effect=to_pdf_registrando):
            resposta = self.client.get(reverse('pdf_revista', args=[self.revista.id]))
        self.assertEqual(resposta.status_code, 200)
        resposta.close()
        texto = subprocess.run(['pdftotext', '-layout', gerados[0], '-'], capture_output=True, text=True).stdout
        return texto.split('\f')

    def test_so_coordenador_acessa(self):
        for tipo, nome in ((1, 'a2'), (2, 'p2')):
            self.client.force_login(Usuario.objects.create_user(nome, password='x', tipo_usuario=tipo))
            self.assertEqual(self.client.get(reverse('caderno', args=[self.revista.id])).status_code, 403)

    def test_salva_campos(self):
        resposta = self.client.post(reverse('caderno', args=[self.revista.id]), {
            'titulo': 'Caderno 2026/2', 'introducao': 'Texto',
            'comissao': 'Fulano\nBeltrana', 'revisao': '',
        })
        self.assertRedirects(resposta, reverse('caderno', args=[self.revista.id]))
        self.revista.refresh_from_db()
        self.assertEqual(self.revista.titulo, 'Caderno 2026/2')
        self.assertEqual(self.revista.comissao, 'Fulano\nBeltrana')

    def test_tela_lista_resumos_na_ordem_do_pdf(self):
        # Duas turmas com a mesma disciplina e o mesmo nome não podem se misturar
        gemea = Turma.objects.create(
            responsavel=self.professor, semestre=self.turma.semestre, nome_turma='T1',
            codigo_acesso='GEMEA1', disciplina='Disciplina', curso='Curso',
        )
        self._projeto('A da gemea', turma=gemea)
        self._projeto('Z da primeira')

        html = self.client.get(reverse('caderno', args=[self.revista.id])).content.decode()
        self.assertEqual(html.count('Disciplina · T1'), 2)
        self.assertLess(html.index('Resumo'), html.index('Z da primeira'))
        self.assertLess(html.index('Z da primeira'), html.index('A da gemea'))

        tex = self._tex_gerado()
        self.assertEqual(tex.count(r'\chapter{Disciplina}'), 2)
        self.assertLess(tex.index(r'\section{Z da primeira}'), tex.index(r'\section{A da gemea}'))

    def test_pdf_usa_campos_salvos(self):
        self.revista.introducao = 'Primeiro paragrafo\nSegundo_paragrafo'
        self.revista.comissao = 'Fulano\n\nBeltrana'
        self.revista.organizadores = 'Org 100%'
        self.revista.save()

        tex = self._tex_gerado()
        self.assertIn('Primeiro paragrafo\n\nSegundo\\_paragrafo', tex)
        self.assertIn('Fulano \\\\\nBeltrana', tex)
        self.assertIn('Org 100\\%', tex)
        self.assertIn('Ana Coord', tex)  # coordenação geral em branco: usa o coordenador do semestre
        for placeholder in ('NOME_', 'ORGANIZADORES', '_INTRODUCAO_REVISTA_', '_CONTEUDO_REVISTA_'):
            self.assertNotIn(placeholder, tex)

    def test_placeholder_digitado_nao_e_substituido_de_novo(self):
        self.revista.comissao = 'Comissão dos ORGANIZADORES'
        self.revista.organizadores = 'Fulano'
        self.revista.save()

        tex = self._tex_gerado()
        self.assertIn('Comissão dos ORGANIZADORES', tex)

    @skipUnless(shutil.which('pdflatex') and shutil.which('pdftotext'), 'precisa do pdflatex e do pdftotext')
    def test_pdf_real_com_expediente_e_sumario(self):
        # "[" e "*" no começo da linha viriam logo depois de um "\\" do template
        self.revista.comissao = '[Coord.] Fulano\n* Beltrana'
        self.revista.save()

        paginas = self._pdf_real()
        texto = '\n'.join(paginas)
        self.assertIn('[Coord.] Fulano', texto)
        self.assertIn('* Beltrana', texto)
        # "Introdução" aparece no sumário e depois no capítulo
        self.assertEqual(texto.split('Sumário', 1)[1].count('Introdução'), 2)

    @skipUnless(shutil.which('pdflatex') and shutil.which('pdftotext'), 'precisa do pdflatex e do pdftotext')
    def test_sumario_longo_tem_numeros_de_pagina_certos(self):
        # Com ~50 resumos o sumário ocupa 2 páginas e empurra o resto do caderno
        for i in range(2, 51):
            self._projeto(f'Resumo {i:02d}')

        paginas = self._pdf_real()
        entrada = re.compile(r'Resumo 50[ .]*(\d+)\s*$', re.MULTILINE)
        no_sumario = next(int(m.group(1)) for p in paginas if (m := entrada.search(p)))
        pagina_do_resumo = next(
            p for p in paginas
            if re.search(r'^\s*\d+\.\d+\s+Resumo 50\s*$', p, re.MULTILINE) and not entrada.search(p)
        )
        numero_impresso = int(pagina_do_resumo.strip().splitlines()[-1].strip())
        self.assertEqual(no_sumario, numero_impresso)
