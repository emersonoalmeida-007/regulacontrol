from django import forms
from django.contrib.auth import get_user_model

from .models import Licenca, Renovacao, Unidade


class DataInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class LicencaForm(forms.ModelForm):
    class Meta:
        model = Licenca
        fields = [
            "tipo", "unidade", "numero", "data_emissao", "data_validade",
            "responsavel", "arquivo", "observacoes", "ativa",
        ]
        widgets = {
            "data_emissao": DataInput(),
            "data_validade": DataInput(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
            "arquivo": forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = get_user_model().objects.filter(is_active=True).order_by("first_name")
        self.fields["responsavel"].label_from_instance = lambda u: u.get_full_name() or u.username

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        if arquivo and hasattr(arquivo, "name") and not arquivo.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Envie o documento em PDF.")
        return arquivo

    def clean(self):
        dados = super().clean()
        emissao, validade = dados.get("data_emissao"), dados.get("data_validade")
        if emissao and validade and validade < emissao:
            self.add_error("data_validade", "A validade não pode ser anterior à emissão.")
        return dados


class RenovacaoForm(forms.ModelForm):
    class Meta:
        model = Renovacao
        fields = ["nova_emissao", "nova_validade", "numero_protocolo", "observacao"]
        widgets = {
            "nova_emissao": DataInput(),
            "nova_validade": DataInput(),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dados = super().clean()
        emissao, validade = dados.get("nova_emissao"), dados.get("nova_validade")
        if emissao and validade and validade < emissao:
            self.add_error("nova_validade", "A validade não pode ser anterior à emissão.")
        return dados


class UnidadeForm(forms.ModelForm):
    # Aceita o CNPJ com ou sem máscara; a limpeza deixa só os 14 números.
    cnpj = forms.CharField(
        label="CNPJ",
        max_length=18,
        help_text="Digite o CNPJ e saia do campo para buscar os dados na BrasilAPI.",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )

    class Meta:
        model = Unidade
        fields = ["cnpj", "nome", "razao_social", "logradouro", "municipio", "uf"]

    def clean_cnpj(self):
        cnpj = "".join(ch for ch in self.cleaned_data["cnpj"] if ch.isdigit())
        if len(cnpj) != 14:
            raise forms.ValidationError("O CNPJ precisa ter 14 números.")
        return cnpj

    def clean_uf(self):
        return self.cleaned_data["uf"].upper()
