from django.db import models
from django.contrib.auth.models import AbstractUser



class Usuario(AbstractUser):

    TIPOS_USUARIO = (
        (1, 'Aluno'),
        (2, 'Professor'),
        (3, 'Coordenador'),
    )

    tipo_usuario = models.IntegerField(
        choices=TIPOS_USUARIO,
        default=1
    )

    ra = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.username



class Semestre(models.Model):

    ano = models.IntegerField()

    semestre = models.IntegerField(
        choices=(
            (1, '1º Semestre'),
            (2, '2º Semestre'),
        )
    )

    coordenador = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='semestres_coordenados',
        limit_choices_to={'tipo_usuario': 3}
    )

    class Meta:
        unique_together = ('ano', 'semestre')

    def __str__(self):
        return f'{self.ano}/{self.semestre}'


class Programa(models.Model):

    nome = models.CharField(
        max_length=255,
        unique=True
    )

    def __str__(self):
        return self.nome


class ODS(models.Model):

    numero = models.IntegerField(
        unique=True
    )

    nome = models.CharField(
        max_length=255
    )

    def __str__(self):
        return f'ODS {self.numero} - {self.nome}'



class Turma(models.Model):

    responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='turmas_responsavel',
        limit_choices_to={'tipo_usuario': 2}
    )

    semestre = models.ForeignKey(
        Semestre,
        on_delete=models.PROTECT,
        related_name='turmas'
    )

    nome_turma = models.CharField(
        max_length=100
    )

    codigo_acesso = models.CharField(
        max_length=20,
        unique=True
    )

    disciplina = models.CharField(
        max_length=255
    )

    curso = models.CharField(
        max_length=255
    )

    def __str__(self):
        return f'{self.nome_turma} - {self.disciplina} ({self.semestre})'



class Inscricao(models.Model):

    aluno = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='inscricoes',
        limit_choices_to={'tipo_usuario': 1}
    )

    turma = models.ForeignKey(
        Turma,
        on_delete=models.CASCADE,
        related_name='inscricoes'
    )

    data_inscricao = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        unique_together = (
            'aluno',
            'turma'
        )

    def __str__(self):
        return f'{self.aluno} - {self.turma}'


class Projeto(models.Model):
    STATUS = (
        (0, 'Rascunho'),
        (1, 'Em análise'),
        (2, 'Aprovado'),
        (3, 'Rejeitado'),
    )

    aluno = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='projetos',
        limit_choices_to={'tipo_usuario': 1}
    )
    turma = models.ForeignKey(
        Turma,
        on_delete=models.CASCADE,
        related_name='projetos'
    )

    programa = models.ManyToManyField(
        Programa,
        related_name='projetos'
    )

    ods = models.ManyToManyField(
        ODS,
        related_name='projetos'
    )

    titulo_projeto = models.CharField(max_length=255)
    nome_autores = models.TextField()
    objetivos_trabalho = models.TextField()
    metodologia_projeto = models.TextField()
    resultados_projeto = models.TextField()
    justificativa_ods = models.TextField()
    reflexao_projeto = models.TextField()
    referencia_projeto = models.TextField(null=True, blank=True)
    
    status_projeto = models.IntegerField(
        choices=STATUS,
        default=0
    )

    class Meta:
        unique_together = ('aluno', 'turma')

    def __str__(self):
        return self.titulo_projeto


class Submissao(models.Model):

    RESULTADOS = (
        (0, 'Em análise'),
        (1, 'Aprovado'),
        (2, 'Rejeitado'),
    )

    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='submissoes'
    )

    resultado_submissao = models.IntegerField(
        choices=RESULTADOS,
        default=0
    )

    feedback = models.TextField(
        null=True,
        blank=True
    )

    data_submissao = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f'Submissão #{self.id}'



class Revista(models.Model):

    titulo = models.CharField(
        max_length=255
    )

    semestre = models.OneToOneField(
        Semestre,
        on_delete=models.CASCADE,
        related_name='revista'
    )

    data_criacao = models.DateTimeField(
        auto_now_add=True
    )

    # Conteúdo editável pelo coordenador. Todos opcionais (default '') para
    # as revistas que já existem no banco continuarem válidas.
    introducao = models.TextField(blank=True, default='')

    # Expediente ("Informações da publicação"): um nome por linha
    coordenador_geral = models.TextField(blank=True, default='')
    coordenador_editorial = models.TextField(blank=True, default='')
    comissao = models.TextField(blank=True, default='')
    revisao = models.TextField(blank=True, default='')
    diagramacao = models.TextField(blank=True, default='')
    organizadores = models.TextField(blank=True, default='')

    # Usados no PDF quando o coordenador deixa o campo em branco
    def introducao_padrao(self):
        return (
            'Este caderno reúne os resumos estruturados dos projetos desenvolvidos nas '
            f'disciplinas vinculadas ao Programa PEPICT no semestre {self.semestre}.'
        )

    def coordenador_geral_padrao(self):
        coordenador = self.semestre.coordenador
        return coordenador.get_full_name() or coordenador.username

    def __str__(self):
        return f'{self.titulo} - {self.semestre}'


class ProjetoRevista(models.Model):

    revista = models.ForeignKey(
        Revista,
        on_delete=models.CASCADE,
        related_name='projetos_revista'
    )

    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.CASCADE,
        related_name='revistas'
    )

    class Meta:
        unique_together = (
            'revista',
            'projeto'
        )

    def __str__(self):
        return f'{self.projeto} na {self.revista}'