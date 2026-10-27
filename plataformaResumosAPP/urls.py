from django.urls import path
from .views import login_view,cadastro_view,dashboard_aluno,dashboard_professor,dashboard_coordenador,logout_view ,criar_turma_view,inscrever_em_turma_view,relatorio_view,submissao_view,painel_turma_view,projeto_analise_view,turmas_coordenador_view,projetos_aprovados_view,projeto_leitura_view,pdf_resumo_view, gera_revista_view,gerencia_tipo_usuario_view,ajuda_view,privacidade_view

urlpatterns = [
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('cadastro/', cadastro_view, name='cadastro'),
    path('logout/', logout_view, name='logout'),
    path('aluno/', dashboard_aluno, name='dashboard_aluno'),
    path('professor/', dashboard_professor, name='dashboard_professor'),
    path('coordenador/', dashboard_coordenador, name='dashboard_coordenador'),
    path('criarturma/', criar_turma_view, name='criar_turma'),
    path('inscricao/', inscrever_em_turma_view, name='inscrever_em_turma'),
    path('relatorio/<int:inscricao_id>/', relatorio_view, name='relatorio_projeto'),
    path('projeto/<int:projeto_id>/submeter/', submissao_view, name='submissao_projeto'),
    path('painel_turma/<int:turma_id>/', painel_turma_view, name='painel_turma'),
    path('projeto_em_analise/<int:projeto_id>/', projeto_analise_view ,name='projeto_analise'),
    path('coordenador/turmas/', turmas_coordenador_view, name='turmas_coordenador'),
    path('coordenador/turma/<int:turma_id>/aprovados/', projetos_aprovados_view, name='projetos_aprovados'),
    path('coordenador/projeto/<int:projeto_id>/leitura/', projeto_leitura_view, name='projeto_leitura'),
    path('projeto/<int:projeto_id>/pdf/', pdf_resumo_view, name='pdf_resumo'), 
    path('coordenador/revista/<int:revista_id>/pdf/', gera_revista_view, name='pdf_revista'),
    path('coordenador/gerencia_tipo_usuario',gerencia_tipo_usuario_view,name='gerenciar_tipos_usuarios'),
    path('ajuda/', ajuda_view, name='ajuda'),
    path('privacidade/', privacidade_view, name='privacidade'),
]