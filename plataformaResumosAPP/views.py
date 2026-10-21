import os
import random
import string
from .topdf import to_pdf
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from .forms import LoginForm, UsuarioCreationForm, CriacaoTurma, InscricaoEmTurma, ProjetoForm,BuscaUsuarioForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseForbidden
from .models import Turma, Semestre, Inscricao, Projeto, Programa, ODS, Submissao, Revista, ProjetoRevista,Usuario
from django.db import IntegrityError
from django.db.models import Count

User = get_user_model()


def login_view(request):

    form = LoginForm(request.POST or None)

    if request.method == 'POST':

        if form.is_valid():

            username_input = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Login usando email
            if '@' in username_input:
                try:
                    user_obj = User.objects.get(
                        email=username_input
                    )
                    username = user_obj.username

                except User.DoesNotExist:
                    username = username_input

            else:
                username = username_input

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user:

                login(request, user)

                #Redirecionamento para dashboard por tipo de usuario
                if user.tipo_usuario == 1:
                    return redirect('dashboard_aluno')
                elif user.tipo_usuario == 2:
                    return redirect('dashboard_professor')
                elif user.tipo_usuario == 3:
                    return redirect('dashboard_coordenador')
            else:
                form.add_error(None, "Usuário ou senha incorretos.")

    return render(request, 'login.html', {'form': form})


def cadastro_view(request):
    if request.method == 'POST':
        form = UsuarioCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cadastro realizado com sucesso! Faça o login.")
            return redirect('login')
    else:
        form = UsuarioCreationForm()
    return render(request, 'cadastro.html', {'form': form})


@login_required
def dashboard_aluno(request):
    if request.user.tipo_usuario != 1:
        return HttpResponseForbidden()
    
   
    lista_inscricoes = Inscricao.objects.filter(aluno=request.user)
    

    for inscricao in lista_inscricoes:
        inscricao.projeto_vinculado = Projeto.objects.filter(aluno=request.user, turma=inscricao.turma).first()

    # Contadores do painel: turmas do semestre mais recente,
    # resumos editáveis (Rascunho/Rejeitado) e resumos aguardando avaliação (Em análise)
    semestre_atual = Semestre.objects.order_by('-ano', '-semestre').first()
    projetos_aluno = Projeto.objects.filter(aluno=request.user)

    return render(request, 'aluno/dashboard_aluno.html', {
        'lista_inscricoes': lista_inscricoes,
        'stat_turmas_inscritas': lista_inscricoes.filter(turma__semestre=semestre_atual).count(),
        'stat_resumos_andamento': projetos_aluno.filter(status_projeto__in=[0, 3]).count(),
        'stat_resumos_submetidos': projetos_aluno.filter(status_projeto=1).count(),
    })


@login_required
def dashboard_professor(request):
    if request.user.tipo_usuario != 2:
        return HttpResponseForbidden()
    
    lista_turmas = Turma.objects.filter(responsavel=request.user)

 
    return render(request, 'professor/dashboard_professor.html', {'lista_turmas':lista_turmas} )


@login_required
def dashboard_coordenador(request):
    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()
    
    semestre_atual = Semestre.objects.order_by('-ano', '-semestre').first()

    # Mais recentes primeiro + já conta os projetos de cada caderno numa query só
    revistas = (
        Revista.objects
        .select_related('semestre')
        .annotate(num_projetos=Count('projetos_revista'))
        .order_by('-semestre__ano', '-semestre__semestre')
    )

    return render(request, 'coordenador/dashboard_coordenador.html', {
        'revistas': revistas,
        'semestre_atual': semestre_atual,
        'stat_turmas': Turma.objects.filter(semestre=semestre_atual).count(),
        'stat_aprovados': Projeto.objects.filter(turma__semestre=semestre_atual, status_projeto=2).count(),
        'stat_cadernos': revistas.count(),
    })


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def criar_turma_view(request):
    if request.user.tipo_usuario != 2:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = CriacaoTurma(request.POST)
        if form.is_valid():
            turma = form.save(commit=False)
            
            
            turma.responsavel = request.user
            semestre_atual = Semestre.objects.first() 
            if not semestre_atual:
                messages.error(request, "Nenhum semestre cadastrado no sistema.")
                return render(request, 'professor/criar_turma.html', {'form': form})
            
            turma.semestre = semestre_atual
            
            while True:
                codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not Turma.objects.filter(codigo_acesso=codigo).exists():
                    break
            
            turma.codigo_acesso = codigo
            turma.save()
            messages.success(request, f"Turma criada com sucesso! Código de acesso: {codigo}")
            return redirect('dashboard_professor')
    else:
        form = CriacaoTurma()

    return render(request, 'professor/criar_turma.html', {'form': form})


@login_required
def inscrever_em_turma_view(request):
    if request.user.tipo_usuario != 1:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = InscricaoEmTurma(request.POST)
        if form.is_valid():
            codigo = form.cleaned_data['codigo_acesso']
            try:
                turma = Turma.objects.get(codigo_acesso=codigo)
                
                Inscricao.objects.create(aluno=request.user, turma=turma)
                messages.success(request, f"Inscrição realizada com sucesso na turma: {turma.nome_turma}")
                return redirect('dashboard_aluno')
                
            except Turma.DoesNotExist:
                messages.error(request, "Código de acesso inválido.")
            except IntegrityError:
                messages.error(request, "Você já está inscrito nesta turma.")
    else:
        form = InscricaoEmTurma()

    return render(request, 'aluno/inscricao_turma.html', {'form': form})


@login_required
def relatorio_view(request, inscricao_id):
    inscricao = get_object_or_404(Inscricao, id=inscricao_id, aluno=request.user)

    prog1, _ = Programa.objects.get_or_create(nome="Educação e Sustentabilidade")
    prog2, _ = Programa.objects.get_or_create(nome="Tecnologia e Inovação para o Desenvolvimento Social")
    
    for i in range(1, 18):
        ODS.objects.get_or_create(numero=i, defaults={'nome': f'Objetivo de Desenvolvimento Sustentável {i}'})

    projeto, criado = Projeto.objects.get_or_create(
        aluno=request.user,
        turma=inscricao.turma,
        defaults={
            'titulo_projeto': f"Projeto - {inscricao.turma.nome_turma}",
            'nome_autores': request.user.get_full_name(),
        }
    )

    if criado:
        projeto.programa.add(prog1)

    if request.method == 'POST':
  
        if projeto.status_projeto not in [0, 3]:
            messages.error(request, "Este relatório não pode ser editado pois já foi submetido.")
            return redirect('relatorio_projeto', inscricao_id=inscricao.id)

        form = ProjetoForm(request.POST, instance=projeto)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do relatório salvos com sucesso!")
            return redirect('relatorio_projeto', inscricao_id=inscricao.id)
        else:
            messages.error(request, "Erro ao salvar. Verifique os campos (ODS: mínimo 1, máximo 3).")
    else:
        form = ProjetoForm(instance=projeto)

    submissao = projeto.submissoes.order_by('-data_submissao').first()
 
    return render(request, "aluno/relatorio.html", {
        "projeto": projeto,
        "form": form,
        "submissao": submissao,
        "editavel": projeto.status_projeto in [0, 3],
    })


@login_required
def submissao_view(request, projeto_id):
    if request.user.tipo_usuario != 1:
        return HttpResponseForbidden()
    
    projeto = get_object_or_404(Projeto, id=projeto_id, aluno=request.user)
    
   
    if projeto.status_projeto in [0, 3]:
        projeto.status_projeto = 1  
        projeto.save()
        
        Submissao.objects.create(
            projeto=projeto,
            resultado_submissao=0
        )
        messages.success(request, "Projeto submetido com sucesso!")
    else:
        messages.error(request, "Este projeto não pode ser submetido no momento.")
        
    return redirect('dashboard_aluno')

@login_required
def painel_turma_view(request, turma_id):
    if request.user.tipo_usuario != 2:
        return HttpResponseForbidden()

    #busca turmas do professor conectado
    turma = get_object_or_404(
        Turma,
        id=turma_id,
        responsavel=request.user
    )

    # Busca projetos da turma encontrada
    projetos = Projeto.objects.filter(
        turma=turma,
        submissoes__isnull=False
    ).select_related(
        'aluno'
    ).distinct().order_by(
        'aluno__first_name',
        'aluno__username'
)

    return render(request, 'professor/painel_turma.html', {
        'turma': turma,
        'projetos': projetos
    })

@login_required
def projeto_analise_view(request, projeto_id):
    if request.user.tipo_usuario != 2:
        return HttpResponseForbidden()
 
    projeto = get_object_or_404(
        Projeto,
        id=projeto_id,
        turma__responsavel=request.user
    )
 
    submissao = projeto.submissoes.order_by('-data_submissao').first()
 
    if not submissao:
        messages.error(request, "Este projeto não possui submissões.")
        return redirect('painel_turma', turma_id=projeto.turma.id)
 
    ja_avaliado = submissao.resultado_submissao != 0
 
    if request.method == 'POST':
        if ja_avaliado:
            messages.error(request, "Esta submissão já foi avaliada e não pode ser alterada.")
            return redirect('projeto_analise', projeto_id=projeto.id)
 
        feedback = request.POST.get('feedback', '').strip()
        decisao = request.POST.get('decisao')
 
        if decisao not in ['1', '2']:
            messages.error(request, "Avaliação inválida.")
            return redirect('projeto_analise', projeto_id=projeto.id)
 
        submissao.feedback = feedback
        submissao.resultado_submissao = int(decisao)
        submissao.save()
 
        projeto.status_projeto = 2 if decisao == '1' else 3
        projeto.save()
 
        messages.success(request, "Avaliação registrada com sucesso.")
        return redirect('painel_turma', turma_id=projeto.turma.id)
 
    return render(request, "professor/projeto_aluno.html", {
        'projeto': projeto,
        'submissao': submissao,
        'ja_avaliado': ja_avaliado,
    })

@login_required
def turmas_coordenador_view(request):
    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()
 
    semestres = Semestre.objects.prefetch_related('turmas').order_by('-ano', '-semestre')
 
    return render(request, 'coordenador/turmas_coordenador.html', {
        'semestres': semestres,
    })
 
 
@login_required
def projetos_aprovados_view(request, turma_id):
    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()
 
    turma = get_object_or_404(Turma, id=turma_id)
 
    projetos = Projeto.objects.filter(
        turma=turma,
        status_projeto=2
    ).select_related('aluno').prefetch_related('programa', 'ods')
 
    revista, _ = Revista.objects.get_or_create(
        semestre=turma.semestre,
        defaults={'titulo': f'Revista {turma.semestre}'}
    )
 
    projetos_na_revista = set(
        ProjetoRevista.objects.filter(revista=revista).values_list('projeto_id', flat=True)
    )
 
    if request.method == 'POST':
        ids_selecionados = request.POST.getlist('projetos_selecionados')
 
        adicionados = 0
        for projeto_id in ids_selecionados:
            projeto = get_object_or_404(Projeto, id=projeto_id, turma=turma, status_projeto=2)
            _, criado = ProjetoRevista.objects.get_or_create(revista=revista, projeto=projeto)
            if criado:
                adicionados += 1
 
        if adicionados:
            messages.success(request, f"{adicionados} projeto(s) adicionado(s) à revista.")
        else:
            messages.info(request, "Os projetos selecionados já estavam na revista.")
 
        return redirect('projetos_aprovados', turma_id=turma.id)
 
    return render(request, 'coordenador/projetos_aprovados.html', {
        'turma': turma,
        'projetos': projetos,
        'projetos_na_revista': projetos_na_revista,
        'revista': revista,
    })
 
 
@login_required
def projeto_leitura_view(request, projeto_id):
    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()
 
    projeto = get_object_or_404(Projeto, id=projeto_id, status_projeto=2)
 
    return render(request, 'coordenador/projeto_leitura.html', {
        'projeto': projeto,
    })


@login_required
def pdf_resumo_view(request, projeto_id):

    if request.user.tipo_usuario == 1:
        projeto = get_object_or_404(Projeto, id=projeto_id, aluno=request.user)
    elif request.user.tipo_usuario == 2:
        projeto = get_object_or_404(Projeto, id=projeto_id, turma__responsavel=request.user)
    else:
        return HttpResponseForbidden()


    dados = {
        'document_type': 'resumo',
        'titulo_resumo': projeto.titulo_projeto,
        'autores': projeto.nome_autores,
        'disciplina': projeto.turma.disciplina,
        'pepict': ', '.join(p.nome for p in projeto.programa.all()),
        'objetivos': projeto.objetivos_trabalho,
        'metodologia': projeto.metodologia_projeto,
        'resultados': projeto.resultados_projeto,
        'ods': ', '.join(str(o) for o in projeto.ods.all()),
        'reflexao': projeto.reflexao_projeto,
        'referencias': projeto.referencia_projeto or '',
    }

    try:
        pdf_gerado = to_pdf(dados)

        if os.path.exists(pdf_gerado):
            response = FileResponse(open(pdf_gerado, 'rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="resumo_{projeto.id}.pdf"'
            os.remove(pdf_gerado)
            return response

        messages.error(request, "O arquivo PDF não foi encontrado.")

    except Exception as e:
        messages.error(request, f"Erro ao gerar o PDF: {str(e)}")

 
    return redirect(request.META.get('HTTP_REFERER', 'dashboard_aluno'))


def gera_capitulos(revista_id): 

    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'arquivos_temp')
    os.makedirs(temp_dir, exist_ok=True)

    caminho_temp_capitulos = os.path.join(temp_dir, "conteudo_revista.txt")

    revista = get_object_or_404(Revista, pk=revista_id)

    # Limpa o arquivo no início (começa do zero)
    with open(caminho_temp_capitulos, "w", encoding="utf-8") as arquivo:
        arquivo.write("")

    turmas = Turma.objects.filter(semestre=revista.semestre)

    for turma in turmas:

        
        with open(caminho_temp_capitulos, "a", encoding="utf-8") as arquivo:
            arquivo.write(fr"\chapter{{{turma.disciplina}}}" + "\n\n")

        
        projetos = Projeto.objects.filter(turma=turma)

        
        for projeto in projetos:

            programas_vinculados = ", ".join([p.nome for p in projeto.programa.all()])

            with open(caminho_temp_capitulos, "a", encoding="utf-8") as arquivo:
                arquivo.write(fr"\newpage" + "\n")
                arquivo.write(fr"\section{{{projeto.titulo_projeto}}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Autores}}" + "\n" + f"{projeto.nome_autores}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Disciplina e Curso}}" + "\n" + f"{turma.curso}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Programa PEPICT vinculado}}" + "\n" + f"{programas_vinculados}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Objetivos}}" + "\n" + f"{projeto.objetivos_trabalho}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")
            
                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Metodologia}}" + "\n" + f"{projeto.metodologia_projeto}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Resultados e Produtos}}" + "\n" + f"{projeto.resultados_projeto}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Relação com os ODS}}" + "\n" + f"{projeto.justificativa_ods}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Reflexão Crítica}}" + "\n" + f"{projeto.reflexao_projeto}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

                arquivo.write(fr"\noindent" + "\n")
                arquivo.write(fr"\textbf{{Referências}}" + "\n" + f"{projeto.referencia_projeto}" + "\n\n")
                arquivo.write(fr"\vspace{{0.7cm}}" + "\n")

@login_required
def gera_revista_view(request, revista_id):
    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()

    # Executa a escrita sequencial no arquivo txt
    gera_capitulos(revista_id)
    
    revista = get_object_or_404(Revista, pk=revista_id)
    data_formatada = revista.data_criacao.strftime('%Y')

    dados = {
        'document_type': 'revista',
        'titulo_revista': revista.titulo,
        'data': data_formatada,
    }

    try:
        pdf_gerado = to_pdf(dados)

        if os.path.exists(pdf_gerado):
            response = FileResponse(open(pdf_gerado, 'rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="resumo_{revista.id}.pdf"'

            return response

        messages.error(request, "O arquivo PDF não foi encontrado.")

    except Exception as e:
        messages.error(request, f"Erro ao gerar o PDF: {str(e)}")

 
    return redirect(request.META.get('HTTP_REFERER', 'dashboard_coordenador'))

@login_required
def gerencia_tipo_usuario_view(request):

    if request.user.tipo_usuario != 3:
        return HttpResponseForbidden()

    form = BuscaUsuarioForm(request.GET or None)
    usuarios = Usuario.objects.none()    

    if form.is_valid() and form.cleaned_data.get('username'):
        username_busca = form.cleaned_data.get('username')

        usuarios = Usuario.objects.filter(
            username__icontains=username_busca,
            tipo_usuario__in=[1, 2]
        )

    if request.method == 'POST':
            usuario_id = request.POST.get('usuario_id')
            usuario_foco = get_object_or_404(Usuario, id=usuario_id)

            if usuario_foco.tipo_usuario == 1:
                usuario_foco.tipo_usuario = 2 
                menssagem = f"O usuário {usuario_foco.username} agora é Professor(a)."
            elif usuario_foco.tipo_usuario == 2:
                usuario_foco.tipo_usuario = 1 
                menssagem = f"O usuário {usuario_foco.username} agora é Aluno(a)."
            
            usuario_foco.save()
            messages.success(request, menssagem)
            
            
            return redirect(f"{request.path}?username={request.GET.get('username', '')}")

    return render(request, 'coordenador/gerenciar_usuarios.html', {
        'form': form,
        'usuarios': usuarios
    })
