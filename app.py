import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.sqlite3")
DEV_WHATSAPP_NUMBER = "5581991498930"
LOGO_FILENAME = "ChatGPT Image 22 de fev. de 2026, 10_23_07.png"
SECOES_IMOVEIS = ["Residencial", "Comercial", "Terrenos & Rurais"]

app = Flask(__name__)
app.config["SECRET_KEY"] = "troque-esta-chave-em-producao"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def log_action(user_id, action):
    db = get_db()
    db.execute(
        "INSERT INTO activity_logs (user_id, action, created_at) VALUES (?, ?, ?)",
        (user_id, action, datetime.now().isoformat()),
    )
    db.commit()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def execute(sql, params=()):
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Acesso permitido apenas para administradores.", "warning")
            return redirect(url_for("admin_dashboard"))
        return view(*args, **kwargs)

    return wrapped


@app.template_filter("brl")
def brl(value):
    if value is None:
        return "R$ 0,00"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def get_content(key, default=""):
    row = query_one("SELECT value FROM contents WHERE key = ?", (key,))
    return row["value"] if row else default


def get_setting(key, default=""):
    row = query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def build_whatsapp_url(raw_value, message):
    raw = (raw_value or "").strip()
    if not raw:
        return ""

    if "wa.me/" in raw:
        phone_candidate = raw.split("wa.me/")[-1].split("?")[0]
    else:
        phone_candidate = raw
    phone = re.sub(r"\D", "", phone_candidate)

    if not phone:
        return ""
    return f"https://wa.me/{phone}?text={quote(message)}"


def build_property_whatsapp_message(imovel):
    return (
        "Olá Carlos Câmara, tenho interesse neste imóvel:\n"
        f"Ref: #{imovel['id']}\n"
        f"Imóvel: {imovel['titulo']}\n"
        f"Localização: {imovel['localizacao']}\n"
        f"Valor: {brl(imovel['preco'])}\n"
        "Pode me passar mais informações?"
    )


def get_location_options():
    rows = query_all(
        """
        SELECT localizacao, estado
        FROM imoveis
        WHERE ativo = 1
        """
    )
    cidades = set()
    estados = set()
    for row in rows:
        local = (row["localizacao"] or "").strip()
        estado_row = (row["estado"] or "").strip().upper()
        if estado_row:
            estados.add(estado_row)
        if not local:
            continue
        if " - " in local:
            cidade, estado = local.rsplit(" - ", 1)
            cidade = cidade.strip()
            estado = estado.strip().upper()
            if cidade:
                cidades.add(cidade)
            if estado and not estado_row:
                estados.add(estado)
        else:
            cidades.add(local)
    return sorted(cidades), sorted(estados)


@app.context_processor
def inject_globals():
    return {
        "site_nome": get_setting("site_nome", "Carlos Câmara"),
        "creci": get_setting("creci", "CRECI 13107"),
        "telefone": get_setting("telefone", "81 996086470"),
        "telefone_secundario": get_setting("telefone_secundario", "81 992333407"),
        "email_contato": get_setting("email_contato", "clcamara@creci.org.br"),
        "whatsapp": get_setting("whatsapp", ""),
        "instagram": get_setting("instagram", ""),
        "facebook": get_setting("facebook", ""),
    }


@app.get("/logo-carlos")
def logo_carlos():
    logo_path = os.path.join(BASE_DIR, LOGO_FILENAME)
    if not os.path.exists(logo_path):
        abort(404)
    return send_file(logo_path)


def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'editor',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS imoveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            localizacao TEXT NOT NULL,
            estado TEXT,
            secao TEXT NOT NULL DEFAULT 'Residencial',
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL DEFAULT 0,
            area REAL NOT NULL DEFAULT 0,
            dormitorios INTEGER NOT NULL DEFAULT 0,
            banheiros INTEGER NOT NULL DEFAULT 0,
            vagas INTEGER NOT NULL DEFAULT 0,
            suites INTEGER NOT NULL DEFAULT 0,
            caracteristicas TEXT,
            tour360_url TEXT,
            fotos TEXT,
            destaque INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            visualizacoes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            nome TEXT NOT NULL,
            email TEXT,
            telefone TEXT,
            mensagem TEXT,
            imovel_interesse TEXT,
            status TEXT NOT NULL DEFAULT 'novo',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contents (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """
    )

    # Migracao simples para bases antigas.
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(imoveis)").fetchall()
    }
    if "estado" not in existing_columns:
        cursor.execute("ALTER TABLE imoveis ADD COLUMN estado TEXT")
    if "secao" not in existing_columns:
        cursor.execute("ALTER TABLE imoveis ADD COLUMN secao TEXT NOT NULL DEFAULT 'Residencial'")

    # Backfill de estado e secao para manter tudo organizado.
    imoveis_existentes = cursor.execute(
        "SELECT id, localizacao, tipo, secao, estado FROM imoveis"
    ).fetchall()
    for item in imoveis_existentes:
        estado = (item[4] or "").strip().upper()
        secao = (item[3] or "").strip()
        local = (item[1] or "").strip()
        tipo = (item[2] or "").strip().lower()

        if not estado and " - " in local:
            estado = local.rsplit(" - ", 1)[1].strip().upper()
        if not secao:
            if tipo in {"comercial", "sala comercial", "galpao", "loja"}:
                secao = "Comercial"
            elif tipo in {"terreno", "sitio", "chacara", "fazenda", "rural"}:
                secao = "Terrenos & Rurais"
            else:
                secao = "Residencial"

        cursor.execute(
            "UPDATE imoveis SET estado = ?, secao = ? WHERE id = ?",
            (estado, secao, item[0]),
        )

    admin_user = cursor.execute("SELECT id FROM users WHERE email = ?", ("admin@local",)).fetchone()
    if not admin_user:
        cursor.execute(
            """
            INSERT INTO users (nome, email, senha_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Administrador",
                "admin@local",
                generate_password_hash("admin123"),
                "admin",
                datetime.now().isoformat(),
            ),
        )

    default_contents = {
        "quem_somos": "Carlos Camara e corretor e consultor imobiliario, com atuacao focada em atendimento consultivo e resultado para quem compra ou anuncia. O trabalho combina conhecimento de mercado, avaliacao realista, estrategia de divulgacao e acompanhamento completo de cada etapa, do primeiro contato ate o fechamento. A prioridade e oferecer transparencia, comunicacao clara e agilidade para que cada cliente tome decisoes seguras com suporte profissional e humano.",
        "politica_privacidade": "Politica de Privacidade\n\n1. Dados coletados: coletamos apenas os dados informados voluntariamente em formularios e contatos, como nome, telefone, e-mail e mensagem.\n\n2. Finalidade de uso: utilizamos esses dados para atendimento comercial, retorno de solicitacoes, envio de informacoes sobre imoveis e acompanhamento de negociações.\n\n3. Compartilhamento: nao vendemos dados pessoais. O compartilhamento pode ocorrer somente quando necessario para viabilizar servicos relacionados a negociacao imobiliaria, sempre com responsabilidade e sigilo.\n\n4. Armazenamento e seguranca: adotamos medidas tecnicas e administrativas para proteger os dados contra acesso indevido, perda ou uso nao autorizado.\n\n5. Direitos do titular: o cliente pode solicitar atualizacao, correcao ou exclusao de dados de contato a qualquer momento pelos canais oficiais.\n\n6. Cookies e navegacao: podemos utilizar recursos tecnicos de navegacao para melhorar a experiencia no site e medir desempenho de paginas.\n\n7. Contato: para qualquer solicitacao sobre privacidade e tratamento de dados, entre em contato pelos canais exibidos no site.\n\nAo utilizar este site, voce concorda com os termos desta politica.",
        "servico_comprar_imovel": "Encontre as melhores opcoes para comprar seu imovel com suporte completo.",
        "servico_anuncie_imovel": "Anuncie seu imovel conosco e alcance compradores qualificados.",
    }
    for key, value in default_contents.items():
        cursor.execute(
            "INSERT OR IGNORE INTO contents (key, value) VALUES (?, ?)",
            (key, value),
        )

    default_settings = {
        "site_nome": "Carlos Câmara",
        "creci": "CRECI 13107",
        "telefone": "81 996086470",
        "telefone_secundario": "81 992333407",
        "email_contato": "clcamara@creci.org.br",
        "whatsapp": "https://wa.me/5581996086470",
        "instagram": "",
        "facebook": "",
        "endereco": "Sao Paulo - SP",
        "seo_title": "Carlos Câmara - Imóveis",
        "seo_description": "Carlos Camara, corretor e consultor imobiliario. Compra e anuncio de imoveis com atendimento especializado.",
    }
    for key, value in default_settings.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    # Atualiza instalacoes que nasceram com a marca antiga.
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'site_nome' AND value = ?",
        ("Carlos Corretor", "Rogério Corretor"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'email_contato' AND value = ?",
        ("contato@carloscorretor.com", "contato@rogeriocorretor.com"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'seo_title' AND value = ?",
        ("Carlos Corretor - Imoveis", "Rogério Corretor - Imoveis"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'site_nome' AND value = ?",
        ("Carlos Câmara", "Carlos Corretor"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'email_contato' AND value = ?",
        ("clcamara@creci.org.br", "contato@carloscorretor.com"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'seo_title' AND value = ?",
        ("Carlos Câmara - Imóveis", "Carlos Corretor - Imoveis"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'site_nome' AND value = ?",
        ("Carlos Câmara", "Carlos CÃ¢mara"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'site_nome' AND value = ?",
        ("Carlos Câmara", "Carlos âmara"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'seo_title' AND value = ?",
        ("Carlos Câmara - Imóveis", "Carlos CÃ¢mara - Imóveis"),
    )
    cursor.execute(
        "UPDATE settings SET value = ? WHERE key = 'seo_title' AND value = ?",
        ("Carlos Câmara - Imóveis", "Carlos âmara - Imóveis"),
    )

    sample_imovel = cursor.execute("SELECT id FROM imoveis LIMIT 1").fetchone()
    if not sample_imovel:
        now = datetime.now().isoformat()
        cursor.execute(
            """
            INSERT INTO imoveis (
                titulo, descricao, localizacao, estado, secao, tipo, categoria, preco, area,
                dormitorios, banheiros, vagas, suites, caracteristicas, tour360_url,
                fotos, destaque, ativo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Apartamento moderno com varanda",
                "Imovel em excelente estado, com acabamento premium e lazer completo.",
                "Sao Paulo - SP",
                "SP",
                "Residencial",
                "Apartamento",
                "para Comprar",
                650000,
                78,
                2,
                2,
                1,
                1,
                "Piscina,Varanda gourmet,Academia",
                "",
                "https://images.unsplash.com/photo-1560185007-c5ca9d2c014d",
                1,
                1,
                now,
                now,
            ),
        )

    db.commit()
    db.close()


@app.route("/")
def home():
    secoes_home = {}
    for secao in SECOES_IMOVEIS:
        secoes_home[secao] = query_all(
            """
            SELECT * FROM imoveis
            WHERE ativo = 1 AND secao = ?
            ORDER BY destaque DESC, id DESC
            LIMIT 8
            """,
            (secao,),
        )
    imoveis_para_contato = query_all(
        "SELECT id, titulo, localizacao, preco FROM imoveis WHERE ativo = 1 ORDER BY id DESC"
    )
    cidades, estados = get_location_options()
    return render_template(
        "public/home.html",
        secoes_home=secoes_home,
        imoveis_para_contato=imoveis_para_contato,
        cidades=cidades,
        estados=estados,
    )


@app.get("/quero-um-site-assim")
def quero_um_site_assim():
    texto = (
        "Ola! Vi o site do Carlos Câmara e gostei muito do resultado. "
        "Quero fazer um orçamento para criar um site profissional para o meu negocio, "
        "com design premium e foco em conversao. "
        "Pode me enviar valores, prazo e como funciona o processo?"
    )
    whatsapp_url = build_whatsapp_url(DEV_WHATSAPP_NUMBER, texto)
    if whatsapp_url:
        return redirect(whatsapp_url)
    flash("WhatsApp nao configurado no painel.", "warning")
    return redirect(url_for("home"))


@app.route("/imoveis")
def imoveis():
    visual = request.args.get("visual", "carrossel")
    if visual not in {"carrossel", "lista"}:
        visual = "carrossel"

    filters = []
    params = []

    cidade = request.args.get("cidade", "").strip()
    if cidade:
        filters.append("UPPER(localizacao) LIKE ?")
        params.append(f"{cidade.upper()}%")

    estado = request.args.get("estado", "").strip().upper()
    if estado:
        filters.append("UPPER(COALESCE(estado, '')) = ?")
        params.append(estado)

    secao = request.args.get("secao", "").strip()
    if secao in SECOES_IMOVEIS:
        filters.append("secao = ?")
        params.append(secao)

    text_filters = {
        "localizacao": "localizacao LIKE ?",
        "tipo": "tipo = ?",
        "categoria": "categoria = ?",
    }
    for field, sql in text_filters.items():
        value = request.args.get(field, "").strip()
        if value:
            filters.append(sql)
            params.append(f"%{value}%") if "LIKE" in sql else params.append(value)

    numeric_filters = {
        "preco_min": ("preco >= ?", float),
        "preco_max": ("preco <= ?", float),
        "area_min": ("area >= ?", float),
        "dormitorios": ("dormitorios >= ?", int),
        "banheiros": ("banheiros >= ?", int),
        "vagas": ("vagas >= ?", int),
        "suites": ("suites >= ?", int),
    }
    for field, (sql, cast) in numeric_filters.items():
        value = request.args.get(field, "").strip()
        if value:
            try:
                filters.append(sql)
                params.append(cast(value))
            except ValueError:
                pass

    caracteristica = request.args.get("caracteristica", "").strip()
    if caracteristica:
        filters.append("caracteristicas LIKE ?")
        params.append(f"%{caracteristica}%")

    base_query = "SELECT * FROM imoveis WHERE ativo = 1"
    if filters:
        base_query += " AND " + " AND ".join(filters)
    base_query += " ORDER BY id DESC"

    items = query_all(base_query, tuple(params))
    whatsapp_base = get_setting("whatsapp", "")
    imoveis_with_links = []
    for item in items:
        row = dict(item)
        row["whatsapp_link"] = build_whatsapp_url(
            whatsapp_base,
            build_property_whatsapp_message(item),
        )
        imoveis_with_links.append(row)
    cidades, estados = get_location_options()
    return render_template(
        "public/imoveis.html",
        imoveis=imoveis_with_links,
        visual=visual,
        cidades=cidades,
        estados=estados,
        secoes=SECOES_IMOVEIS,
    )


@app.route("/imovel/<int:imovel_id>")
def imovel_detalhe(imovel_id):
    imovel = query_one("SELECT * FROM imoveis WHERE id = ? AND ativo = 1", (imovel_id,))
    if not imovel:
        flash("Imovel nao encontrado.", "warning")
        return redirect(url_for("imoveis"))

    execute(
        "UPDATE imoveis SET visualizacoes = visualizacoes + 1 WHERE id = ?",
        (imovel_id,),
    )
    whatsapp_link = build_whatsapp_url(
        get_setting("whatsapp", ""),
        build_property_whatsapp_message(imovel),
    )
    return render_template("public/imovel_detalhe.html", imovel=imovel, whatsapp_link=whatsapp_link)


@app.route("/empresa/<slug>")
def pagina_empresa(slug):
    map_keys = {
        "quem-somos": ("Quem somos", "quem_somos"),
        "politica-de-privacidade": ("Politica de Privacidade", "politica_privacidade"),
    }
    page = map_keys.get(slug)
    if not page:
        flash("Pagina nao encontrada.", "warning")
        return redirect(url_for("home"))

    titulo, key = page
    conteudo = get_content(key, "")
    return render_template("public/pagina.html", titulo=titulo, conteudo=conteudo)


@app.route("/servico/<slug>")
def servico(slug):
    map_keys = {
        "comprar-imovel": ("Comprar imovel", "servico_comprar_imovel"),
        "anuncie-seu-imovel": ("Anuncie seu imovel", "servico_anuncie_imovel"),
    }
    page = map_keys.get(slug)
    if not page:
        flash("Servico nao encontrado.", "warning")
        return redirect(url_for("home"))

    titulo, key = page
    conteudo = get_content(key, "")
    return render_template("public/servico.html", titulo=titulo, conteudo=conteudo, slug=slug)


@app.post("/lead")
def salvar_lead():
    tipo = request.form.get("tipo", "geral")
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("Nome e obrigatorio para enviar.", "danger")
        return redirect(request.referrer or url_for("home"))

    email = request.form.get("email", "").strip()
    telefone = request.form.get("telefone", "").strip()
    mensagem = request.form.get("mensagem", "").strip()
    imovel_interesse = request.form.get("imovel_interesse", "").strip()
    imovel_id = request.form.get("imovel_id", "").strip()
    imovel_referencia = ""
    if imovel_id:
        try:
            imovel = query_one("SELECT id, titulo FROM imoveis WHERE id = ?", (int(imovel_id),))
            if imovel:
                imovel_referencia = f"#{imovel['id']} - {imovel['titulo']}"
        except ValueError:
            imovel_referencia = ""

    if imovel_referencia:
        if imovel_interesse:
            imovel_interesse = f"{imovel_interesse} | Ref. {imovel_referencia}"
        else:
            imovel_interesse = f"Ref. {imovel_referencia}"

    execute(
        """
        INSERT INTO leads (tipo, nome, email, telefone, mensagem, imovel_interesse, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tipo,
            nome,
            email,
            telefone,
            mensagem,
            imovel_interesse,
            "novo",
            datetime.now().isoformat(),
        ),
    )

    tipo_label = {
        "anuncie_seu_imovel": "Anuncie seu imovel",
        "comprar_imovel": "Comprar imovel",
        "quero_site_assim": "Quero um site assim",
    }.get(tipo, "Contato geral")

    texto = (
        f"Olá Carlos Câmara, tudo bem?%0A"
        f"Tenho interesse em: {tipo_label}%0A"
        f"Nome: {nome}%0A"
        f"Telefone: {telefone or '-'}%0A"
        f"E-mail: {email or '-'}%0A"
        f"Imóvel selecionado: {imovel_referencia or '-'}%0A"
        f"Tipo do imóvel: {imovel_interesse or '-'}%0A"
        f"Mensagem: {mensagem or '-'}"
    ).replace("%0A", "\n")

    whatsapp_destino = get_setting("whatsapp", "")
    if tipo == "quero_site_assim":
        texto = (
            "Ola! Vi o site do Carlos Câmara e quero fazer um orçamento para um projeto parecido.\n"
            f"Nome: {nome}\n"
            f"Telefone: {telefone or '-'}\n"
            f"E-mail: {email or '-'}\n"
            "Quero entender valores, prazo de entrega e etapas do desenvolvimento."
        )
        whatsapp_destino = DEV_WHATSAPP_NUMBER

    whatsapp_url = build_whatsapp_url(whatsapp_destino, texto)
    if whatsapp_url:
        return redirect(whatsapp_url)

    flash("Lead enviado, mas o WhatsApp nao esta configurado no painel.", "warning")
    return redirect(request.referrer or url_for("home"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        user = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if user and check_password_hash(user["senha_hash"], senha):
            session["user_id"] = user["id"]
            session["user_nome"] = user["nome"]
            session["role"] = user["role"]
            log_action(user["id"], "Login no painel")
            flash("Bem-vindo ao painel.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Credenciais invalidas.", "danger")
    return render_template("admin/login.html")


@app.route("/admin/logout")
@login_required
def admin_logout():
    log_action(session.get("user_id"), "Logout no painel")
    session.clear()
    flash("Sessao encerrada.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    total_imoveis = query_one("SELECT COUNT(*) AS total FROM imoveis")["total"]
    total_leads = query_one("SELECT COUNT(*) AS total FROM leads")["total"]
    novos_leads = query_one("SELECT COUNT(*) AS total FROM leads WHERE status = 'novo'")["total"]
    top_imoveis = query_all(
        "SELECT titulo, visualizacoes FROM imoveis ORDER BY visualizacoes DESC LIMIT 5"
    )
    ultimos_leads = query_all("SELECT * FROM leads ORDER BY id DESC LIMIT 5")
    return render_template(
        "admin/dashboard.html",
        total_imoveis=total_imoveis,
        total_leads=total_leads,
        novos_leads=novos_leads,
        top_imoveis=top_imoveis,
        ultimos_leads=ultimos_leads,
    )


@app.route("/admin/imoveis")
@login_required
def admin_imoveis():
    items = query_all("SELECT * FROM imoveis ORDER BY id DESC")
    return render_template("admin/imoveis_list.html", imoveis=items)


def parse_imovel_form():
    secao = request.form.get("secao", "Residencial").strip()
    if secao not in SECOES_IMOVEIS:
        secao = "Residencial"
    return {
        "titulo": request.form.get("titulo", "").strip(),
        "descricao": request.form.get("descricao", "").strip(),
        "localizacao": request.form.get("localizacao", "").strip(),
        "estado": request.form.get("estado", "").strip().upper()[:2],
        "secao": secao,
        "tipo": request.form.get("tipo", "").strip(),
        "categoria": request.form.get("categoria", "").strip(),
        "preco": float(request.form.get("preco", "0") or 0),
        "area": float(request.form.get("area", "0") or 0),
        "dormitorios": int(request.form.get("dormitorios", "0") or 0),
        "banheiros": int(request.form.get("banheiros", "0") or 0),
        "vagas": int(request.form.get("vagas", "0") or 0),
        "suites": int(request.form.get("suites", "0") or 0),
        "caracteristicas": request.form.get("caracteristicas", "").strip(),
        "tour360_url": request.form.get("tour360_url", "").strip(),
        "fotos": request.form.get("fotos", "").strip(),
        "destaque": 1 if request.form.get("destaque") == "on" else 0,
        "ativo": 1 if request.form.get("ativo") == "on" else 0,
    }


@app.route("/admin/imoveis/novo", methods=["GET", "POST"])
@login_required
def admin_imovel_novo():
    if request.method == "POST":
        data = parse_imovel_form()
        if not data["titulo"] or not data["localizacao"] or not data["tipo"] or not data["categoria"]:
            flash("Preencha os campos obrigatorios.", "danger")
            return render_template(
                "admin/imovel_form.html",
                imovel=data,
                modo="novo",
                secoes=SECOES_IMOVEIS,
            )

        now = datetime.now().isoformat()
        execute(
            """
            INSERT INTO imoveis (
                titulo, descricao, localizacao, estado, secao, tipo, categoria, preco, area,
                dormitorios, banheiros, vagas, suites, caracteristicas, tour360_url,
                fotos, destaque, ativo, visualizacoes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["titulo"],
                data["descricao"],
                data["localizacao"],
                data["estado"],
                data["secao"],
                data["tipo"],
                data["categoria"],
                data["preco"],
                data["area"],
                data["dormitorios"],
                data["banheiros"],
                data["vagas"],
                data["suites"],
                data["caracteristicas"],
                data["tour360_url"],
                data["fotos"],
                data["destaque"],
                data["ativo"],
                0,
                now,
                now,
            ),
        )
        log_action(session.get("user_id"), f"Criou imovel: {data['titulo']}")
        flash("Imovel cadastrado com sucesso.", "success")
        return redirect(url_for("admin_imoveis"))
    return render_template(
        "admin/imovel_form.html",
        imovel={},
        modo="novo",
        secoes=SECOES_IMOVEIS,
    )


@app.route("/admin/imoveis/<int:imovel_id>/editar", methods=["GET", "POST"])
@login_required
def admin_imovel_editar(imovel_id):
    imovel = query_one("SELECT * FROM imoveis WHERE id = ?", (imovel_id,))
    if not imovel:
        flash("Imovel nao encontrado.", "warning")
        return redirect(url_for("admin_imoveis"))

    if request.method == "POST":
        data = parse_imovel_form()
        now = datetime.now().isoformat()
        execute(
            """
            UPDATE imoveis SET
                titulo = ?, descricao = ?, localizacao = ?, estado = ?, secao = ?, tipo = ?, categoria = ?, preco = ?, area = ?,
                dormitorios = ?, banheiros = ?, vagas = ?, suites = ?, caracteristicas = ?, tour360_url = ?,
                fotos = ?, destaque = ?, ativo = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["titulo"],
                data["descricao"],
                data["localizacao"],
                data["estado"],
                data["secao"],
                data["tipo"],
                data["categoria"],
                data["preco"],
                data["area"],
                data["dormitorios"],
                data["banheiros"],
                data["vagas"],
                data["suites"],
                data["caracteristicas"],
                data["tour360_url"],
                data["fotos"],
                data["destaque"],
                data["ativo"],
                now,
                imovel_id,
            ),
        )
        log_action(session.get("user_id"), f"Editou imovel #{imovel_id}")
        flash("Imovel atualizado com sucesso.", "success")
        return redirect(url_for("admin_imoveis"))

    return render_template(
        "admin/imovel_form.html",
        imovel=dict(imovel),
        modo="editar",
        secoes=SECOES_IMOVEIS,
    )


@app.post("/admin/imoveis/<int:imovel_id>/excluir")
@login_required
def admin_imovel_excluir(imovel_id):
    execute("DELETE FROM imoveis WHERE id = ?", (imovel_id,))
    log_action(session.get("user_id"), f"Excluiu imovel #{imovel_id}")
    flash("Imovel excluido.", "info")
    return redirect(url_for("admin_imoveis"))


@app.route("/admin/leads")
@login_required
def admin_leads():
    status = request.args.get("status", "").strip()
    if status:
        leads = query_all("SELECT * FROM leads WHERE status = ? ORDER BY id DESC", (status,))
    else:
        leads = query_all("SELECT * FROM leads ORDER BY id DESC")
    return render_template("admin/leads_list.html", leads=leads, status_atual=status)


@app.post("/admin/leads/<int:lead_id>/status")
@login_required
def admin_lead_status(lead_id):
    novo_status = request.form.get("status", "novo")
    execute("UPDATE leads SET status = ? WHERE id = ?", (novo_status, lead_id))
    log_action(session.get("user_id"), f"Alterou status do lead #{lead_id} para {novo_status}")
    flash("Status do lead atualizado.", "success")
    return redirect(url_for("admin_leads"))


@app.route("/admin/conteudo", methods=["GET", "POST"])
@login_required
def admin_conteudo():
    allowed_keys = [
        "quem_somos",
        "politica_privacidade",
        "servico_comprar_imovel",
        "servico_anuncie_imovel",
    ]
    if request.method == "POST":
        key = request.form.get("key", "")
        value = request.form.get("value", "")
        if key in allowed_keys:
            execute(
                """
                INSERT INTO contents (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            log_action(session.get("user_id"), f"Atualizou conteudo: {key}")
            flash("Conteudo salvo com sucesso.", "success")
            return redirect(url_for("admin_conteudo", key=key))
        flash("Chave de conteudo invalida.", "danger")

    selected = request.args.get("key", "quem_somos")
    if selected not in allowed_keys:
        selected = "quem_somos"
    value = get_content(selected, "")
    return render_template(
        "admin/conteudo_form.html",
        allowed_keys=allowed_keys,
        selected=selected,
        value=value,
    )


@app.route("/admin/config", methods=["GET", "POST"])
@login_required
def admin_config():
    config_keys = [
        "site_nome",
        "creci",
        "telefone",
        "telefone_secundario",
        "email_contato",
        "whatsapp",
        "instagram",
        "facebook",
        "endereco",
        "seo_title",
        "seo_description",
    ]
    if request.method == "POST":
        for key in config_keys:
            value = request.form.get(key, "").strip()
            execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
        log_action(session.get("user_id"), "Atualizou configuracoes gerais")
        flash("Configuracoes atualizadas com sucesso.", "success")
        return redirect(url_for("admin_config"))

    values = {key: get_setting(key, "") for key in config_keys}
    return render_template("admin/config_form.html", config=values)


@app.route("/admin/usuarios")
@login_required
@admin_required
def admin_usuarios():
    users = query_all("SELECT id, nome, email, role, created_at FROM users ORDER BY id DESC")
    return render_template("admin/users_list.html", users=users)


@app.route("/admin/usuarios/novo", methods=["GET", "POST"])
@login_required
@admin_required
def admin_usuario_novo():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "").strip()
        role = request.form.get("role", "editor")

        if not nome or not email or not senha:
            flash("Preencha nome, email e senha.", "danger")
            return render_template("admin/user_form.html")

        try:
            execute(
                """
                INSERT INTO users (nome, email, senha_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (nome, email, generate_password_hash(senha), role, datetime.now().isoformat()),
            )
            log_action(session.get("user_id"), f"Criou usuario: {email}")
            flash("Usuario criado com sucesso.", "success")
            return redirect(url_for("admin_usuarios"))
        except sqlite3.IntegrityError:
            flash("Este email ja esta em uso.", "danger")

    return render_template("admin/user_form.html")


@app.route("/admin/logs")
@login_required
@admin_required
def admin_logs():
    logs = query_all(
        """
        SELECT l.id, l.action, l.created_at, u.nome AS user_nome
        FROM activity_logs l
        LEFT JOIN users u ON u.id = l.user_id
        ORDER BY l.id DESC LIMIT 100
        """
    )
    return render_template("admin/logs_list.html", logs=logs)


if __name__ == "__main__":
    init_db()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "80"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
