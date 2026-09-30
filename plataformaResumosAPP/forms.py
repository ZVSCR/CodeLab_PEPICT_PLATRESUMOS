from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Turma, Programa, Projeto, ODS

Usuario = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(
        label='Usuário (ou E-mail)',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Seu usuário ou e-mail'
        })
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sua senha'
        })
    )


class UsuarioCreationForm(UserCreationForm):

    class Meta:
        model = Usuario
        fields = ('username', 'email', 'first_name', 'last_name', 'ra')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in ['username', 'email', 'first_name', 'last_name', 'ra', 'password1', 'password2']:
            self.fields[field_name].widget.attrs.update({
                'class': 'form-control'
            })

    def save(self, commit=True):
        user = super().save(commit=False)

        user.tipo_usuario = 1

        if commit:
            user.save()

        return user
    

class InscricaoEmTurma(forms.Form):
    codigo_acesso = forms.CharField(
        max_length=20,
        label="Código de acesso"
    )
    
class CriacaoTurma(forms.ModelForm):

    class Meta:

        model = Turma

        fields = (
            'nome_turma',
            'disciplina',
            'curso',
        )

        labels = {
            'nome_turma': 'Nome da Turma',
            'disciplina': 'Unidade Curricular',
            'curso': 'Curso Graduação',
        }

        widgets = {

            'nome_turma': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'disciplina': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'curso': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

        }

class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = [
            'titulo_projeto', 'programa', 'ods', 'nome_autores', 
            'objetivos_trabalho', 'metodologia_projeto', 'resultados_projeto', 
            'justificativa_ods', 'reflexao_projeto', 'referencia_projeto'
        ]
        widgets = {
  
            'programa': forms.CheckboxSelectMultiple(),
            'ods': forms.CheckboxSelectMultiple(),
            
            'objetivos_trabalho': forms.Textarea(attrs={'rows': 3}),
            'metodologia_projeto': forms.Textarea(attrs={'rows': 3}),
            'resultados_projeto': forms.Textarea(attrs={'rows': 3}),
            'justificativa_ods': forms.Textarea(attrs={'rows': 3}),
            'reflexao_projeto': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_ods(self):
        ods_selecionadas = self.cleaned_data.get('ods')
        quantidade = ods_selecionadas.count()
        
        if quantidade < 1 or quantidade > 3:
            raise forms.ValidationError("Você deve selecionar entre 1 e 3 ODS.")
        return ods_selecionadas
    
class BuscaUsuarioForm(forms.Form):
    username = forms.CharField(
        label='Buscar por nome de usuário',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite o username...'
        })
    )