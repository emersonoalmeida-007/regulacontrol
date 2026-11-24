# RegulaControl

Sistema web de gestão de licenças e documentos regulatórios, com alertas de vencimento e painel de conformidade.
Projeto Integrador em Computação II (PJI240) – UNIVESP, 2027.1.

## O que o sistema faz

- Cadastro de unidades com preenchimento automático pelo CNPJ (BrasilAPI)
- Cadastro de licenças com upload do PDF e status automático: vigente, vence em até 90/60/30 dias, vencida
- Lista com busca e filtros sem recarregar a página, e exportação em CSV
- Registro de renovação com histórico
- Alerta diário por e-mail para cada responsável, com antecedência configurável por licença
- Controle de custos: valor e periodicidade (mensal, semestral, anual) de cada licença e porte da empresa
- Relatório gerencial de custos: custo anual, fluxo de pagamentos de 12 meses, agrupamentos por unidade, órgão, porte e periodicidade, com exportação em CSV e impressão
- API de custos: `/api/custos/`
- Painel de conformidade com indicadores e gráficos
- API REST: `/api/licencas/` e `/api/resumo/`
- Perfis de acesso: Administrador, Analista e Consulta

## Como cada requisito do PI é atendido

| Requisito | Onde está |
| --- | --- |
| Framework web | Django 5 (`config/`, `licencas/`) |
| Banco de dados | Modelos em `licencas/models.py`; SQLite local, PostgreSQL na nuvem |
| JavaScript | `static/js/filtros.js`, `cnpj.js`, `painel.js` (Chart.js) |
| Nuvem | `render.yaml` e `build.sh` |
| API | Consumo: `licencas/brasilapi.py` · Própria: `licencas/api.py` |
| Acessibilidade | Templates com HTML semântico, rótulos, foco visível, link "pular para o conteúdo", status com ícone + texto, tabelas alternativas aos gráficos |
| Controle de versão | Git + GitHub |
| Testes | `licencas/tests.py` (27 testes) + `.github/workflows/testes.yml` |
| Análise de dados | `licencas/consultas.py` + painel |

## Rodar no computador

Pré-requisito: Python 3.12 ou mais recente.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py carregar_demo
python manage.py runserver
```

Abra http://127.0.0.1:8000 e entre com um dos usuários de demonstração. Todos usam a senha `demo12345`:

| Usuário | Perfil | Pode |
| --- | --- | --- |
| `admin` | Administrador | Tudo, inclusive /admin |
| `analista` | Analista | Cadastrar, editar e renovar |
| `consulta` | Consulta | Somente visualizar |

Os dados de demonstração são **fictícios**. Não cadastre dados reais sem autorização da organização parceira (LGPD).

## Comandos úteis

```powershell
python manage.py test                     # roda os testes
python manage.py enviar_alertas --simular # quantos e-mails seriam enviados hoje
python manage.py enviar_alertas           # envia (no desenvolvimento, aparecem no terminal)
```

## Publicar no Render

1. Suba o código para um repositório no GitHub.
2. No Render, escolha **New > Blueprint** e selecione o repositório. O `render.yaml` cria o banco PostgreSQL e o serviço web.
3. Depois do deploy, abra o **Shell** do serviço e rode `python manage.py createsuperuser` (ou `carregar_demo` para a apresentação).
4. O alerta diário roda pelo GitHub Actions (`.github/workflows/alertas.yml`). Cadastre os *secrets* listados no topo desse arquivo.

## Estrutura

```
config/            configurações e rotas principais
licencas/
  models.py        tabelas e regra de status (calcular_status)
  consultas.py     filtros e indicadores do painel
  views.py         telas
  api.py           API REST
  brasilapi.py     consumo da BrasilAPI
  alertas.py       e-mails de vencimento
  tests.py         testes automatizados
templates/         base e login
static/            CSS e JavaScript
```
