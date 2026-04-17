# Site do Carlos Corretor (Python + SQLite)

Projeto simples e rapido, mas completo, para site imobiliario com painel admin.

## Funcionalidades

- Site publico com:
  - Menu Empresa, Servicos e Imoveis
  - Busca e filtros de imoveis
  - Pagina de detalhes do imovel
  - Formularios: peca seu imovel, anuncie seu imovel, simule financiamento
- Painel admin com:
  - Login
  - Dashboard com metricas basicas
  - CRUD de imoveis
  - Gestao de leads (com status)
  - Edicao de conteudos institucionais
  - Configuracoes de contato e SEO basico
  - Usuarios e permissoes (admin/editor)
  - Logs de atividades

## Stack

- Python (Flask)
- SQLite
- Bootstrap (CDN)

## Como rodar localmente

1. Crie e ative um ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Rode o projeto (porta 5000 local):

```bash
set PORT=5000
python app.py
```

4. Abra no navegador:

- Site: `http://127.0.0.1:5000`
- Admin: `http://127.0.0.1:5000/admin/login`

## Deploy na Square Cloud

Configuracao recomendada:

- Host: `0.0.0.0`
- Port: `80` (via variavel de ambiente `PORT=80`)
- Comando de inicializacao: `python app.py`

Variaveis de ambiente:

- `HOST=0.0.0.0`
- `PORT=80`
- `FLASK_DEBUG=0`

## Login inicial do admin

- E-mail: `admin@local`
- Senha: `admin123`

Altere a senha depois de entrar.
