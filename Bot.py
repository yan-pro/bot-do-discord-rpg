import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
import random
import io
import os
from dotenv import load_dotenv

from mapa import setup_mapa
from guerra import setup_guerra
from batalha import setup_batalha

# ==============================
# CONFIGURAÇÃO DO BOT
# ==============================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
ARQUIVO = "dados.json"
load_dotenv() # Carrega as variáveis do arquivo .env
TOKEN = os.getenv('DISCORD_TOKEN')

# ==============================
# CONFIGURAÇÕES DE EQUILÍBRIO
# ==============================
LIMITE_RECRUTAMENTO = 0.20
LOJA_UNIDADES = {
    "cacas":        [2,   10,   "Nave leve de combate"],
    "destroyers":   [10,  50,   "Nave pesada de destruição"],
    "tanques":      [5,   20,   "Blindado terrestre"],
    "fragatas":     [15,  80,   "Suporte naval espacial"],
    "cruzadores":   [30,  200,  "Nave de linha — pesada e devastadora"],
    "interceptores":[8,   35,   "Nave rápida anti-caça"],
    "bombardeiros": [20,  120,  "Ataque a estruturas e planetas"],
    "corvetas":     [12,  60,   "Furtiva de reconhecimento"],
}

ICONS_UNIDADES = {
    "cacas":        "✈️",
    "destroyers":   "💀",
    "tanques":      "🛡️",
    "fragatas":     "⚓",
    "cruzadores":   "🛸",
    "interceptores":"☄️",
    "bombardeiros": "💣",
    "corvetas":     "🌑",
}

# ==============================
# SISTEMA DE PLANETAS
# ==============================
TIPOS_PLANETA = {
    "agricola":   {"nome":"Agrícola",   "emoji":"🌾", "bonus_tipo":"populacao",  "desc":"Fértil e abundante em vida"},
    "industrial": {"nome":"Industrial", "emoji":"🏭", "bonus_tipo":"minerios",   "desc":"Rico em recursos minerais"},
    "militar":    {"nome":"Militar",    "emoji":"⚔️", "bonus_tipo":"recrutas",   "desc":"Posição estratégica de defesa"},
    "comercial":  {"nome":"Comercial",  "emoji":"💰", "bonus_tipo":"pib",        "desc":"Hub de comércio interestelar"},
    "cientifico": {"nome":"Científico", "emoji":"🔬", "bonus_tipo":"tecnologia", "desc":"Centro de pesquisa avançada"},
    "ermo":       {"nome":"Ermo",       "emoji":"🪨", "bonus_tipo":None,         "desc":"Sem recursos, valor estratégico"},
}

NIVEIS_PLANETA = {
    "desconhecido":   {"nome":"Desconhecido", "emoji":"❓", "multiplicador":0, "custo_pib":0,          "custo_min":0},
    "colonia":        {"nome":"Colônia",      "emoji":"🏕️", "multiplicador":1, "custo_pib":5_000_000,  "custo_min":1_000},
    "cidade":         {"nome":"Cidade",       "emoji":"🏙️", "multiplicador":2, "custo_pib":20_000_000, "custo_min":5_000},
    "capital":        {"nome":"Capital",      "emoji":"👑", "multiplicador":4, "custo_pib":80_000_000, "custo_min":20_000},
    "colonia_pendente":{"nome":"Pendente",    "emoji":"🚀", "multiplicador":0, "custo_pib":0,          "custo_min":0},
}

BONUS_BASE_PLANETA = {
    "populacao": 50_000,
    "minerios":  500,
    "recrutas":  1_000,
    "pib":       2_000_000,
    "tecnologia": 1,
}

def calcular_bonus_planeta(planeta):
    nivel = planeta.get("nivel", "desconhecido")
    if nivel in ("desconhecido", "colonia_pendente"):
        return {}
    tipo = planeta.get("tipo")
    if not tipo or tipo == "ermo":
        return {}
    mult       = NIVEIS_PLANETA.get(nivel, {}).get("multiplicador", 0)
    bonus_tipo = TIPOS_PLANETA[tipo]["bonus_tipo"]
    valor      = BONUS_BASE_PLANETA.get(bonus_tipo, 0) * mult
    return {bonus_tipo: valor}

def get_planeta(imp, nome):
    return imp.get("planetas_data", {}).get(nome)

# ==============================
# SISTEMA DE TECNOLOGIA
# ==============================
AREAS_TECH = {
    "militar":    {"nome":"Tecnologia Militar",     "emoji":"⚔️", "desc":"Aumenta o poder de combate",       "bonus":"+5% de poder por nível",         "cor":0x450A0A},
    "industrial": {"nome":"Tecnologia Industrial",  "emoji":"🏭", "desc":"Aumenta produção de minérios",     "bonus":"+10% de produção por nível",      "cor":0x1C1917},
    "economico":  {"nome":"Tecnologia Econômica",   "emoji":"💰", "desc":"Aumenta o PIB por turno",          "bonus":"+5% de PIB por turno por nível",  "cor":0x78350F},
    "espacial":   {"nome":"Tecnologia Espacial",    "emoji":"🚀", "desc":"Expande capacidade territorial",   "bonus":"+2 slots por nível",              "cor":0x042F2E},
    "espionagem": {"nome":"Tecnologia de Espionagem","emoji":"🕵️","desc":"Melhora operações de intel",       "bonus":"+10% de chance por nível",        "cor":0x0F172A},
}

NIVEL_MAX_TECH = 10

def custo_tech(nivel_atual):
    prox = nivel_atual + 1
    return {"pib": 1_000_000 * (prox ** 2), "minerios": 500 * (prox ** 2)}

def bonus_tech(imp, area):
    nivel = imp.get("tecnologias", {}).get(area, 0)
    bonus_por_nivel = {"militar":0.05,"industrial":0.10,"economico":0.05,"espacial":0.0,"espionagem":0.10}
    return 1.0 + (nivel * bonus_por_nivel.get(area, 0.0))

def slots_territorio(imp):
    nivel = imp.get("tecnologias", {}).get("espacial", 0)
    return 5 + (nivel * 2)

NOMES_NIVEIS = ["","Primitivo","Emergente","Desenvolvido","Avançado","Superior","Elite","Estelar","Cósmico","Transcendente","Ascendido"]

TIPOS_FABRICAS = {
    "fabrica_pequena":5,"fabrica_media":15,"fabrica_grande":40,"fabrica_continental":100,"mundo_forja":500
}
PRECO_FABRICAS = {
    "fabrica_pequena":     [500_000,     200,   5,   "Pequena"],
    "fabrica_media":       [2_000_000,   600,   15,  "Media"],
    "fabrica_grande":      [8_000_000,   1_500, 40,  "Grande"],
    "fabrica_continental": [30_000_000,  5_000, 100, "Continental"],
    "mundo_forja":         [150_000_000, 20_000,500, "Mundo Forja"],
}

# ==============================
# PALETA DE CORES
# ==============================
COR_PRIMARIA   = 0x6B21A8
COR_PERIGO     = 0x7F1D1D
COR_SUCESSO    = 0x3B0764
COR_NEUTRO     = 0x0F172A
COR_ALERTA     = 0x7C3AED
COR_OURO       = 0x78350F
COR_COMERCIO   = 0x0C4A6E
COR_MILITAR    = 0x450A0A
COR_EVENTO_BOM = 0x1E3A5F
COR_EVENTO_MAU = 0x4C0519
COR_TERRITORIO = 0x042F2E
COR_HISTORIA   = 0x1C1917

BANNER_MILITAR  = "https://i.imgur.com/8TtWRSe.jpg"
BANNER_LOJA     = "https://i.imgur.com/nMXYkSp.jpg"
BANNER_RANKING  = "https://i.imgur.com/vFqKMbD.jpg"
BANNER_EVENTO   = "https://i.imgur.com/QUmYDqY.jpg"
BANNER_COMERCIO = "https://i.imgur.com/WqLuVnO.jpg"
BANNER_TERRIT   = "https://i.imgur.com/KzHcJVA.jpg"

RODAPE_PADRAO   = "⬡ Sistema Galáctico de Impérios"
RODAPE_MILITAR  = "⚔️ Comando Supremo das Frotas"
RODAPE_LOJA     = "🛒 Arsenal Galáctico"
RODAPE_COMERCIO = "🤝 Câmara de Comércio Interestelar"
RODAPE_TERRIT   = "🌌 Cartografia Galáctica"
RODAPE_HISTORIA = "📜 Arquivo Imperial Secreto"
RODAPE_EVENTO   = "🌐 Transmissão de Emergência"
RODAPE_ADM      = "🛡️ Conselho dos Administradores"

SEP_PADRAO   = "░▒▓█  ⬡  Sistema Galáctico  ⬡  █▓▒░"
SEP_MILITAR  = "⚔ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ⚔"
SEP_LOJA     = "◈ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ◈"
SEP_COMERCIO = "◆ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ◆"
SEP_EVENTO   = "◉ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ◉"
SEP_TERRIT   = "🌐 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 🌐"
SEPARADOR    = SEP_PADRAO

FLAVOR_TURNO = [
    "🌠 *As estrelas testemunham o avanço dos impérios...*",
    "🔭 *O cosmos não espera — novos recursos emergem das sombras.*",
    "⚡ *A máquina de guerra galáctica nunca para.*",
    "🌌 *Um novo ciclo. Novas conquistas a serem feitas.*",
    "💫 *O universo expandiu. Seus cofres também.*",
]
FLAVOR_COMPRA = [
    "🚀 *Frotas partem para as fronteiras do espaço...*",
    "⚔️ *O arsenal do império cresce na escuridão.*",
    "🌑 *Novas forças juram lealdade ao trono imperial.*",
    "💀 *Inimigos já tremem ao ouvir o rugido dos motores.*",
]
FLAVOR_MINAR = [
    "⛏️ *Sondas perfuram as entranhas do asteroide...*",
    "🪨 *Minerais raros emergem das profundezas do vazio.*",
    "💎 *As colônias mineiras trabalham sem descanso.*",
    "🌋 *Vulcões estelares revelam seus tesouros.*",
]
FLAVOR_CONSTRUIR = [
    "🏗️ *As fornalhas estelares trabalham dia e noite...*",
    "🔩 *Engenheiros imperiais erguem o futuro do império.*",
    "⚙️ *O complexo industrial expande seu alcance.*",
]

# ==============================
# SISTEMA DE ARQUIVOS
# ==============================
def carregar():
    if not os.path.exists(ARQUIVO):
        return {"imperios": {}, "cofre_servidor": {"pib": 0, "minerios": 0}}
    with open(ARQUIVO, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"imperios": {}, "cofre_servidor": {"pib": 0, "minerios": 0}}

def salvar(dados_locais):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(dados_locais, f, indent=4, ensure_ascii=False)

dados = carregar()

# ==============================
# AUXILIARES
# ==============================
def formatar_numero(n):
    return f"{n:,}".replace(",", ".")

def formatar_creditos(n):
    return f"{formatar_numero(n)} créditos"

def nome_bonito(chave):
    nomes = {
        "cacas":"Caças","destroyers":"Destroyers","tanques":"Tanques","fragatas":"Fragatas",
        "cruzadores":"Cruzadores","interceptores":"Interceptores","bombardeiros":"Bombardeiros","corvetas":"Corvetas",
    }
    return nomes.get(chave, chave.replace("_", " ").title())

def tem_permissao_adm(interaction):
    cargos = [c.name.lower() for c in interaction.user.roles]
    return "adm" in cargos or "administrador" in cargos or interaction.user.guild_permissions.administrator

def registrar_historico(id_u, evento):
    imp = dados["imperios"].get(id_u)
    if not imp:
        return
    entrada = f"[{datetime.now().strftime('%d/%m %H:%M')}] {evento}"
    if "historico" not in imp:
        imp["historico"] = []
    imp["historico"].insert(0, entrada)
    imp["historico"] = imp["historico"][:20]

def imperio_existe(id_u):
    return id_u in dados["imperios"]

def get_cor(imp):
    try:
        return int(imp.get("cor", "6B21A8"), 16)
    except ValueError:
        return COR_PRIMARIA

def thumbnail_empire(embed, imp):
    if imp.get("brasao", "").startswith("http"):
        embed.set_thumbnail(url=imp["brasao"])

def garantir_campos(imp):
    imp.setdefault("tecnologias", {a: 0 for a in AREAS_TECH})
    imp.setdefault("planetas_data", {})
    imp.setdefault("historico_guerras", [])
    imp.setdefault("aliancas", [])
    imp.setdefault("vassalos", [])
    imp.setdefault("planetas", [])
    imp.setdefault("sistemas", [])
    imp.setdefault("projetos", {})
    imp.setdefault("historico", [])
    for k in LOJA_UNIDADES:
        imp.setdefault(k, 0)
    for k in TIPOS_FABRICAS:
        imp.setdefault("fabricas", {})
        imp["fabricas"].setdefault(k, 0)

# ==============================
# GERADOR DE BANNER (CORREÇÃO 3)
# ==============================
def gerar_banner_imperio(imp: dict):
    """Gera um banner 800x200 estrelado com a cor do império. Retorna BytesIO ou None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    W, H = 800, 200
    cor_hex = imp.get("cor", "6B21A8")
    try:
        r = int(cor_hex[0:2], 16)
        g = int(cor_hex[2:4], 16)
        b = int(cor_hex[4:6], 16)
    except Exception:
        r, g, b = 107, 33, 168

    base = Image.new("RGBA", (W, H), (8, 4, 20, 255))
    d = ImageDraw.Draw(base)

    # Estrelas aleatórias baseadas no nome (seed fixo = banner sempre igual)
    rng = random.Random(imp.get("nome", "x"))
    for _ in range(300):
        sx, sy = rng.randint(0, W), rng.randint(0, H)
        sb = rng.randint(80, 220)
        d.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(sb, sb, sb, 130))

    # Gradiente vertical com a cor do império
    for i in range(H):
        alpha = int(100 * (1 - i / H))
        d.line([(0, i), (W, i)], fill=(r, g, b, alpha))

    # Bordas coloridas
    d.rectangle([0, H - 4, W, H], fill=(r, g, b, 230))
    d.rectangle([0, 0, W, 3],     fill=(r, g, b, 130))

    # Textos
    try:
        fn = ImageFont.truetype("arial.ttf", 38)
        fs = ImageFont.truetype("arial.ttf", 17)
    except Exception:
        fn = fs = ImageFont.load_default()

    nome = imp.get("nome", "Império")
    desc = imp.get("descricao", "")
    if desc:
        desc = f'"{desc[:55]}"' if len(desc) <= 55 else f'"{desc[:55]}..."'

    d.text((W // 2, 68),  nome, fill=(255, 255, 255, 245), font=fn, anchor="mm")
    if desc:
        dr = min(r + 90, 255); dg = min(g + 90, 255); db = min(b + 90, 255)
        d.text((W // 2, 118), desc, fill=(dr, dg, db, 200), font=fs, anchor="mm")
    d.text((W // 2, 157), "⬡ Sistema Galáctico de Impérios ⬡", fill=(180, 170, 210, 155), font=fs, anchor="mm")

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ==============================
# MODALS
# ==============================

# Modal de tecnologias — abre logo após o ModalCriar
class ModalTecnologias(discord.ui.Modal, title="Tecnologias Iniciais do Império"):
    tec_militar    = discord.ui.TextInput(label="⚔️ Tecnologia Militar (0-10)",    placeholder="0", default="0", max_length=2)
    tec_industrial = discord.ui.TextInput(label="🏭 Tecnologia Industrial (0-10)", placeholder="0", default="0", max_length=2)
    tec_economico  = discord.ui.TextInput(label="💰 Tecnologia Econômica (0-10)",  placeholder="0", default="0", max_length=2)
    tec_espacial   = discord.ui.TextInput(label="🚀 Tecnologia Espacial (0-10)",   placeholder="0", default="0", max_length=2)
    tec_espionagem = discord.ui.TextInput(label="🕵️ Tecnologia Espionagem (0-10)", placeholder="0", default="0", max_length=2)

    def __init__(self, id_u, membro, capital_val, celula_mapa, brasao_val):
        super().__init__()
        self.id_u        = id_u
        self.membro      = membro
        self.capital_val = capital_val
        self.celula_mapa = celula_mapa
        self.brasao_val  = brasao_val

    def _parse_nivel(self, valor: str) -> int:
        try:
            n = int(valor.strip())
            return max(0, min(10, n))
        except ValueError:
            return 0

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=False)
        imp = dados["imperios"].get(self.id_u)
        if not imp:
            return await interaction.followup.send("❌ Império não encontrado.", ephemeral=True)

        techs = {
            "militar":    self._parse_nivel(self.tec_militar.value),
            "industrial": self._parse_nivel(self.tec_industrial.value),
            "economico":  self._parse_nivel(self.tec_economico.value),
            "espacial":   self._parse_nivel(self.tec_espacial.value),
            "espionagem": self._parse_nivel(self.tec_espionagem.value),
        }
        imp["tecnologias"] = techs
        salvar(dados)

        # Embed de confirmação final
        embed = discord.Embed(
            title="🌌 Império Registrado com Sucesso!",
            description=f"**{imp['nome']}** desperta nas trevas do cosmos.",
            color=COR_SUCESSO,
        )
        embed.add_field(name="👑 Comandante",  value=self.membro.mention,               inline=True)
        embed.add_field(name="💰 PIB Inicial", value=formatar_creditos(imp["pib"]),      inline=True)
        embed.add_field(name="👥 População",   value=formatar_numero(imp["populacao_total"]), inline=True)
        embed.add_field(name="👑 Capital",     value=self.capital_val,                   inline=True)
        if self.celula_mapa:
            embed.add_field(name="🗺️ Posição no Mapa", value=f"`{self.celula_mapa}`",   inline=True)
        # Tecnologias
        tech_txt = "  ".join(f"{AREAS_TECH[a]['emoji']} `{techs[a]}`" for a in AREAS_TECH)
        embed.add_field(name="🔬 Tecnologias Iniciais", value=tech_txt, inline=False)
        if self.brasao_val:
            embed.set_thumbnail(url=self.brasao_val)
        embed.set_footer(text=RODAPE_PADRAO)
        await interaction.followup.send(embed=embed)


# CORREÇÃO 1 — ModalCriar com tecnologias iniciais integradas
class ModalCriar(discord.ui.Modal, title="Registrar Novo Imperio"):
    nome    = discord.ui.TextInput(label="Nome do Imperio",  placeholder="Ex: Imperio Estelar")
    capital = discord.ui.TextInput(label="Nome da Capital",  placeholder="Ex: Nova Terra")
    pib     = discord.ui.TextInput(label="PIB Inicial",      placeholder="Ex: 1000000")
    pop     = discord.ui.TextInput(label="Populacao",        default="1000000")
    techs   = discord.ui.TextInput(
        label="Techs: Mil/Ind/Eco/Esp/Espi (0-10 cada)",
        placeholder="Ex: 2/3/1/0/0",
        default="0/0/0/0/0",
        required=False,
    )

    def __init__(self, membro):
        super().__init__()
        self.membro = membro

    def _parse_techs(self, valor: str) -> dict:
        areas  = list(AREAS_TECH.keys())
        partes = [p.strip() for p in valor.replace(",", "/").split("/")]
        result = {}
        for i, area in enumerate(areas):
            try:    result[area] = max(0, min(10, int(partes[i]))) if i < len(partes) else 0
            except: result[area] = 0
        return result

    async def on_submit(self, interaction):
        id_u = str(self.membro.id)
        await interaction.response.defer(ephemeral=False)
        try:
            pib_val = int(self.pib.value.replace(".", "").replace(",", ""))
            pop_val = int(self.pop.value.replace(".", "").replace(",", ""))
        except ValueError:
            return await interaction.followup.send("Valor invalido! Use apenas numeros.", ephemeral=True)

        capital_val = self.capital.value.strip()
        techs_val   = self._parse_techs(self.techs.value or "0/0/0/0/0")

        dados["imperios"][id_u] = {
            "nome": self.nome.value, "pib": pib_val, "minerios": 5000,
            "populacao_total": pop_val, "recrutas": 0,
            "brasao": "", "descricao": "", "cor": "6B21A8",
            "fabricas": {k: 0 for k in TIPOS_FABRICAS}, "projetos": {},
            "planetas": [capital_val],
            "sistemas": [], "historico": [],
            "tecnologias": techs_val,
            "planetas_data": {
                capital_val: {"nivel": "capital", "tipo": "comercial", "recurso": None}
            },
            "historico_guerras": [], "aliancas": [], "vassalos": [],
        }
        for k in LOJA_UNIDADES:
            dados["imperios"][id_u][k] = 0
        salvar(dados)

        celula_mapa = None
        try:
            from mapa import carregar_mapa, mapear_capital_automatico
            cfg_mapa    = carregar_mapa()
            celula_mapa = mapear_capital_automatico(cfg_mapa, capital_val, raio=30)
            await atualizar_mapa()
        except Exception as e:
            print(f"[ModalCriar] Aviso ao mapear capital: {e}")

        tech_txt = "  ".join(f"{AREAS_TECH[a]['emoji']} `{techs_val[a]}`" for a in AREAS_TECH)
        embed = discord.Embed(
            title="🌌 Novo Império Registrado",
            description=f"**{self.nome.value}** desperta nas trevas do cosmos.",
            color=COR_SUCESSO,
        )
        embed.add_field(name="👑 Comandante",  value=self.membro.mention,        inline=True)
        embed.add_field(name="💰 PIB Inicial", value=formatar_creditos(pib_val), inline=True)
        embed.add_field(name="👥 População",   value=formatar_numero(pop_val),   inline=True)
        embed.add_field(name="👑 Capital",     value=capital_val,                inline=True)
        if celula_mapa:
            embed.add_field(name="🗺️ Mapa",   value=f"`{celula_mapa}`",         inline=True)
        embed.add_field(name="🔬 Tecnologias", value=tech_txt,                   inline=False)
        embed.add_field(name="🎨 Brasão",      value="Use `/alterar_brasao` para definir o brasão", inline=False)
        embed.set_footer(text=RODAPE_PADRAO)
        await interaction.followup.send(embed=embed)


class ModalCriarProjeto(discord.ui.Modal, title="Registrar Projeto"):
    nome_projeto   = discord.ui.TextInput(label="Nome do Projeto",        placeholder="Ex: Estacao Orbital Alpha")
    descricao      = discord.ui.TextInput(label="Descricao",              style=discord.TextStyle.paragraph, max_length=500)
    custo_minerios = discord.ui.TextInput(label="Custo em Minerios",      placeholder="Ex: 2000")
    custo_pib      = discord.ui.TextInput(label="Custo em Creditos",      placeholder="Ex: 500000")
    poder_militar  = discord.ui.TextInput(label="Poder Militar (PM) que concede", placeholder="Ex: 500 (0 se nenhum)", default="0")
    foto_url       = discord.ui.TextInput(label="URL da Imagem (opcional)", placeholder="https://...", required=False)

    def __init__(self, membro):
        super().__init__()
        self.membro = membro

    async def on_submit(self, interaction):
        id_u = str(self.membro.id)
        if not imperio_existe(id_u):
            return await interaction.response.send_message(f"{self.membro.mention} nao tem um imperio.", ephemeral=True)
        try:
            custo_min = int(self.custo_minerios.value.replace(".", "").replace(",", ""))
            custo_pib = int(self.custo_pib.value.replace(".", "").replace(",", ""))
            pm_val    = int(self.poder_militar.value.replace(".", "").replace(",", ""))
        except ValueError:
            return await interaction.response.send_message("Valores inválidos! Use apenas números.", ephemeral=True)
        imp    = dados["imperios"][id_u]
        nome_p = self.nome_projeto.value.strip()
        foto   = self.foto_url.value.strip() if self.foto_url.value else ""
        imp["projetos"][nome_p] = {
            "descricao":      self.descricao.value.strip(),
            "custo_minerios": custo_min,
            "custo_pib":      custo_pib,
            "poder_militar":  pm_val,
            "foto":           foto,
        }
        salvar(dados)
        embed = discord.Embed(
            title="🔭 Projeto Registrado",
            description=f"**{nome_p}**\n{self.descricao.value.strip()}",
            color=COR_ALERTA,
        )
        embed.add_field(name="💸 Custo Previsto",   value=f"💎 {formatar_numero(custo_min)} min.\n💰 {formatar_creditos(custo_pib)}", inline=True)
        embed.add_field(name="📦 Reservas Atuais",  value=f"💎 {formatar_numero(imp['minerios'])} min.\n💰 {formatar_creditos(imp['pib'])}", inline=True)
        if pm_val > 0:
            embed.add_field(name="⚔️ Poder Militar", value=f"+{formatar_numero(pm_val)} PM ao concluir", inline=False)
        embed.set_footer(text=f"{RODAPE_PADRAO} · Recursos cobrados na conclusão")
        if foto.startswith("http"):
            embed.set_image(url=foto)
        await interaction.response.send_message(content=f"📋 Projeto registrado para {self.membro.mention}!", embed=embed)


class ModalEditarPerfil(discord.ui.Modal, title="Editar Perfil do Imperio"):
    brasao_url = discord.ui.TextInput(label="URL do Brasao",       placeholder="https://...", required=False)
    descricao  = discord.ui.TextInput(label="Descricao / Lore",    style=discord.TextStyle.paragraph, max_length=600, required=False)
    cor_hex    = discord.ui.TextInput(label="Cor hex (ex FF5733)", placeholder="FF5733", max_length=6, required=False)

    def __init__(self, membro):
        super().__init__()
        self.membro = membro

    async def on_submit(self, interaction):
        imp = dados["imperios"].get(str(self.membro.id))
        if not imp:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        if self.brasao_url.value.strip().startswith("http"):
            imp["brasao"] = self.brasao_url.value.strip()
        if self.descricao.value.strip():
            imp["descricao"] = self.descricao.value.strip()
        if self.cor_hex.value.strip():
            try:
                int(self.cor_hex.value.strip(), 16)
                imp["cor"] = self.cor_hex.value.strip().upper()
            except ValueError:
                pass
        salvar(dados)
        embed = discord.Embed(title="🎨 Registros Imperiais Atualizados", description=f"O arquivo de **{imp['nome']}** foi modificado.", color=COR_SUCESSO)
        embed.set_footer(text=RODAPE_PADRAO)
        thumbnail_empire(embed, imp)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# CORREÇÃO 2 — Modal para alterar brasão via !setar_brasao
class ModalBrasao(discord.ui.Modal, title="Alterar Brasão do Império"):
    brasao_url = discord.ui.TextInput(
        label="Nova URL do Brasão",
        placeholder="https://i.imgur.com/...",
        min_length=10,
    )

    def __init__(self, id_u):
        super().__init__()
        self.id_u = id_u

    async def on_submit(self, interaction):
        url = self.brasao_url.value.strip()
        if not url.startswith("http"):
            return await interaction.response.send_message(
                "❌ URL inválida. Deve começar com http.", ephemeral=True
            )
        dados["imperios"][self.id_u]["brasao"] = url
        salvar(dados)
        imp = dados["imperios"][self.id_u]
        embed = discord.Embed(title="🎨 Brasão Atualizado!", color=COR_SUCESSO)
        embed.set_image(url=url)
        embed.set_thumbnail(url=url)
        embed.set_footer(text=RODAPE_PADRAO)
        await interaction.response.send_message(embed=embed)


# ==============================
# VIEW - COBRAR COM BOTOES
# ==============================
class ViewCobrar(discord.ui.View):
    def __init__(self, id_cobrador, id_cobrado, pib, minerios, motivo):
        super().__init__(timeout=120)
        self.id_cobrador = id_cobrador
        self.id_cobrado  = id_cobrado
        self.pib         = pib
        self.minerios    = minerios
        self.motivo      = motivo
        self.encerrado   = False

    async def _encerrar(self, interaction, aceito):
        if self.encerrado:
            return await interaction.response.send_message("Esta cobranca ja foi respondida.", ephemeral=True)
        if str(interaction.user.id) != self.id_cobrado:
            return await interaction.response.send_message("Apenas o cobrado pode responder.", ephemeral=True)
        self.encerrado = True
        for item in self.children:
            item.disabled = True
        imp_cobrado  = dados["imperios"].get(self.id_cobrado, {})
        imp_cobrador = dados["imperios"].get(self.id_cobrador, {})
        if not aceito:
            embed = discord.Embed(title="❌ Cobrança Recusada", description=f"**{imp_cobrado.get('nome','?')}** recusou.", color=COR_PERIGO)
            embed.set_footer(text=RODAPE_PADRAO)
            thumbnail_empire(embed, imp_cobrado)
            return await interaction.response.edit_message(embed=embed, view=self)
        sem = []
        if self.pib      > 0 and imp_cobrado.get("pib",0)      < self.pib:      sem.append("Créditos insuficientes")
        if self.minerios > 0 and imp_cobrado.get("minerios",0) < self.minerios: sem.append("Minérios insuficientes")
        if sem:
            embed = discord.Embed(title="⚠️ Recursos Insuficientes", description="\n".join(sem), color=COR_PERIGO)
            embed.set_footer(text=RODAPE_PADRAO)
            return await interaction.response.edit_message(embed=embed, view=self)
        imp_cobrado["pib"]       -= self.pib
        imp_cobrado["minerios"]  -= self.minerios
        imp_cobrador["pib"]      += self.pib
        imp_cobrador["minerios"] += self.minerios
        partes = []
        if self.pib      > 0: partes.append(formatar_creditos(self.pib))
        if self.minerios > 0: partes.append(f"{formatar_numero(self.minerios)} min.")
        txt = " + ".join(partes)
        registrar_historico(self.id_cobrado,  f"Pagou {txt} para {imp_cobrador.get('nome','?')} - {self.motivo}")
        registrar_historico(self.id_cobrador, f"Recebeu {txt} de {imp_cobrado.get('nome','?')} - {self.motivo}")
        salvar(dados)
        embed = discord.Embed(title="✅ Cobrança Aceita e Paga", color=COR_SUCESSO)
        embed.add_field(name="💸 Valor Pago", value=txt, inline=False)
        embed.add_field(name=f"📦 Saldo de {imp_cobrado.get('nome','?')}", value=f"💰 {formatar_creditos(imp_cobrado.get('pib',0))} | 💎 {formatar_numero(imp_cobrado.get('minerios',0))} min.", inline=False)
        embed.set_footer(text=RODAPE_PADRAO)
        thumbnail_empire(embed, imp_cobrado)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✅ Aceitar", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction, button):
        await self._encerrar(interaction, True)

    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction, button):
        await self._encerrar(interaction, False)


# ==============================
# SLASH COMMANDS - ADM
# ==============================

@bot.tree.command(name="criar_imperio", description="[ADM] Registra um novo jogador")
async def slash_criar(interaction, membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    await interaction.response.send_modal(ModalCriar(membro))


@bot.tree.command(name="editar_perfil", description="[ADM] Edita brasao, descricao e cor")
async def slash_editar_perfil(interaction, membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    if not imperio_existe(str(membro.id)):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    await interaction.response.send_modal(ModalEditarPerfil(membro))


@bot.tree.command(name="turno", description="[ADM] Processa a producao de todos")
async def slash_turno(interaction):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)

    await interaction.response.defer()

    relatorio = {}  # id_u -> {nome, pib_ganho, min_ganho}

    for id_u, imp in dados["imperios"].items():
        garantir_campos(imp)
        prod_base       = sum(imp["fabricas"].get(k, 0) * v for k, v in TIPOS_FABRICAS.items())
        prod_industrial = int(prod_base * bonus_tech(imp, "industrial"))
        pib_bonus       = int(20_000_000 * bonus_tech(imp, "economico"))

        ganho_pib = pib_bonus
        ganho_min = 10 + prod_industrial

        imp["pib"]      += pib_bonus
        imp["minerios"] += 10 + prod_industrial

        buff = imp.get("buff_guerra", {})
        if buff.get("industrial"):
            b = int((10 + prod_industrial) * buff["industrial"] / 100)
            imp["minerios"] += b; ganho_min += b
        if buff.get("economico"):
            b = int(pib_bonus * buff["economico"] / 100)
            imp["pib"] += b; ganho_pib += b
        if buff.get("recrutas"):
            bonus_rec = int(imp.get("recrutas", 0) * buff["recrutas"] / 100)
            limite    = int(imp["populacao_total"] * LIMITE_RECRUTAMENTO)
            imp["recrutas"] = min(imp.get("recrutas",0) + bonus_rec, limite)

        nerf = imp.get("nerf_guerra", {})
        if nerf.get("industrial"):
            n = int((10 + prod_industrial) * nerf["industrial"] / 100)
            imp["minerios"] = max(0, imp["minerios"] - n); ganho_min -= n
        if nerf.get("economico"):
            n = int(pib_bonus * nerf["economico"] / 100)
            imp["pib"]      = max(0, imp["pib"] - n); ganho_pib -= n
        if nerf.get("geral"):
            pct = nerf["geral"] / 100
            imp["pib"]      = max(0, int(imp["pib"]      * (1 - pct)))
            imp["minerios"] = max(0, int(imp["minerios"] * (1 - pct)))

        vassalagem = imp.get("vassalagem")
        tributo_pib = 0
        if vassalagem and vassalagem.get("tributo", 0) > 0:
            tributo_pib = int(imp["pib"] * vassalagem["tributo"] / 100)
            imp["pib"]  = max(0, imp["pib"] - tributo_pib)
            ganho_pib  -= tributo_pib
            id_s = vassalagem.get("soberano")
            if id_s and id_s in dados["imperios"]:
                dados["imperios"][id_s]["pib"] += tributo_pib

        for nome_p, dados_p in imp["planetas_data"].items():
            bonus = calcular_bonus_planeta(dados_p)
            if "pib"       in bonus: imp["pib"]             += bonus["pib"];      ganho_pib += bonus["pib"]
            if "minerios"  in bonus: imp["minerios"]         += bonus["minerios"]; ganho_min += bonus["minerios"]
            if "recrutas"  in bonus: imp["recrutas"]          = min(imp["recrutas"] + bonus["recrutas"], int(imp["populacao_total"] * LIMITE_RECRUTAMENTO))
            if "populacao" in bonus: imp["populacao_total"]  += bonus["populacao"]

        if imp.get("sancao"):
            imp["sancao"]["turnos"] -= 1
            if imp["sancao"]["turnos"] <= 0:
                del imp["sancao"]

        relatorio[id_u] = {
            "nome":      imp["nome"],
            "pib_ganho": ganho_pib,
            "min_ganho": ganho_min,
            "tributo":   tributo_pib,
            "sancao":    bool(imp.get("sancao")),
        }

    salvar(dados)

    # Embed principal
    flavor = random.choice(FLAVOR_TURNO)
    embed = discord.Embed(
        title="🌠 Ciclo Galáctico Processado",
        description=f"{flavor}\n{SEP_PADRAO}",
        color=COR_PRIMARIA,
    )
    embed.add_field(name="📊 Impérios Ativos", value=str(len(dados["imperios"])), inline=True)
    embed.add_field(name="🔄 Status",           value="Produção distribuída",      inline=True)
    embed.set_image(url=BANNER_EVENTO)
    embed.set_footer(text=RODAPE_ADM)
    await interaction.followup.send(embed=embed)

    # Embed de ganhos por império
    linhas = []
    for id_u, r in sorted(relatorio.items(), key=lambda x: x[1]["pib_ganho"], reverse=True):
        sinal_pib = "+" if r["pib_ganho"] >= 0 else ""
        sinal_min = "+" if r["min_ganho"] >= 0 else ""
        tag = " 🚫" if r["sancao"] else ""
        tributo_txt = f"  *(−{formatar_creditos(r['tributo'])} tributo)*" if r["tributo"] > 0 else ""
        linhas.append(
            f"**{r['nome']}**{tag}\n"
            f"　💰 {sinal_pib}{formatar_creditos(r['pib_ganho'])}{tributo_txt}  "
            f"💎 {sinal_min}{formatar_numero(r['min_ganho'])} min."
        )

    # Discord tem limite de 4096 chars por embed — divide se necessário
    chunks = []
    bloco  = ""
    for l in linhas:
        if len(bloco) + len(l) > 3800:
            chunks.append(bloco)
            bloco = l + "\n\n"
        else:
            bloco += l + "\n\n"
    if bloco:
        chunks.append(bloco)

    for i, chunk in enumerate(chunks):
        titulo = "📈  Ganhos deste Turno" if i == 0 else "📈  Ganhos deste Turno (cont.)"
        emb = discord.Embed(title=titulo, description=chunk.strip(), color=COR_PRIMARIA)
        emb.set_footer(text=RODAPE_ADM)
        await interaction.followup.send(embed=emb)

    await atualizar_mapa()


@bot.tree.command(name="registrar_projeto", description="[ADM] Registra um projeto para um jogador")
async def slash_registrar_projeto(interaction, membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    await interaction.response.send_modal(ModalCriarProjeto(membro))


@bot.tree.command(name="construir_projeto", description="[ADM] Constrói um projeto descontando recursos (pode definir quantidade)")
@app_commands.describe(membro="Jogador", nome_projeto="Nome exato do projeto", quantidade="Quantidade a construir (padrão: 1)")
async def slash_construir_projeto(interaction, membro: discord.Member, nome_projeto: str, quantidade: int = 1):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if quantidade < 1:
        return await interaction.response.send_message("Quantidade deve ser pelo menos 1.", ephemeral=True)
    imp      = dados["imperios"][id_u]
    projetos = imp.get("projetos", {})
    if nome_projeto not in projetos:
        lista = "\n".join(f"• {p}" for p in projetos) or "Nenhum projeto."
        return await interaction.response.send_message(f"Projeto não encontrado.\n\n**Disponíveis:**\n{lista}", ephemeral=True)
    projeto   = projetos[nome_projeto]
    custo_min = projeto["custo_minerios"] * quantidade
    custo_pib = projeto["custo_pib"]      * quantidade
    pm_ganho  = projeto.get("poder_militar", 0) * quantidade
    sem = []
    if imp["minerios"] < custo_min: sem.append(f"💎 Precisa {formatar_numero(custo_min)} min., tem {formatar_numero(imp['minerios'])}")
    if imp["pib"]      < custo_pib: sem.append(f"💰 Precisa {formatar_creditos(custo_pib)}, tem {formatar_creditos(imp['pib'])}")
    if sem:
        return await interaction.response.send_message("❌ Recursos insuficientes:\n" + "\n".join(sem), ephemeral=True)
    imp["minerios"] -= custo_min
    imp["pib"]      -= custo_pib
    # Remove o projeto se for quantidade única, mantém se for recorrente
    del imp["projetos"][nome_projeto]
    registrar_historico(id_u, f"Projeto construído: {nome_projeto} × {quantidade}")
    salvar(dados)
    titulo = f"🏗️ {'Construção' if quantidade == 1 else f'{quantidade}× Construção'} Concluída"
    embed = discord.Embed(
        title=titulo,
        description=f"**{nome_projeto}**\n{projeto.get('descricao','')}",
        color=get_cor(imp),
    )
    embed.add_field(name="🔢 Quantidade",  value=str(quantidade),                                                     inline=True)
    embed.add_field(name="💸 Consumido",   value=f"💎 {formatar_numero(custo_min)} min.\n💰 {formatar_creditos(custo_pib)}", inline=True)
    embed.add_field(name="📦 Restante",    value=f"💎 {formatar_numero(imp['minerios'])} min.\n💰 {formatar_creditos(imp['pib'])}", inline=True)
    if pm_ganho > 0:
        embed.add_field(name="⚔️ PM Ganho", value=f"+{formatar_numero(pm_ganho)} Poder Militar", inline=False)
    embed.set_footer(text=f"{RODAPE_PADRAO} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    if projeto.get("foto", "").startswith("http"):
        embed.set_image(url=projeto["foto"])
    await interaction.response.send_message(content=f"🌌 {membro.mention} expandiu seu império!", embed=embed)


@bot.tree.command(name="ver_projetos", description="[ADM] Lista os projetos de um jogador com imagens")
async def slash_ver_projetos(interaction, membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    projetos = dados["imperios"][id_u].get("projetos", {})
    if not projetos:
        return await interaction.response.send_message("📭 Nenhum projeto registrado.", ephemeral=True)
    imp = dados["imperios"][id_u]
    await interaction.response.defer()
    for nome_p, info in projetos.items():
        pm = info.get("poder_militar", 0)
        embed = discord.Embed(
            title=f"🔭 {nome_p}",
            description=info.get("descricao", "Sem descrição."),
            color=COR_ALERTA,
        )
        embed.add_field(name="💎 Custo Minérios", value=formatar_numero(info["custo_minerios"]) + " min.", inline=True)
        embed.add_field(name="💰 Custo Créditos", value=formatar_creditos(info["custo_pib"]),              inline=True)
        if pm > 0:
            embed.add_field(name="⚔️ PM ao Concluir", value=f"+{formatar_numero(pm)}", inline=True)
        foto = info.get("foto", "")
        if foto.startswith("http"):
            embed.set_image(url=foto)
        embed.set_footer(text=f"{RODAPE_PADRAO} · {imp['nome']}")
        thumbnail_empire(embed, imp)
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="definir_recursos", description="[ADM] Define diretamente os recursos de um jogador")
@app_commands.describe(membro="Jogador", pib="Novo PIB (-1 para nao alterar)", minerios="Novos minerios (-1 para nao alterar)")
async def slash_definir_recursos(interaction, membro: discord.Member, pib: int = -1, minerios: int = -1):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp = dados["imperios"][id_u]
    if pib      >= 0: imp["pib"]      = pib
    if minerios >= 0: imp["minerios"] = minerios
    registrar_historico(id_u, "Recursos definidos pelo ADM")
    salvar(dados)
    embed = discord.Embed(title="⚙️ Recursos Definidos", color=COR_ALERTA)
    embed.add_field(name="💰 PIB",      value=formatar_creditos(imp["pib"]),    inline=True)
    embed.add_field(name="💎 Minérios", value=formatar_numero(imp["minerios"]), inline=True)
    embed.set_footer(text=f"{RODAPE_ADM} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="definir_fabricas", description="[ADM] Define a quantidade de uma fabrica")
@app_commands.describe(membro="Jogador", fabrica="Tipo", quantidade="Nova quantidade")
@app_commands.choices(fabrica=[
    app_commands.Choice(name="Fabrica Pequena",     value="fabrica_pequena"),
    app_commands.Choice(name="Fabrica Media",       value="fabrica_media"),
    app_commands.Choice(name="Fabrica Grande",      value="fabrica_grande"),
    app_commands.Choice(name="Fabrica Continental", value="fabrica_continental"),
    app_commands.Choice(name="Mundo Forja",         value="mundo_forja"),
])
async def slash_definir_fabricas(interaction, membro: discord.Member, fabrica: str, quantidade: int):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if quantidade < 0:
        return await interaction.response.send_message("Quantidade deve ser >= 0.", ephemeral=True)
    imp   = dados["imperios"][id_u]
    label = PRECO_FABRICAS[fabrica][3]
    imp["fabricas"][fabrica] = quantidade
    registrar_historico(id_u, f"Fábricas definidas: {label} → {quantidade}")
    salvar(dados)
    embed = discord.Embed(title="⚙️ Fábricas Definidas", color=COR_ALERTA)
    embed.add_field(name="🏭 Tipo",       value=label,           inline=True)
    embed.add_field(name="🔢 Quantidade", value=str(quantidade), inline=True)
    embed.set_footer(text=f"{RODAPE_ADM} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="recrutar", description="[ADM] Recruta soldados para um jogador")
@app_commands.describe(membro="Jogador", quantidade="Numero de recrutas")
async def slash_recrutar(interaction, membro: discord.Member, quantidade: int):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if quantidade <= 0:
        return await interaction.response.send_message("Quantidade deve ser positiva.", ephemeral=True)
    imp    = dados["imperios"][id_u]
    limite = int(imp["populacao_total"] * LIMITE_RECRUTAMENTO)
    atual  = imp.get("recrutas", 0)
    if atual + quantidade > limite:
        return await interaction.response.send_message(
            f"Limite atingido!\nMáximo: **{formatar_numero(limite)}** | Disponível: **{formatar_numero(limite - atual)}**", ephemeral=True)
    imp["recrutas"] += quantidade
    registrar_historico(id_u, f"Recrutou {formatar_numero(quantidade)} soldados")
    salvar(dados)
    embed = discord.Embed(title="🪖 Recrutamento Realizado!", color=COR_SUCESSO)
    embed.add_field(name="➕ Recrutados", value=formatar_numero(quantidade),      inline=True)
    embed.add_field(name="🪖 Total",      value=formatar_numero(imp["recrutas"]), inline=True)
    embed.add_field(name="📊 Capacidade", value=f"{formatar_numero(imp['recrutas'])} / {formatar_numero(limite)}", inline=False)
    embed.set_footer(text=f"{RODAPE_ADM} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"🪖 {membro.mention} recebeu reforços!", embed=embed)


@bot.tree.command(name="dar_fabrica", description="[ADM] Da fabricas a um jogador. Mundo Forja exige sacrificio de planeta!")
@app_commands.describe(membro="Jogador", fabrica="Tipo", quantidade="Quantidade a dar (padrão: 1)", planeta_sacrificado="Planeta a sacrificar (só Mundo Forja)")
@app_commands.choices(fabrica=[
    app_commands.Choice(name="Fabrica Pequena",     value="fabrica_pequena"),
    app_commands.Choice(name="Fabrica Media",       value="fabrica_media"),
    app_commands.Choice(name="Fabrica Grande",      value="fabrica_grande"),
    app_commands.Choice(name="Fabrica Continental", value="fabrica_continental"),
    app_commands.Choice(name="Mundo Forja",         value="mundo_forja"),
])
async def slash_dar_fabrica(interaction, membro: discord.Member, fabrica: str, quantidade: int = 1, planeta_sacrificado: str = ""):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if quantidade < 1:
        return await interaction.response.send_message("Quantidade deve ser pelo menos 1.", ephemeral=True)
    imp = dados["imperios"][id_u]
    if fabrica == "mundo_forja":
        planetas = imp.get("planetas", [])
        if not planeta_sacrificado:
            lista = "\n".join(f"• {p}" for p in planetas) or "Nenhum planeta."
            return await interaction.response.send_message(
                f"⚠️ **Mundo Forja exige sacrifício de um planeta!**\n\nPlanetas:\n{lista}", ephemeral=True)
        if planeta_sacrificado not in planetas:
            lista = "\n".join(f"• {p}" for p in planetas) or "Nenhum."
            return await interaction.response.send_message(f"Planeta não encontrado.\n{lista}", ephemeral=True)
        imp["planetas"].remove(planeta_sacrificado)
        registrar_historico(id_u, f"🔥 Planeta {planeta_sacrificado} sacrificado para Mundo Forja")
    imp["fabricas"][fabrica] += quantidade
    label = PRECO_FABRICAS[fabrica][3]
    prod  = PRECO_FABRICAS[fabrica][2]
    registrar_historico(id_u, f"Recebeu {quantidade}× fábrica: {label}")
    salvar(dados)
    desc = f"O planeta **{planeta_sacrificado}** foi consumido pelas fornalhas estelares." if fabrica == "mundo_forja" else "A infraestrutura industrial cresce."
    cor  = COR_PERIGO if fabrica == "mundo_forja" else COR_SUCESSO
    embed = discord.Embed(title="🏭 Fábrica(s) Concedida(s)!", description=desc, color=cor)
    embed.add_field(name="🏗️ Tipo",       value=f"**{label}** (+{prod} min/turno cada)", inline=True)
    embed.add_field(name="🔢 Quantidade",  value=str(quantidade),                         inline=True)
    embed.add_field(name="📦 Total Agora", value=str(imp["fabricas"][fabrica]),           inline=True)
    embed.add_field(name="📈 Prod. Total", value=f"+{imp['fabricas'][fabrica]*prod} min/turno", inline=True)
    if fabrica == "mundo_forja":
        embed.add_field(name="💀 Sacrificado", value=planeta_sacrificado, inline=True)
    embed.set_footer(text=f"{RODAPE_ADM} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"🏭 {membro.mention} recebeu {quantidade}× {label}!", embed=embed)


@bot.tree.command(name="adicionar_planeta", description="[ADM] Adiciona um planeta desconhecido ao imperio")
@app_commands.describe(membro="Jogador", nome="Nome do planeta", tipo="Planeta ou Sistema")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Planeta", value="planeta"),
    app_commands.Choice(name="Sistema", value="sistema"),
])
async def slash_adicionar_planeta(interaction, membro: discord.Member, nome: str, tipo: str):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u  = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp   = dados["imperios"][id_u]
    chave = "planetas" if tipo == "planeta" else "sistemas"
    if nome in imp.get(chave, []):
        return await interaction.response.send_message(f"**{nome}** ja esta registrado.", ephemeral=True)
    imp.setdefault(chave, []).append(nome)
    if tipo == "planeta":
        imp.setdefault("planetas_data", {})[nome] = {"nivel":"desconhecido","tipo":None,"recurso":None}
    registrar_historico(id_u, f"{'Planeta' if tipo == 'planeta' else 'Sistema'} adquirido: {nome}")
    salvar(dados)
    emoji = "❓" if tipo == "planeta" else "🌌"
    embed = discord.Embed(title=f"{emoji}  Território Descoberto!", description=f"{SEP_TERRIT}\n*O cosmos guarda seus segredos...*\n{SEP_TERRIT}", color=COR_TERRITORIO)
    embed.add_field(name=f"{emoji} Descoberto", value=f"**{nome}**", inline=True)
    embed.add_field(name="🔍 Status",            value="Desconhecido — colonize para revelar", inline=True)
    embed.set_image(url=BANNER_TERRIT)
    embed.set_footer(text=f"{RODAPE_TERRIT}  ·  {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"❓ {membro.mention} descobriu um novo território!", embed=embed)
    await atualizar_mapa()


@bot.tree.command(name="revelar_planeta", description="[ADM] Revela o tipo de um planeta ao ser colonizado")
@app_commands.describe(membro="Jogador", nome="Nome do planeta", tipo="Tipo do planeta", recurso="Recurso único (opcional)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="🌾 Agrícola",   value="agricola"),
    app_commands.Choice(name="🏭 Industrial", value="industrial"),
    app_commands.Choice(name="⚔️ Militar",    value="militar"),
    app_commands.Choice(name="💰 Comercial",  value="comercial"),
    app_commands.Choice(name="🔬 Científico", value="cientifico"),
    app_commands.Choice(name="🪨 Ermo",       value="ermo"),
])
async def slash_revelar_planeta(interaction, membro: discord.Member, nome: str, tipo: str, recurso: str = ""):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp = dados["imperios"][id_u]
    if nome not in imp.get("planetas", []):
        return await interaction.response.send_message(f"Planeta **{nome}** nao encontrado.", ephemeral=True)
    imp.setdefault("planetas_data", {})[nome] = {"nivel":"colonia","tipo":tipo,"recurso":recurso or None}
    registrar_historico(id_u, f"🌍 Planeta {nome} revelado: {TIPOS_PLANETA[tipo]['nome']}")
    salvar(dados)
    info_tipo = TIPOS_PLANETA[tipo]
    bonus     = calcular_bonus_planeta(imp["planetas_data"][nome])
    bonus_txt = "\n".join(f"+{v:,} {k}/turno".replace(",",".") for k,v in bonus.items()) if bonus else "Nenhum bônus direto"
    embed = discord.Embed(title=f"{info_tipo['emoji']}  Planeta Revelado!", description=f"{SEP_TERRIT}\n*Os exploradores retornam com notícias do novo mundo.*\n{SEP_TERRIT}", color=COR_TERRITORIO)
    embed.add_field(name="🪐 Planeta",     value=f"**{nome}**",     inline=True)
    embed.add_field(name="🏷️ Tipo",        value=info_tipo["nome"], inline=True)
    embed.add_field(name="🏕️ Nível",       value="Colônia",         inline=True)
    embed.add_field(name="📊 Bônus/Turno", value=bonus_txt,         inline=True)
    if recurso:
        embed.add_field(name="💎 Recurso Único", value=recurso, inline=True)
    embed.add_field(name="📖 Descrição", value=info_tipo["desc"], inline=False)
    embed.set_image(url=BANNER_TERRIT)
    embed.set_footer(text=f"{RODAPE_TERRIT}  ·  {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"{info_tipo['emoji']} {membro.mention} revelou seu planeta!", embed=embed)
    await atualizar_mapa()


@bot.tree.command(name="desenvolver_planeta", description="[ADM] Evolui o nível de um planeta manualmente")
@app_commands.describe(membro="Jogador", nome="Nome do planeta", nivel="Novo nível")
@app_commands.choices(nivel=[
    app_commands.Choice(name="🏕️ Colônia", value="colonia"),
    app_commands.Choice(name="🏙️ Cidade",  value="cidade"),
    app_commands.Choice(name="👑 Capital", value="capital"),
])
async def slash_desenvolver_planeta(interaction, membro: discord.Member, nome: str, nivel: str):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp = dados["imperios"][id_u]
    if nome not in imp.get("planetas_data", {}):
        return await interaction.response.send_message(f"Planeta **{nome}** nao encontrado ou nao revelado.", ephemeral=True)
    if nivel == "capital":
        for n, p in imp["planetas_data"].items():
            if p.get("nivel") == "capital" and n != nome:
                return await interaction.response.send_message(f"❌ Já existe uma Capital: **{n}**!", ephemeral=True)
    imp["planetas_data"][nome]["nivel"] = nivel
    registrar_historico(id_u, f"Planeta {nome} evoluído para {NIVEIS_PLANETA[nivel]['nome']}")
    salvar(dados)
    info_n    = NIVEIS_PLANETA[nivel]
    bonus     = calcular_bonus_planeta(imp["planetas_data"][nome])
    bonus_txt = "\n".join(f"+{v:,} {k}/turno".replace(",",".") for k,v in bonus.items()) if bonus else "Nenhum"
    embed = discord.Embed(title=f"{info_n['emoji']}  Planeta Desenvolvido!", color=COR_SUCESSO)
    embed.add_field(name="🪐 Planeta",     value=nome,           inline=True)
    embed.add_field(name="📈 Novo Nível",  value=info_n["nome"], inline=True)
    embed.add_field(name="📊 Bônus/Turno", value=bonus_txt,      inline=True)
    embed.set_footer(text=f"{RODAPE_ADM}  ·  {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"{info_n['emoji']} {membro.mention} desenvolveu um planeta!", embed=embed)


@bot.tree.command(name="destruir_planeta", description="[ADM] Remove um planeta destruido do imperio")
@app_commands.describe(membro="Jogador", nome="Nome", tipo="Planeta ou Sistema")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Planeta", value="planeta"),
    app_commands.Choice(name="Sistema", value="sistema"),
])
async def slash_destruir_planeta(interaction, membro: discord.Member, nome: str, tipo: str):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u  = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp   = dados["imperios"][id_u]
    chave = "planetas" if tipo == "planeta" else "sistemas"
    lista = imp.get(chave, [])
    if nome not in lista:
        disp = "\n".join(f"• {p}" for p in lista) or "Nenhum."
        return await interaction.response.send_message(f"**{nome}** nao encontrado.\n{disp}", ephemeral=True)
    lista.remove(nome)
    if tipo == "planeta":
        imp.get("planetas_data", {}).pop(nome, None)
    registrar_historico(id_u, f"{'Planeta' if tipo == 'planeta' else 'Sistema'} destruido: {nome}")
    salvar(dados)
    embed = discord.Embed(title="💥  Território Destruído", description=f"{SEP_TERRIT}\n**{nome}** foi apagado para sempre.\n{SEP_TERRIT}", color=COR_PERIGO)
    embed.set_image(url=BANNER_TERRIT)
    embed.set_footer(text=f"{RODAPE_TERRIT}  ·  {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"💥 {membro.mention} perdeu um território!", embed=embed)
    await atualizar_mapa()


@bot.tree.command(name="transferir_planeta", description="[ADM] Transfere planeta/sistema entre imperios")
@app_commands.describe(origem="Jogador de origem", destino="Jogador de destino", nome="Nome", tipo="Planeta ou Sistema")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Planeta", value="planeta"),
    app_commands.Choice(name="Sistema", value="sistema"),
])
async def slash_transferir_planeta(interaction, origem: discord.Member, destino: discord.Member, nome: str, tipo: str):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_orig = str(origem.id)
    id_dest = str(destino.id)
    for m, i in [(origem, id_orig), (destino, id_dest)]:
        if not imperio_existe(i):
            return await interaction.response.send_message(f"{m.mention} nao tem um imperio.", ephemeral=True)
    imp_orig = dados["imperios"][id_orig]
    imp_dest = dados["imperios"][id_dest]
    chave    = "planetas" if tipo == "planeta" else "sistemas"
    if nome not in imp_orig.get(chave, []):
        disp = "\n".join(f"• {p}" for p in imp_orig.get(chave, [])) or "Nenhum."
        return await interaction.response.send_message(f"**{nome}** nao pertence a {origem.display_name}.\n{disp}", ephemeral=True)
    imp_orig[chave].remove(nome)
    imp_dest.setdefault(chave, []).append(nome)
    if tipo == "planeta" and nome in imp_orig.get("planetas_data", {}):
        imp_dest.setdefault("planetas_data", {})[nome] = imp_orig["planetas_data"].pop(nome)
    registrar_historico(id_orig, f"{'Planeta' if tipo=='planeta' else 'Sistema'} transferido: {nome} -> {imp_dest['nome']}")
    registrar_historico(id_dest, f"{'Planeta' if tipo=='planeta' else 'Sistema'} recebido: {nome} de {imp_orig['nome']}")
    salvar(dados)
    emojit = "🪐" if tipo == "planeta" else "🌌"
    embed  = discord.Embed(title=f"{emojit}  Território Transferido", description=f"{SEP_TERRIT}\n*As fronteiras do cosmos se redesenham.*\n{SEP_TERRIT}", color=COR_COMERCIO)
    embed.add_field(name=f"{emojit} Território", value=f"**{nome}**",     inline=True)
    embed.add_field(name="📤 Cedido por",         value=imp_orig["nome"], inline=True)
    embed.add_field(name="📥 Recebido por",       value=imp_dest["nome"], inline=True)
    embed.set_image(url=BANNER_TERRIT)
    embed.set_footer(text=RODAPE_TERRIT)
    await interaction.response.send_message(content=f"{emojit} {origem.mention} → {destino.mention}", embed=embed)
    await atualizar_mapa()


@bot.tree.command(name="dar_recursos", description="[ADM] Da PIB ou minerios a um jogador")
@app_commands.describe(membro="Jogador", pib="Creditos", minerios="Minerios", motivo="Motivo")
async def slash_dar_recursos(interaction, membro: discord.Member, pib: int = 0, minerios: int = 0, motivo: str = "Concessao ADM"):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if pib == 0 and minerios == 0:
        return await interaction.response.send_message("Informe ao menos um valor.", ephemeral=True)
    imp = dados["imperios"][id_u]
    imp["pib"]      += pib
    imp["minerios"] += minerios
    partes = []
    if pib      > 0: partes.append(formatar_creditos(pib))
    if minerios > 0: partes.append(f"{formatar_numero(minerios)} min.")
    registrar_historico(id_u, f"Recebeu {' + '.join(partes)} do ADM - {motivo}")
    salvar(dados)
    embed = discord.Embed(title="🎁 Recursos Concedidos!", color=COR_SUCESSO)
    if pib      > 0: embed.add_field(name="💰 Créditos",  value=formatar_creditos(pib),   inline=True)
    if minerios > 0: embed.add_field(name="💎 Minérios",  value=formatar_numero(minerios), inline=True)
    embed.add_field(name="📝 Motivo",     value=motivo, inline=False)
    embed.add_field(name="📦 Novo Saldo", value=f"💰 {formatar_creditos(imp['pib'])} | 💎 {formatar_numero(imp['minerios'])} min.", inline=False)
    embed.set_footer(text=f"{RODAPE_ADM} · {imp['nome']}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"🎁 {membro.mention} recebeu recursos!", embed=embed)


@bot.tree.command(name="transferir", description="[ADM] Move recursos entre dois jogadores")
@app_commands.describe(origem="Origem", destino="Destino", pib="Creditos", minerios="Minerios", motivo="Motivo")
async def slash_transferir(interaction, origem: discord.Member, destino: discord.Member, pib: int = 0, minerios: int = 0, motivo: str = "Transferencia ADM"):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_orig = str(origem.id)
    id_dest = str(destino.id)
    for m, i in [(origem, id_orig), (destino, id_dest)]:
        if not imperio_existe(i):
            return await interaction.response.send_message(f"{m.mention} nao tem um imperio.", ephemeral=True)
    if pib == 0 and minerios == 0:
        return await interaction.response.send_message("Informe ao menos um valor.", ephemeral=True)
    imp_orig = dados["imperios"][id_orig]
    imp_dest = dados["imperios"][id_dest]
    sem = []
    if pib      > 0 and imp_orig["pib"]      < pib:      sem.append("Créditos insuficientes")
    if minerios > 0 and imp_orig["minerios"] < minerios: sem.append("Minérios insuficientes")
    if sem:
        return await interaction.response.send_message(f"{origem.display_name}: " + ", ".join(sem), ephemeral=True)
    imp_orig["pib"]      -= pib
    imp_orig["minerios"] -= minerios
    imp_dest["pib"]      += pib
    imp_dest["minerios"] += minerios
    partes = []
    if pib      > 0: partes.append(formatar_creditos(pib))
    if minerios > 0: partes.append(f"{formatar_numero(minerios)} min.")
    txt = " + ".join(partes)
    registrar_historico(id_orig, f"Transferiu {txt} -> {imp_dest['nome']} - {motivo}")
    registrar_historico(id_dest, f"Recebeu {txt} de {imp_orig['nome']} - {motivo}")
    salvar(dados)
    embed = discord.Embed(title="🔀 Transferência Realizada!", color=COR_COMERCIO)
    embed.add_field(name="📤 De",   value=imp_orig["nome"], inline=True)
    embed.add_field(name="📥 Para", value=imp_dest["nome"], inline=True)
    if pib      > 0: embed.add_field(name="💰 Créditos", value=formatar_creditos(pib),    inline=True)
    if minerios > 0: embed.add_field(name="💎 Minérios", value=formatar_numero(minerios),  inline=True)
    embed.add_field(name="📝 Motivo", value=motivo, inline=False)
    embed.set_footer(text=RODAPE_PADRAO)
    await interaction.response.send_message(content=f"🔀 {origem.mention} → {destino.mention}", embed=embed)


@bot.tree.command(name="remover_imperio", description="[ADM] Remove permanentemente o imperio de um jogador")
async def slash_remover_imperio(interaction, membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    nome_imp = dados["imperios"][id_u]["nome"]
    del dados["imperios"][id_u]
    salvar(dados)
    await interaction.response.send_message(f"🗑️ O império **{nome_imp}** de {membro.mention} foi removido.")


@bot.tree.command(name="evento", description="[ADM] Dispara um evento global")
@app_commands.describe(tipo="Tipo", valor="Valor", descricao="Descricao")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Bonus de PIB",      value="bonus_pib"),
    app_commands.Choice(name="Perda de PIB",      value="perda_pib"),
    app_commands.Choice(name="Bonus de Minerios", value="bonus_minerios"),
    app_commands.Choice(name="Perda de Minerios", value="perda_minerios"),
    app_commands.Choice(name="Bonus pct PIB",     value="bonus_pib_pct"),
    app_commands.Choice(name="Perda pct PIB",     value="perda_pib_pct"),
])
async def slash_evento(interaction, tipo: str, valor: int, descricao: str = "Evento global"):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    if not dados["imperios"]:
        return await interaction.response.send_message("Nenhum imperio.", ephemeral=True)
    if valor <= 0:
        return await interaction.response.send_message("Valor deve ser positivo.", ephemeral=True)
    for id_u, imp in dados["imperios"].items():
        if   tipo == "bonus_pib":      imp["pib"]      += valor
        elif tipo == "perda_pib":      imp["pib"]       = max(0, imp["pib"] - valor)
        elif tipo == "bonus_minerios": imp["minerios"] += valor
        elif tipo == "perda_minerios": imp["minerios"]  = max(0, imp["minerios"] - valor)
        elif tipo == "bonus_pib_pct":  imp["pib"]      += int(imp["pib"] * valor / 100)
        elif tipo == "perda_pib_pct":  imp["pib"]       = max(0, imp["pib"] - int(imp["pib"] * valor / 100))
        registrar_historico(id_u, f"Evento: {descricao}")
    salvar(dados)
    emojis = {"bonus_pib":"💰","perda_pib":"💸","bonus_minerios":"💎","perda_minerios":"💣","bonus_pib_pct":"📈","perda_pib_pct":"📉"}
    emoji  = emojis.get(tipo, "🌐")
    cor    = COR_EVENTO_BOM if "bonus" in tipo else COR_EVENTO_MAU
    embed  = discord.Embed(title=f"{emoji}  Transmissão de Emergência Galáctica", description=f"{SEP_EVENTO}\n**{descricao}**\n{SEP_EVENTO}", color=cor)
    embed.add_field(name="🌍 Impérios Afetados", value=f"`{len(dados['imperios'])}`", inline=True)
    embed.add_field(name="📡 Tipo",              value=tipo.replace("_"," ").title(),  inline=True)
    embed.set_image(url=BANNER_EVENTO)
    embed.set_footer(text=RODAPE_EVENTO)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="sancao", description="[ADM] Bloqueia um jogador de usar loja e mineração por X turnos")
@app_commands.describe(membro="Jogador", turnos="Turnos (0 para remover)", motivo="Motivo")
async def slash_sancao(interaction, membro: discord.Member, turnos: int, motivo: str = "Decisão do Conselho"):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    imp = dados["imperios"][id_u]
    if turnos <= 0:
        imp.pop("sancao", None)
        registrar_historico(id_u, "Sanção removida pelo Conselho")
        salvar(dados)
        embed = discord.Embed(title="⚖️  Sanção Removida", description=f"**{imp['nome']}** foi absolvido.", color=COR_SUCESSO)
        embed.set_footer(text=RODAPE_ADM)
        thumbnail_empire(embed, imp)
        return await interaction.response.send_message(content=f"⚖️ {membro.mention} foi absolvido.", embed=embed)
    imp["sancao"] = {"turnos": turnos, "motivo": motivo}
    registrar_historico(id_u, f"Sancionado por {turnos} turno(s) — {motivo}")
    salvar(dados)
    embed = discord.Embed(title="🚫  Sanção Imperial Decretada", description=f"{SEP_EVENTO}\n**{imp['nome']}** foi sancionado.\n{SEP_EVENTO}", color=COR_PERIGO)
    embed.add_field(name="⏳ Duração", value=f"`{turnos}` turno(s)", inline=True)
    embed.add_field(name="📝 Motivo",  value=motivo,                 inline=True)
    embed.add_field(name="🚫 Efeitos", value="Loja e mineração bloqueadas", inline=False)
    embed.set_footer(text=RODAPE_ADM)
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(content=f"🚫 {membro.mention} foi sancionado!", embed=embed)


@bot.tree.command(name="censo", description="[ADM] Relatório geral de todos os impérios")
async def slash_censo(interaction):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    if not dados["imperios"]:
        return await interaction.response.send_message("Nenhum império registrado.", ephemeral=True)
    total_pib      = sum(i.get("pib",0)            for i in dados["imperios"].values())
    total_minerios = sum(i.get("minerios",0)        for i in dados["imperios"].values())
    total_recrutas = sum(i.get("recrutas",0)        for i in dados["imperios"].values())
    total_pop      = sum(i.get("populacao_total",0) for i in dados["imperios"].values())
    total_planetas = sum(len(i.get("planetas",[]))  for i in dados["imperios"].values())
    total_sistemas = sum(len(i.get("sistemas",[]))  for i in dados["imperios"].values())
    total_fab      = sum(sum(i.get("fabricas",{}).values()) for i in dados["imperios"].values())
    total_projetos = sum(len(i.get("projetos",{}))  for i in dados["imperios"].values())
    total_unidades = sum(sum(i.get(k,0) for k in LOJA_UNIDADES) for i in dados["imperios"].values())
    sancionados    = [i["nome"] for i in dados["imperios"].values() if i.get("sancao")]
    vassalos_total = sum(len(i.get("vassalos",[])) for i in dados["imperios"].values())
    linhas_imp = []
    for id_u, imp in sorted(dados["imperios"].items(), key=lambda x: x[1].get("pib",0), reverse=True):
        tag  = " 🚫" if imp.get("sancao") else ""
        tagv = " 🔗" if imp.get("vassalagem") else ""
        linhas_imp.append(f"**{imp['nome']}**{tag}{tagv}  ·  💰 {formatar_creditos(imp['pib'])}  ·  ⚔️ {formatar_numero(sum(imp.get(k,0) for k in LOJA_UNIDADES))} un.  ·  🪐 {len(imp.get('planetas',[]))} planetas")
    embed = discord.Embed(title="📊  Censo Galáctico  —  Relatório Geral", description=f"{SEP_PADRAO}\n" + "\n".join(linhas_imp) + f"\n{SEP_PADRAO}", color=COR_PRIMARIA)
    embed.add_field(name="🏛️ Impérios",  value=f"`{len(dados['imperios'])}`",   inline=True)
    embed.add_field(name="💰 PIB Total",  value=formatar_creditos(total_pib),    inline=True)
    embed.add_field(name="💎 Min. Total", value=formatar_numero(total_minerios),  inline=True)
    embed.add_field(name="👥 Pop. Total", value=formatar_numero(total_pop),       inline=True)
    embed.add_field(name="🪖 Recrutas",   value=formatar_numero(total_recrutas),  inline=True)
    embed.add_field(name="⚔️ Unidades",   value=formatar_numero(total_unidades),  inline=True)
    embed.add_field(name="🏭 Fábricas",   value=f"`{total_fab}`",               inline=True)
    embed.add_field(name="🪐 Planetas",   value=f"`{total_planetas}`",           inline=True)
    embed.add_field(name="🌌 Sistemas",   value=f"`{total_sistemas}`",           inline=True)
    embed.add_field(name="🔭 Projetos",   value=f"`{total_projetos}` pendentes", inline=True)
    embed.add_field(name="🔗 Vassalos",   value=f"`{vassalos_total}`",           inline=True)
    if sancionados:
        embed.add_field(name="🚫 Sancionados", value=", ".join(sancionados), inline=False)
    embed.set_footer(text=f"{RODAPE_ADM}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="definir_tech", description="[ADM] Define o nível de tecnologia de um jogador")
@app_commands.describe(membro="Jogador", area="Área tecnológica", nivel="Nível desejado (0-10)")
@app_commands.choices(area=[
    app_commands.Choice(name="Militar",    value="militar"),
    app_commands.Choice(name="Industrial", value="industrial"),
    app_commands.Choice(name="Economico",  value="economico"),
    app_commands.Choice(name="Espacial",   value="espacial"),
    app_commands.Choice(name="Espionagem", value="espionagem"),
])
async def slash_definir_tech(interaction, membro: discord.Member, area: str, nivel: int):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissao.", ephemeral=True)
    id_u = str(membro.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message(f"{membro.mention} nao tem um imperio.", ephemeral=True)
    if nivel < 0 or nivel > NIVEL_MAX_TECH:
        return await interaction.response.send_message(f"Nível deve ser entre 0 e {NIVEL_MAX_TECH}.", ephemeral=True)
    imp = dados["imperios"][id_u]
    imp.setdefault("tecnologias", {a: 0 for a in AREAS_TECH})[area] = nivel
    nome_nv = NOMES_NIVEIS[nivel]
    registrar_historico(id_u, f"{AREAS_TECH[area]['emoji']} {AREAS_TECH[area]['nome']} → Nível {nivel} pelo ADM")
    salvar(dados)
    info  = AREAS_TECH[area]
    barra = "█" * nivel + "░" * (NIVEL_MAX_TECH - nivel)
    embed = discord.Embed(title="⚙️  Tecnologia Definida", description=f"**{info['nome']}** de **{imp['nome']}** foi alterada.", color=info["cor"])
    embed.add_field(name=f"{info['emoji']} Área",  value=info["nome"],               inline=True)
    embed.add_field(name="📈 Nível",               value=f"`{nivel}` — *{nome_nv}*", inline=True)
    embed.add_field(name="📊 Progresso",           value=f"`[{barra}]`",             inline=False)
    embed.add_field(name="✨ Bônus Ativo",          value=info["bonus"],              inline=True)
    embed.set_footer(text=RODAPE_ADM)
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(embed=embed)


# ==============================
# DIPLOMACIA ADM
# ==============================

@bot.tree.command(name="formar_alianca", description="[ADM] Formaliza uma aliança entre dois impérios")
@app_commands.describe(imp1="Primeiro membro", imp2="Segundo membro", nome="Nome da aliança")
async def slash_formar_alianca(interaction, imp1: discord.Member, imp2: discord.Member, nome: str = ""):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    id1, id2 = str(imp1.id), str(imp2.id)
    for mid in [id1, id2]:
        if not imperio_existe(mid):
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
    imp_1 = dados["imperios"][id1]
    imp_2 = dados["imperios"][id2]
    imp_1.setdefault("aliancas", [])
    imp_2.setdefault("aliancas", [])
    if id2 not in imp_1["aliancas"]: imp_1["aliancas"].append(id2)
    if id1 not in imp_2["aliancas"]: imp_2["aliancas"].append(id1)
    nome_alianca = nome or f"Aliança {imp_1['nome']} & {imp_2['nome']}"

    # Guarda o nome da aliança em ambos os impérios
    if "nome_aliancas" not in imp_1: imp_1["nome_aliancas"] = {}
    if "nome_aliancas" not in imp_2: imp_2["nome_aliancas"] = {}
    imp_1["nome_aliancas"][id2] = nome_alianca
    imp_2["nome_aliancas"][id1] = nome_alianca

    registrar_historico(id1, f"🤝 Aliança formada com {imp_2['nome']}: {nome_alianca}")
    registrar_historico(id2, f"🤝 Aliança formada com {imp_1['nome']}: {nome_alianca}")
    salvar(dados)

    # Lista todos os membros da aliança
    todos_membros = [imp_1["nome"], imp_2["nome"]]

    embed = discord.Embed(
        title=f"🤝  {nome_alianca}",
        description=f"{SEP_PADRAO}\n*Uma nova aliança foi forjada no cosmos.*\n{SEP_PADRAO}",
        color=0x1E3A5F,
    )
    embed.add_field(name="📜 Nome da Aliança", value=f"**{nome_alianca}**", inline=False)
    embed.add_field(name="🏛️ Membros Fundadores",
                    value="\n".join(f"🤝 **{m}**" for m in todos_membros), inline=False)
    embed.add_field(name="💡 Dica",
                    value="Use `/adicionar_membro_alianca` para adicionar mais impérios!", inline=False)
    embed.set_footer(text=RODAPE_ADM)
    await interaction.response.send_message(content=f"🤝 {imp1.mention} e {imp2.mention}!", embed=embed)


@bot.tree.command(name="adicionar_membro_alianca", description="[ADM] Adiciona um novo membro a uma aliança existente")
@app_commands.describe(membro_existente="Membro já na aliança", novo_membro="Novo império a entrar")
async def slash_adicionar_membro_alianca(interaction, membro_existente: discord.Member, novo_membro: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    id_exist = str(membro_existente.id)
    id_novo  = str(novo_membro.id)
    for mid in [id_exist, id_novo]:
        if not imperio_existe(mid):
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
    imp_exist = dados["imperios"][id_exist]
    imp_novo  = dados["imperios"][id_novo]

    aliados_exist = imp_exist.get("aliancas", [])
    if not aliados_exist:
        return await interaction.response.send_message(
            f"**{imp_exist['nome']}** não tem nenhuma aliança ativa.", ephemeral=True)

    # Pega o nome da aliança do membro existente (pega o primeiro)
    nomes_aliancas = imp_exist.get("nome_aliancas", {})
    nome_alianca   = list(nomes_aliancas.values())[0] if nomes_aliancas else f"Aliança de {imp_exist['nome']}"

    # Adiciona o novo membro a todos os aliados existentes
    imp_novo.setdefault("aliancas", [])
    imp_novo.setdefault("nome_aliancas", {})

    membros_nomes = [imp_exist["nome"]]
    for id_aliado in aliados_exist:
        if id_aliado not in dados["imperios"]: continue
        imp_aliado = dados["imperios"][id_aliado]
        imp_aliado.setdefault("aliancas", [])
        imp_aliado.setdefault("nome_aliancas", {})
        if id_novo not in imp_aliado["aliancas"]:
            imp_aliado["aliancas"].append(id_novo)
            imp_aliado["nome_aliancas"][id_novo] = nome_alianca
        if id_aliado not in imp_novo["aliancas"]:
            imp_novo["aliancas"].append(id_aliado)
            imp_novo["nome_aliancas"][id_aliado] = nome_alianca
        membros_nomes.append(imp_aliado["nome"])

    # Liga o existente com o novo
    if id_novo not in imp_exist["aliancas"]:
        imp_exist["aliancas"].append(id_novo)
        imp_exist["nome_aliancas"][id_novo] = nome_alianca
    if id_exist not in imp_novo["aliancas"]:
        imp_novo["aliancas"].append(id_exist)
        imp_novo["nome_aliancas"][id_exist] = nome_alianca

    membros_nomes.append(imp_novo["nome"])
    membros_unicos = list(dict.fromkeys(membros_nomes))  # remove duplicatas

    registrar_historico(id_novo,  f"🤝 Entrou na aliança: {nome_alianca}")
    registrar_historico(id_exist, f"🤝 {imp_novo['nome']} entrou na aliança: {nome_alianca}")
    salvar(dados)

    embed = discord.Embed(
        title=f"🤝  Novo Membro na Aliança!",
        description=f"{SEP_PADRAO}\n**{imp_novo['nome']}** entrou em **{nome_alianca}**.\n{SEP_PADRAO}",
        color=0x1E3A5F,
    )
    embed.add_field(name="📜 Aliança",   value=f"**{nome_alianca}**", inline=False)
    embed.add_field(name="🏛️ Membros",
                    value="\n".join(f"🤝 **{m}**" for m in membros_unicos), inline=False)
    embed.set_footer(text=RODAPE_ADM)
    await interaction.response.send_message(content=f"🤝 {novo_membro.mention} entrou na aliança!", embed=embed)


@bot.tree.command(name="dissolver_alianca", description="[ADM] Dissolve a aliança entre dois impérios")
@app_commands.describe(imp1="Primeiro membro", imp2="Segundo membro")
async def slash_dissolver_alianca(interaction, imp1: discord.Member, imp2: discord.Member):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    id1, id2 = str(imp1.id), str(imp2.id)
    for mid in [id1, id2]:
        if not imperio_existe(mid):
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
    imp_1 = dados["imperios"][id1]
    imp_2 = dados["imperios"][id2]
    if id2 in imp_1.get("aliancas",[]): imp_1["aliancas"].remove(id2)
    if id1 in imp_2.get("aliancas",[]): imp_2["aliancas"].remove(id1)
    registrar_historico(id1, f"💔 Aliança dissolvida com {imp_2['nome']}")
    registrar_historico(id2, f"💔 Aliança dissolvida com {imp_1['nome']}")
    salvar(dados)
    embed = discord.Embed(title="💔  Aliança Dissolvida", description=f"**{imp_1['nome']}** e **{imp_2['nome']}** seguem caminhos separados.", color=COR_PERIGO)
    embed.set_footer(text=RODAPE_ADM)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="registrar_tratado", description="[ADM] Registra um tratado formal entre impérios")
@app_commands.describe(imp1="Primeiro signatário", imp2="Segundo signatário", nome="Nome do tratado", termos="Termos completos")
async def slash_registrar_tratado(interaction, imp1: discord.Member, imp2: discord.Member, nome: str, termos: str):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    id1, id2 = str(imp1.id), str(imp2.id)
    for mid in [id1, id2]:
        if not imperio_existe(mid):
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
    imp_1 = dados["imperios"][id1]
    imp_2 = dados["imperios"][id2]
    registrar_historico(id1, f"📜 Tratado firmado com {imp_2['nome']}: {nome}")
    registrar_historico(id2, f"📜 Tratado firmado com {imp_1['nome']}: {nome}")
    salvar(dados)
    embed = discord.Embed(title=f"📜  Tratado Firmado  ·  {nome}", description=f"{SEP_PADRAO}\n*O Conselho Galáctico registra o acordo.*\n{SEP_PADRAO}", color=0x0C4A6E)
    embed.add_field(name="🏛️ Signatários", value=f"**{imp_1['nome']}**  ×  **{imp_2['nome']}**", inline=False)
    embed.add_field(name="📋 Termos",      value=termos, inline=False)
    embed.add_field(name="📅 Data",        value=datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
    embed.set_footer(text=RODAPE_ADM)
    await interaction.response.send_message(content=f"📜 {imp1.mention} e {imp2.mention}", embed=embed)


@bot.tree.command(name="evento_narrativo", description="[ADM] Dispara evento global com imagem e efeitos avançados")
@app_commands.describe(titulo="Título", descricao="Descrição narrativa", tipo="Tipo de efeito", valor="Porcentagem", imagem="URL da imagem (opcional)")
@app_commands.choices(tipo=[
    app_commands.Choice(name="💰 Boom econômico (+PIB%)",       value="bonus_pib_pct"),
    app_commands.Choice(name="💸 Crise econômica (-PIB%)",      value="perda_pib_pct"),
    app_commands.Choice(name="💎 Descoberta mineral (+min)",    value="bonus_minerios"),
    app_commands.Choice(name="💣 Catástrofe (-min)",            value="perda_minerios"),
    app_commands.Choice(name="👥 Explosão demográfica (+pop%)", value="bonus_pop"),
    app_commands.Choice(name="☠️ Plague (-pop%)",               value="perda_pop"),
    app_commands.Choice(name="🌐 Neutro (só narrativa)",        value="neutro"),
])
async def slash_evento_narrativo(interaction, titulo: str, descricao: str, tipo: str, valor: int = 0, imagem: str = ""):
    if not tem_permissao_adm(interaction):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)
    if not dados["imperios"]:
        return await interaction.response.send_message("Nenhum império registrado.", ephemeral=True)
    efeito_txt = ""
    for id_u, imp in dados["imperios"].items():
        if   tipo == "bonus_pib_pct":  imp["pib"]            += int(imp["pib"]*valor/100);                                              efeito_txt = f"+{valor}% PIB"
        elif tipo == "perda_pib_pct":  imp["pib"]             = max(0,imp["pib"]-int(imp["pib"]*valor/100));                            efeito_txt = f"-{valor}% PIB"
        elif tipo == "bonus_minerios": imp["minerios"]        += valor;                                                                  efeito_txt = f"+{formatar_numero(valor)} min."
        elif tipo == "perda_minerios": imp["minerios"]         = max(0,imp["minerios"]-valor);                                           efeito_txt = f"-{formatar_numero(valor)} min."
        elif tipo == "bonus_pop":      imp["populacao_total"] += int(imp["populacao_total"]*valor/100);                                  efeito_txt = f"+{valor}% pop."
        elif tipo == "perda_pop":      imp["populacao_total"]  = max(1000,imp["populacao_total"]-int(imp["populacao_total"]*valor/100)); efeito_txt = f"-{valor}% pop."
        if tipo != "neutro":
            registrar_historico(id_u, f"🌐 Evento: {titulo} — {efeito_txt}")
    salvar(dados)
    cor_evento = 0x1E3A5F if "bonus" in tipo else (0x4C0519 if tipo != "neutro" else COR_NEUTRO)
    emoji_tipo = {"bonus_pib_pct":"💰","perda_pib_pct":"💸","bonus_minerios":"💎","perda_minerios":"💣","bonus_pop":"👥","perda_pop":"☠️","neutro":"🌐"}
    embed = discord.Embed(title=f"{emoji_tipo.get(tipo,'🌐')}  {titulo}", description=f"{SEP_EVENTO}\n*{descricao}*\n{SEP_EVENTO}", color=cor_evento)
    if efeito_txt:
        embed.add_field(name="📊 Efeito Global",     value=efeito_txt,                   inline=True)
        embed.add_field(name="🌍 Impérios Afetados", value=str(len(dados["imperios"])), inline=True)
    embed.set_footer(text=f"{RODAPE_EVENTO}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    embed.set_image(url=imagem if imagem.startswith("http") else BANNER_EVENTO)
    await interaction.response.send_message(content="@everyone", embed=embed)


# ==============================
# COMANDOS DE JOGADOR
# ==============================

@bot.command(name="perfil")
async def perfil(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} nao tem um imperio registrado.")
    imp = dados["imperios"][id_u]
    garantir_campos(imp)
    cor          = get_cor(imp)
    fab_txt      = "\n".join(f"{k.replace('_',' ').title()}: **{v}**" for k, v in imp.get("fabricas",{}).items() if v > 0) or "Nenhuma"
    unidades_txt = "\n".join(f"{nome_bonito(k)}: **{formatar_numero(imp.get(k,0))}**" for k in LOJA_UNIDADES)
    techs        = imp.get("tecnologias", {a: 0 for a in AREAS_TECH})
    tech_txt     = "  ".join(f"{AREAS_TECH[a]['emoji']} `{techs.get(a,0)}`" for a in AREAS_TECH)
    embed = discord.Embed(title=f"🌌  {imp['nome']}", description=f"*{imp.get('descricao','Sem descrição — um império envolto em mistério.')}*\n{SEP_PADRAO}", color=cor)
    embed.add_field(name="💰 Economia",         value=f"**PIB:** {formatar_creditos(imp['pib'])}\n**💎 Minérios:** {formatar_numero(imp['minerios'])}", inline=True)
    embed.add_field(name="👥 População",        value=f"**Total:** {formatar_numero(imp['populacao_total'])}\n**🪖 Recrutas:** {formatar_numero(imp['recrutas'])}", inline=True)
    embed.add_field(name="🗺️ Território",       value=f"🪐 **{len(imp.get('planetas',[]))}** planeta(s)  ·  🌌 **{len(imp.get('sistemas',[]))}** sistema(s)", inline=False)
    embed.add_field(name="⚔️ Forças Militares", value=unidades_txt, inline=True)
    embed.add_field(name="🏭 Fábricas",         value=fab_txt,      inline=True)
    embed.add_field(name="🔭 Projetos",         value=f"**{len(imp.get('projetos',{}))}** em andamento", inline=False)
    embed.add_field(name="🔬 Tecnologias",      value=tech_txt, inline=False)
    vassalagem = imp.get("vassalagem")
    if vassalagem:
        icons = {"vassalo":"🔗","fantoche":"🤖","ocupado":"🏴"}
        ic = icons.get(vassalagem["tipo"],"🔗")
        embed.add_field(name=f"{ic} Status Político", value=f"{ic} **{vassalagem['tipo'].title()}** de **{vassalagem['nome_soberano']}**  ·  💸 {vassalagem['tributo']}%/turno", inline=False)
    elif imp.get("vassalos"):
        nv = [dados["imperios"].get(v,{}).get("nome","?") for v in imp["vassalos"] if v in dados["imperios"]]
        if nv:
            embed.add_field(name="👑 Vassalos", value="  ·  ".join(f"🔗 {n}" for n in nv), inline=False)
    # CORREÇÃO 3: banner gerado em vez de URL externa
    thumbnail_empire(embed, imp)
    banner = gerar_banner_imperio(imp)
    if banner:
        f = discord.File(banner, filename="banner.png")
        embed.set_image(url="attachment://banner.png")
        embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
        await ctx.send(file=f, embed=embed)
    else:
        embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
        await ctx.send(embed=embed)


@bot.command(name="status")
async def status(ctx):
    await perfil(ctx)


@bot.command(name="ficha")
async def ficha(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} nao tem um imperio registrado.")
    imp        = dados["imperios"][id_u]
    garantir_campos(imp)
    cor        = get_cor(imp)
    prod_total = sum(imp["fabricas"].get(k,0) * v for k,v in TIPOS_FABRICAS.items())
    fab_linhas = [f"{PRECO_FABRICAS[k][3]}: **{qtd}** (+{PRECO_FABRICAS[k][2]*qtd}/turno)" for k in PRECO_FABRICAS if (qtd := imp["fabricas"].get(k,0)) > 0]
    unidades_txt = "\n".join(f"{nome_bonito(k)}: **{formatar_numero(imp.get(k,0))}**" for k in LOJA_UNIDADES)
    proj_txt   = "\n".join(f"• {p}" for p in imp.get("projetos",{})) or "Nenhum"
    planetas   = imp.get("planetas", [])
    sistemas   = imp.get("sistemas", [])
    techs      = imp.get("tecnologias", {a: 0 for a in AREAS_TECH})
    tech_txt   = "  ".join(f"{AREAS_TECH[a]['emoji']} `{techs.get(a,0)}`" for a in AREAS_TECH)
    embed = discord.Embed(title=f"📋  Dossiê Imperial  ·  {imp['nome']}", description=f"*{imp.get('descricao','Sem descrição.')}*\n{SEP_PADRAO}", color=cor)
    embed.add_field(name="💰 Economia",
        value=f"**PIB:** {formatar_creditos(imp['pib'])}\n**💎 Minérios:** {formatar_numero(imp['minerios'])}\n**📈 Produção:** +{formatar_numero(prod_total)}/turno", inline=True)
    embed.add_field(name="👥 População",
        value=f"**Total:** {formatar_numero(imp['populacao_total'])}\n**🪖 Recrutas:** {formatar_numero(imp['recrutas'])}\n**📊 Limite:** {formatar_numero(int(imp['populacao_total']*LIMITE_RECRUTAMENTO))}", inline=True)
    embed.add_field(name="\u200b", value=SEP_MILITAR, inline=False)
    embed.add_field(name="⚔️ Forças Militares",   value=unidades_txt, inline=True)
    embed.add_field(name="🏭 Complexo Industrial", value="\n".join(fab_linhas) or "Nenhuma", inline=True)
    embed.add_field(name="\u200b", value=SEP_TERRIT, inline=False)
    embed.add_field(name=f"🪐 Planetas [{len(planetas)}]", value="\n".join(f"• {p}" for p in planetas) or "Nenhum", inline=True)
    embed.add_field(name=f"🌌 Sistemas [{len(sistemas)}]", value="\n".join(f"• {s}" for s in sistemas) or "Nenhum", inline=True)
    embed.add_field(name=f"🔭 Projetos [{len(imp.get('projetos',{}))}]", value=proj_txt, inline=False)
    embed.add_field(name="🔬 Tecnologias", value=tech_txt, inline=False)
    # CORREÇÃO 3: banner gerado em vez de URL externa
    thumbnail_empire(embed, imp)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
    banner = gerar_banner_imperio(imp)
    if banner:
        f = discord.File(banner, filename="banner.png")
        embed.set_image(url="attachment://banner.png")
        await ctx.send(file=f, embed=embed)
    else:
        await ctx.send(embed=embed)


# CORREÇÃO 2: !setar_brasao abre modal
@bot.command(name="setar_brasao")
async def setar_brasao(ctx):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    # Modais só funcionam em slash commands / interactions, não em prefix commands
    # Por isso criamos um slash command auxiliar e orientamos o usuário
    await ctx.send(
        f"Para alterar o brasão use o comando `/alterar_brasao` — ele abre uma tela para você colar a URL. "
        f"Ou use `!setar_brasao_url <url>` se preferir digitar direto.",
        ephemeral=False
    )

@bot.command(name="setar_brasao_url")
async def setar_brasao_url(ctx, url: str = None):
    """Fallback para quem preferir digitar a URL direto no chat."""
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    if not url or not url.startswith("http"):
        return await ctx.send("Uso: `!setar_brasao_url <url>`")
    dados["imperios"][id_u]["brasao"] = url
    salvar(dados)
    imp = dados["imperios"][id_u]
    embed = discord.Embed(title="🎨 Brasão Atualizado!", color=COR_SUCESSO)
    embed.set_image(url=url)
    embed.set_thumbnail(url=url)
    embed.set_footer(text=RODAPE_PADRAO)
    await ctx.send(embed=embed)

@bot.tree.command(name="alterar_brasao", description="Altera o brasão do seu império")
async def slash_alterar_brasao(interaction):
    id_u = str(interaction.user.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message("Você não tem um império registrado.", ephemeral=True)
    await interaction.response.send_modal(ModalBrasao(id_u))


@bot.command(name="ranking")
async def ranking(ctx):
    if not dados["imperios"]:
        return await ctx.send("Nenhum imperio registrado.")
    ordenados = sorted(dados["imperios"].items(), key=lambda x: x[1].get("pib",0), reverse=True)[:10]
    linhas    = []
    medalhas  = ["🥇","🥈","🥉"]
    for i, (id_u, imp) in enumerate(ordenados):
        prefixo = medalhas[i] if i < 3 else f"`{i+1}.`"
        linhas.append(f"{prefixo} **{imp['nome']}**\n　💰 {formatar_creditos(imp['pib'])} · ⚔️ {formatar_numero(sum(imp.get(k,0) for k in LOJA_UNIDADES))} un.")
    embed = discord.Embed(title="👑  Supremacia Galáctica  —  Ranking Econômico", description=f"{SEP_PADRAO}\n\n"+"\n\n".join(linhas)+f"\n\n{SEP_PADRAO}", color=COR_OURO)
    embed.set_image(url=BANNER_RANKING)
    embed.set_footer(text=f"⬡ Sistema Galáctico  ·  Top {len(ordenados)} por PIB")
    await ctx.send(embed=embed)


@bot.command(name="ranking_militar")
async def ranking_militar(ctx):
    if not dados["imperios"]:
        return await ctx.send("Nenhum imperio registrado.")
    def poder(imp):
        return sum(imp.get(k,0)*LOJA_UNIDADES[k][1] for k in LOJA_UNIDADES) + imp.get("recrutas",0)
    ordenados = sorted(dados["imperios"].items(), key=lambda x: poder(x[1]), reverse=True)[:10]
    linhas    = []
    medalhas  = ["🥇","🥈","🥉"]
    for i, (id_u, imp) in enumerate(ordenados):
        prefixo = medalhas[i] if i < 3 else f"`{i+1}.`"
        linhas.append(f"{prefixo} **{imp['nome']}**\n　⚔️ {formatar_numero(sum(imp.get(k,0) for k in LOJA_UNIDADES))} un. · 💥 {formatar_numero(poder(imp))} pts")
    embed = discord.Embed(title="⚔️  Supremacia Galáctica  —  Ranking Militar", description=f"{SEP_MILITAR}\n\n"+"\n\n".join(linhas)+f"\n\n{SEP_MILITAR}", color=COR_MILITAR)
    embed.set_image(url=BANNER_MILITAR)
    embed.set_footer(text=f"{RODAPE_MILITAR}  ·  Top {len(ordenados)} por poder de combate")
    await ctx.send(embed=embed)


@bot.command(name="poder_militar")
async def poder_militar(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} nao tem um imperio registrado.")
    imp    = dados["imperios"][id_u]
    linhas = []
    total  = 0
    for k, (c_min, c_pib, desc) in LOJA_UNIDADES.items():
        qtd   = imp.get(k, 0)
        pts   = qtd * c_pib
        total += pts
        linhas.append(f"{ICONS_UNIDADES.get(k,'⚔️')} {nome_bonito(k)}: {formatar_numero(qtd)} × {c_pib} = **{formatar_numero(pts)} pts**")
    rec_pts = imp.get("recrutas", 0)
    total  += rec_pts
    linhas.append(f"🪖 Recrutas: {formatar_numero(rec_pts)} pts")
    embed = discord.Embed(title=f"⚔️  Poder Militar  ·  {imp['nome']}", description="\n".join(linhas), color=get_cor(imp))
    embed.add_field(name="💥 Poder Total", value=f"**{formatar_numero(total)} pts**", inline=False)
    embed.set_footer(text=f"{RODAPE_MILITAR}  ·  {alvo.display_name}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="meus_projetos")
async def meus_projetos(ctx):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Voce nao tem um imperio registrado.")
    projetos = dados["imperios"][id_u].get("projetos", {})
    if not projetos:
        return await ctx.send("📭 Nenhum projeto registrado.")
    imp = dados["imperios"][id_u]
    for nome_p, info in projetos.items():
        pm = info.get("poder_militar", 0)
        embed = discord.Embed(title=f"🔭 {nome_p}", description=info.get("descricao",""), color=COR_ALERTA)
        embed.add_field(name="💎 Minerios", value=formatar_numero(info["custo_minerios"]) + " min.", inline=True)
        embed.add_field(name="💰 Créditos", value=formatar_creditos(info["custo_pib"]),              inline=True)
        if pm > 0:
            embed.add_field(name="⚔️ PM", value=f"+{formatar_numero(pm)}", inline=True)
        embed.set_footer(text=RODAPE_PADRAO)
        thumbnail_empire(embed, imp)
        if info.get("foto","").startswith("http"):
            embed.set_image(url=info["foto"])
        await ctx.send(embed=embed)


@bot.command(name="historico")
async def historico(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} nao tem um imperio registrado.")
    imp     = dados["imperios"][id_u]
    eventos = imp.get("historico", [])
    if not eventos:
        return await ctx.send(f"📭 **{imp['nome']}** ainda não tem eventos registrados.")
    embed = discord.Embed(title=f"📜  Arquivo Imperial  ·  {imp['nome']}", description=f"{SEP_PADRAO}\n"+"\n".join(eventos)+f"\n{SEP_PADRAO}", color=COR_HISTORIA)
    embed.set_footer(text=f"{RODAPE_HISTORIA}  ·  Últimos {len(eventos)} registros")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="tecnologias")
async def tecnologias(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} nao tem um imperio registrado.")
    imp = dados["imperios"][id_u]
    imp.setdefault("tecnologias", {a: 0 for a in AREAS_TECH})
    salvar(dados)
    techs  = imp["tecnologias"]
    linhas = []
    for area, info in AREAS_TECH.items():
        nivel   = techs.get(area, 0)
        nome_nv = NOMES_NIVEIS[nivel] if nivel <= NIVEL_MAX_TECH else "Ascendido"
        barra   = "█" * nivel + "░" * (NIVEL_MAX_TECH - nivel)
        linhas.append(
            f"{info['emoji']} **{info['nome']}** — Nível `{nivel}` — *{nome_nv}*\n"
            f"　`[{barra}]`\n"
            f"　{info['bonus']}"
        )
    embed = discord.Embed(title=f"🔬  Arquivo Tecnológico  ·  {imp['nome']}", description=f"{SEP_PADRAO}\n\n"+"\n\n".join(linhas)+f"\n\n{SEP_PADRAO}", color=get_cor(imp))
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  ADM usa /definir_tech para evoluir")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


# ==============================
# LOJA
# ==============================

@bot.command(name="loja")
async def loja(ctx):
    embed = discord.Embed(title="🛒  Arsenal Galáctico  —  Mercado Imperial", description=f"{SEP_LOJA}\n*Equipe seu império para dominar a galáxia.*\n{SEP_LOJA}", color=COR_PRIMARIA)
    classicas = ["cacas","destroyers","tanques","fragatas"]
    espaciais = ["cruzadores","interceptores","bombardeiros","corvetas"]
    linhas_c  = [f"{ICONS_UNIDADES.get(k,'⚔️')} **{nome_bonito(k)}** — *{LOJA_UNIDADES[k][2]}*\n　💎 `{LOJA_UNIDADES[k][0]}` min.  ·  💰 `{formatar_creditos(LOJA_UNIDADES[k][1])}` cada" for k in classicas]
    linhas_e  = [f"{ICONS_UNIDADES.get(k,'🚀')} **{nome_bonito(k)}** — *{LOJA_UNIDADES[k][2]}*\n　💎 `{LOJA_UNIDADES[k][0]}` min.  ·  💰 `{formatar_creditos(LOJA_UNIDADES[k][1])}` cada" for k in espaciais]
    icons_f   = {"fabrica_pequena":"🔧","fabrica_media":"⚙️","fabrica_grande":"🏗️","fabrica_continental":"🏭","mundo_forja":"🌋"}
    linhas_f  = [f"{icons_f.get(k,'🔩')} **{PRECO_FABRICAS[k][3]}** — `!construir {k}`\n　💎 `{formatar_numero(PRECO_FABRICAS[k][1])}` min.  ·  💰 `{formatar_creditos(PRECO_FABRICAS[k][0])}`  ·  📈 `+{PRECO_FABRICAS[k][2]}/turno`" for k in PRECO_FABRICAS]
    embed.add_field(name="⚔️ ─── Unidades Clássicas ───",      value="\n\n".join(linhas_c), inline=False)
    embed.add_field(name="🚀 ─── Frota Espacial Avançada ───",  value="\n\n".join(linhas_e), inline=False)
    embed.add_field(name="🏭 ─── Infraestrutura Industrial ───", value="\n\n".join(linhas_f), inline=False)
    embed.set_image(url=BANNER_LOJA)
    embed.set_footer(text=f"{RODAPE_LOJA}  ·  !comprar cruzadores 3  |  !construir fabrica_media")
    await ctx.send(embed=embed)




@bot.tree.command(name="comprar", description="Compra unidades militares para o seu império")
@app_commands.describe(unidade="Tipo de unidade", quantidade="Quantidade a comprar")
@app_commands.choices(unidade=[
    app_commands.Choice(name="✈️ Caças — Nave leve de combate",               value="cacas"),
    app_commands.Choice(name="💀 Destroyers — Nave pesada de destruição",     value="destroyers"),
    app_commands.Choice(name="🛡️ Tanques — Blindado terrestre",               value="tanques"),
    app_commands.Choice(name="⚓ Fragatas — Suporte naval espacial",           value="fragatas"),
    app_commands.Choice(name="🛸 Cruzadores — Nave de linha devastadora",     value="cruzadores"),
    app_commands.Choice(name="☄️ Interceptores — Nave rápida anti-caça",      value="interceptores"),
    app_commands.Choice(name="💣 Bombardeiros — Ataque a estruturas",          value="bombardeiros"),
    app_commands.Choice(name="🌑 Corvetas — Furtiva de reconhecimento",       value="corvetas"),
])
async def slash_comprar(interaction, unidade: str, quantidade: int):
    id_u = str(interaction.user.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message("Você não tem um império registrado.", ephemeral=True)
    if dados["imperios"][id_u].get("sancao"):
        return await interaction.response.send_message(f"🚫 **{dados['imperios'][id_u]['nome']}** está sancionado.", ephemeral=True)
    if quantidade <= 0:
        return await interaction.response.send_message("Quantidade deve ser maior que zero.", ephemeral=True)
    c_min, c_pib, desc = LOJA_UNIDADES[unidade]
    total_min = c_min * quantidade
    total_pib = c_pib * quantidade
    imp       = dados["imperios"][id_u]
    sem = []
    if imp["minerios"] < total_min: sem.append(f"💎 Precisa {formatar_numero(total_min)} min., tem {formatar_numero(imp['minerios'])}")
    if imp["pib"]      < total_pib: sem.append(f"💰 Precisa {formatar_creditos(total_pib)}, tem {formatar_creditos(imp['pib'])}")
    if sem:
        return await interaction.response.send_message("❌ Recursos insuficientes:\n" + "\n".join(sem), ephemeral=True)
    imp["minerios"] -= total_min
    imp["pib"]      -= total_pib
    imp[unidade]    += quantidade
    registrar_historico(id_u, f"Comprou {quantidade}× {nome_bonito(unidade)}")
    salvar(dados)
    icon  = ICONS_UNIDADES.get(unidade, "⚔️")
    embed = discord.Embed(title=f"{icon}  Aquisição Militar Confirmada", description=f"{random.choice(FLAVOR_COMPRA)}\n{SEP_MILITAR}", color=COR_SUCESSO)
    embed.add_field(name=f"{icon} Adquirido",    value=f"**{formatar_numero(quantidade)}×** {nome_bonito(unidade)}\n*{desc}*", inline=True)
    embed.add_field(name="💸 Custo Total",        value=f"💎 `{formatar_numero(total_min)}` min.\n💰 `{formatar_creditos(total_pib)}`", inline=True)
    embed.add_field(name="📦 Reservas Restantes", value=f"💎 `{formatar_numero(imp['minerios'])}` min.\n💰 `{formatar_creditos(imp['pib'])}`", inline=True)
    embed.set_footer(text=f"{RODAPE_MILITAR}  ·  Total de {nome_bonito(unidade)}: {formatar_numero(imp[unidade])}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(embed=embed)

# Mantém !comprar como alias para não quebrar quem já usa
@bot.command(name="comprar")
async def comprar(ctx, unidade: str = None, quantidade: str = None):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império. Use `/comprar` no Discord.")
    await ctx.send("⚠️ Use o comando `/comprar` — ele tem autocompletar de unidades!", delete_after=8)


@bot.tree.command(name="construir", description="Constrói uma fábrica para o seu império")
@app_commands.describe(fabrica="Tipo de fábrica a construir")
@app_commands.choices(fabrica=[
    app_commands.Choice(name="🔧 Fábrica Pequena    (+5 min/turno)",    value="fabrica_pequena"),
    app_commands.Choice(name="⚙️ Fábrica Média      (+15 min/turno)",   value="fabrica_media"),
    app_commands.Choice(name="🏗️ Fábrica Grande     (+40 min/turno)",   value="fabrica_grande"),
    app_commands.Choice(name="🏭 Fábrica Continental (+100 min/turno)", value="fabrica_continental"),
    app_commands.Choice(name="🌋 Mundo Forja         (+500 min/turno)", value="mundo_forja"),
])
async def slash_construir(interaction, fabrica: str):
    id_u = str(interaction.user.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message("Você não tem um império registrado.", ephemeral=True)
    if dados["imperios"][id_u].get("sancao"):
        return await interaction.response.send_message(f"🚫 **{dados['imperios'][id_u]['nome']}** está sancionado.", ephemeral=True)
    c_pib, c_min, prod, label = PRECO_FABRICAS[fabrica]
    imp = dados["imperios"][id_u]
    sem = []
    if imp["minerios"] < c_min: sem.append(f"💎 Precisa {formatar_numero(c_min)} min., tem {formatar_numero(imp['minerios'])}")
    if imp["pib"]      < c_pib: sem.append(f"💰 Precisa {formatar_creditos(c_pib)}, tem {formatar_creditos(imp['pib'])}")
    if sem:
        return await interaction.response.send_message("❌ Recursos insuficientes:\n" + "\n".join(sem), ephemeral=True)
    imp["minerios"]          -= c_min
    imp["pib"]               -= c_pib
    imp["fabricas"][fabrica] += 1
    registrar_historico(id_u, f"Construiu {label}")
    salvar(dados)
    icons_f = {"fabrica_pequena":"🔧","fabrica_media":"⚙️","fabrica_grande":"🏗️","fabrica_continental":"🏭","mundo_forja":"🌋"}
    icon    = icons_f.get(fabrica, "🔩")
    embed   = discord.Embed(title=f"{icon}  Instalação Industrial Concluída", description=f"{random.choice(FLAVOR_CONSTRUIR)}\n{SEP_LOJA}", color=COR_SUCESSO)
    embed.add_field(name=f"{icon} Construída",   value=f"**{label}**\n📈 `+{prod}` minérios/turno",                          inline=True)
    embed.add_field(name="💸 Custo Pago",         value=f"💎 `{formatar_numero(c_min)}` min.\n💰 `{formatar_creditos(c_pib)}`", inline=True)
    embed.add_field(name="📦 Reservas Restantes", value=f"💎 `{formatar_numero(imp['minerios'])}` min.\n💰 `{formatar_creditos(imp['pib'])}`", inline=True)
    embed.set_footer(text=f"{RODAPE_LOJA}  ·  Você possui {imp['fabricas'][fabrica]}× {label}")
    thumbnail_empire(embed, imp)
    await interaction.response.send_message(embed=embed)

# Mantém !construir como alias
@bot.command(name="construir")
async def construir(ctx, fabrica: str = None):
    await ctx.send("⚠️ Use o comando `/construir` — ele tem autocompletar de fábricas!", delete_after=8)


# ==============================
# COMERCIO
# ==============================

@bot.command(name="cobrar")
async def cobrar(ctx, destino: discord.Member = None, tipo: str = None, quantidade: str = None, *, motivo: str = "Cobrança"):
    id_cobrador = str(ctx.author.id)
    if not imperio_existe(id_cobrador):
        return await ctx.send("Voce nao tem um imperio registrado.")
    if not destino or not tipo or not quantidade:
        return await ctx.send("Uso: `!cobrar @membro pib/minerios <qtd> <motivo>`")
    if destino.id == ctx.author.id:
        return await ctx.send("Voce nao pode cobrar de si mesmo.")
    id_cobrado = str(destino.id)
    if not imperio_existe(id_cobrado):
        return await ctx.send(f"{destino.display_name} nao tem um imperio.")
    tipo = tipo.lower()
    if tipo not in ("pib", "minerios"):
        return await ctx.send("Tipo inválido. Use `pib` ou `minerios`.")
    try:
        qtd = int(quantidade.replace(".","").replace(",",""))
        if qtd <= 0: raise ValueError
    except ValueError:
        return await ctx.send("Quantidade inválida.")
    pib_val      = qtd if tipo == "pib" else 0
    min_val      = qtd if tipo == "minerios" else 0
    imp_cobrador = dados["imperios"][id_cobrador]
    imp_cobrado  = dados["imperios"][id_cobrado]
    label        = formatar_creditos(qtd) if tipo == "pib" else f"{formatar_numero(qtd)} min."
    embed = discord.Embed(title="📨  Cobrança Recebida!", description=f"{SEP_COMERCIO}\n**{imp_cobrador['nome']}** exige pagamento de **{imp_cobrado['nome']}**.\n{SEP_COMERCIO}", color=COR_ALERTA)
    embed.add_field(name="💸 Valor",      value=f"`{label}`", inline=True)
    embed.add_field(name="📝 Motivo",     value=motivo,       inline=True)
    embed.add_field(name="⏳ Aguardando", value=f"{destino.mention} deve aceitar ou recusar.", inline=False)
    embed.set_image(url=BANNER_COMERCIO)
    embed.set_footer(text=f"{RODAPE_COMERCIO}  ·  Expira em 2 minutos")
    thumbnail_empire(embed, imp_cobrado)
    view = ViewCobrar(id_cobrador, id_cobrado, pib_val, min_val, motivo)
    await ctx.send(content=f"{destino.mention} você recebeu uma cobrança!", embed=embed, view=view)


@bot.command(name="tratar")
async def tratar(ctx, destino: discord.Member = None, tipo: str = None, quantidade: str = None):
    id_orig = str(ctx.author.id)
    if not imperio_existe(id_orig):
        return await ctx.send("Voce nao tem um imperio registrado.")
    if not destino or not tipo or not quantidade:
        return await ctx.send("Uso: `!tratar @membro pib/minerios <qtd>`")
    if destino.id == ctx.author.id:
        return await ctx.send("Voce nao pode enviar para si mesmo.")
    id_dest = str(destino.id)
    if not imperio_existe(id_dest):
        return await ctx.send(f"{destino.display_name} nao tem um imperio.")
    tipo = tipo.lower()
    if tipo not in ("pib","minerios"):
        return await ctx.send("Tipo inválido. Use `pib` ou `minerios`.")
    try:
        qtd = int(quantidade.replace(".","").replace(",",""))
        if qtd <= 0: raise ValueError
    except ValueError:
        return await ctx.send("Quantidade inválida.")
    imp_orig = dados["imperios"][id_orig]
    imp_dest = dados["imperios"][id_dest]
    if imp_orig[tipo] < qtd:
        return await ctx.send("Voce nao tem recursos suficientes.")
    imp_orig[tipo] -= qtd
    imp_dest[tipo] += qtd
    label = formatar_creditos(qtd) if tipo == "pib" else f"{formatar_numero(qtd)} min."
    registrar_historico(id_orig, f"Enviou {label} → {imp_dest['nome']}")
    registrar_historico(id_dest, f"Recebeu {label} de {imp_orig['nome']}")
    salvar(dados)
    embed = discord.Embed(title="🤝  Tratado Comercial Firmado", description=f"{SEP_COMERCIO}\n*A Câmara de Comércio registra a transação.*\n{SEP_COMERCIO}", color=COR_COMERCIO)
    embed.add_field(name="💸 Transferido", value=f"`{label}`",     inline=True)
    embed.add_field(name="📤 Origem",      value=imp_orig["nome"], inline=True)
    embed.add_field(name="📥 Destino",     value=imp_dest["nome"], inline=True)
    embed.set_image(url=BANNER_COMERCIO)
    embed.set_footer(text=RODAPE_COMERCIO)
    await ctx.send(content=f"🤝 {destino.mention} recebeu recursos!", embed=embed)


# ==============================
# MINERACAO
# ==============================

@bot.command(name="minar")
@commands.cooldown(1, 1200, commands.BucketType.user)
async def minar(ctx):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Voce nao tem um imperio registrado.")
    if dados["imperios"][id_u].get("sancao"):
        return await ctx.send(f"🚫 **{dados['imperios'][id_u]['nome']}** está sancionado e não pode minerar.")
    ganho = random.randint(20, 50)
    dados["imperios"][id_u]["minerios"] += ganho
    registrar_historico(id_u, f"Minerou {ganho} unidades")
    salvar(dados)
    imp   = dados["imperios"][id_u]
    embed = discord.Embed(title="⛏️  Extração Concluída", description=f"{random.choice(FLAVOR_MINAR)}\n{SEP_PADRAO}", color=COR_PRIMARIA)
    embed.add_field(name="💎 Extraído", value=f"`{ganho}` minérios", inline=True)
    embed.add_field(name="📦 Reservas", value=f"`{formatar_numero(imp['minerios'])}` minérios totais", inline=True)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  Próxima extração em 20 min")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@minar.error
async def minar_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        m = int(error.retry_after // 60)
        s = int(error.retry_after % 60)
        await ctx.send(f"⛏️ Sondas em campo. Aguarde **{m}m {s}s** para nova extração.")


# ==============================
# NOVOS SISTEMAS — JOGADOR
# ==============================

@bot.command(name="aliancas")
async def aliancas(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} não tem um império.")
    imp   = dados["imperios"][id_u]
    lista = imp.get("aliancas", [])
    aliados = [f"🤝 **{dados['imperios'][a]['nome']}**" for a in lista if a in dados["imperios"]]
    if not aliados:
        return await ctx.send(f"**{imp['nome']}** não tem alianças ativas.")
    embed = discord.Embed(title=f"🤝  Alianças  ·  {imp['nome']}", description="\n".join(aliados), color=0x1E3A5F)
    embed.set_footer(text=RODAPE_PADRAO)
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.tree.command(name="espionar", description="Realiza uma operação de espionagem contra outro império")
@app_commands.describe(alvo="Império a espionar")
async def slash_espionar(interaction, alvo: discord.Member):
    id_u = str(interaction.user.id)
    if not imperio_existe(id_u):
        return await interaction.response.send_message("Você não tem um império registrado.", ephemeral=True)
    id_alvo = str(alvo.id)
    if not imperio_existe(id_alvo):
        return await interaction.response.send_message(f"{alvo.display_name} não tem um império.", ephemeral=True)
    if id_u == id_alvo:
        return await interaction.response.send_message("Você não pode espionar a si mesmo.", ephemeral=True)

    imp_espia = dados["imperios"][id_u]
    imp_alvo  = dados["imperios"][id_alvo]
    nivel_esp = imp_espia.get("tecnologias", {}).get("espionagem", 0)
    nivel_def = imp_alvo.get("tecnologias",  {}).get("espionagem", 0)
    chance    = min(95, max(10, 40 + nivel_esp * 10 - nivel_def * 8))
    sucesso   = random.randint(1, 100) <= chance

    registrar_historico(id_u,    f"🕵️ Tentou espionar {imp_alvo['nome']} — {'Sucesso' if sucesso else 'Falhou'}")
    registrar_historico(id_alvo, f"🚨 Tentativa de espionagem detectada de {imp_espia['nome']}")
    salvar(dados)

    if not sucesso:
        embed = discord.Embed(
            title="🕵️  Operação Falhou",
            description=f"*Seus agentes foram descobertos e capturados.*\n{SEP_PADRAO}",
            color=COR_PERIGO,
        )
        embed.add_field(name="🎯 Alvo",          value=imp_alvo["nome"],    inline=True)
        embed.add_field(name="📊 Sua Chance",     value=f"{chance}%",        inline=True)
        embed.add_field(name="🛡️ Contra-Intel.", value=f"Nível {nivel_def}", inline=True)
        embed.add_field(name="🕵️ Seu Nível",     value=f"Espionagem {nivel_esp}", inline=True)
        embed.add_field(
            name="💡 Como melhorar",
            value="Peça ao ADM para aumentar seu nível de espionagem com `/definir_tech`.",
            inline=False,
        )
        embed.set_footer(text=f"{RODAPE_PADRAO}  ·  Cooldown: 1 hora")
        thumbnail_empire(embed, imp_espia)
        return await interaction.response.send_message(embed=embed)

    # Sucesso — informações reveladas por nível
    embed = discord.Embed(
        title="🕵️  Operação Bem-Sucedida!",
        description=f"*Relatório confidencial sobre **{imp_alvo['nome']}**.*\n{SEP_PADRAO}",
        color=COR_ALERTA,
    )
    embed.add_field(name="🎯 Alvo",       value=imp_alvo["nome"],   inline=True)
    embed.add_field(name="📊 Chance",      value=f"{chance}%",       inline=True)
    embed.add_field(name="🕵️ Nível ESP",  value=str(nivel_esp),     inline=True)

    # Nível 1+ — economia básica
    embed.add_field(name="💰 PIB",       value=formatar_creditos(imp_alvo["pib"]),            inline=True)
    embed.add_field(name="💎 Minérios",  value=formatar_numero(imp_alvo["minerios"]) + " min.", inline=True)
    embed.add_field(name="👥 População", value=formatar_numero(imp_alvo["populacao_total"]),   inline=True)

    # Nível 3+ — militar
    if nivel_esp >= 3:
        poder    = sum(imp_alvo.get(k,0)*LOJA_UNIDADES[k][1] for k in LOJA_UNIDADES)
        recrutas = imp_alvo.get("recrutas", 0)
        unidades = "\n".join(
            f"{ICONS_UNIDADES.get(k,'⚔️')} {nome_bonito(k)}: **{formatar_numero(imp_alvo.get(k,0))}**"
            for k in LOJA_UNIDADES if imp_alvo.get(k, 0) > 0
        ) or "Nenhuma unidade"
        embed.add_field(name="⚔️ Poder Militar", value=f"{formatar_numero(poder)} pts",     inline=True)
        embed.add_field(name="🪖 Recrutas",       value=formatar_numero(recrutas),            inline=True)
        embed.add_field(name="🔫 Unidades",       value=unidades,                             inline=False)

    # Nível 6+ — território e tecnologias
    if nivel_esp >= 6:
        techs   = imp_alvo.get("tecnologias", {})
        tech_s  = "  ".join(f"{AREAS_TECH[a]['emoji']} `{techs.get(a,0)}`" for a in AREAS_TECH)
        planetas = imp_alvo.get("planetas", [])
        sistemas = imp_alvo.get("sistemas", [])
        embed.add_field(name="🪐 Planetas",    value=f"{len(planetas)} planeta(s)\n" + "\n".join(f"• {p}" for p in planetas[:5]) + ("..." if len(planetas)>5 else ""), inline=True)
        embed.add_field(name="🌌 Sistemas",    value=f"{len(sistemas)} sistema(s)",  inline=True)
        embed.add_field(name="🔬 Tecnologias", value=tech_s,                          inline=False)

    # Nível 9+ — fábricas e projetos
    if nivel_esp >= 9:
        fab_txt  = "\n".join(
            f"{PRECO_FABRICAS[k][3]}: **{imp_alvo['fabricas'].get(k,0)}**"
            for k in PRECO_FABRICAS if imp_alvo.get("fabricas",{}).get(k,0) > 0
        ) or "Nenhuma"
        proj_txt = "\n".join(f"• {p}" for p in imp_alvo.get("projetos",{})) or "Nenhum"
        prod     = sum(imp_alvo.get("fabricas",{}).get(k,0)*v for k,v in TIPOS_FABRICAS.items())
        embed.add_field(name="🏭 Fábricas",          value=fab_txt,                               inline=True)
        embed.add_field(name="📈 Produção/Turno",    value=f"+{formatar_numero(prod)} min.",       inline=True)
        embed.add_field(name="🔭 Projetos Ativos",   value=proj_txt,                              inline=False)

    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  Cooldown: 1 hora")
    thumbnail_empire(embed, imp_espia)
    await interaction.response.send_message(embed=embed)

# Mantém !espionar como alias
@bot.command(name="espionar")
@commands.cooldown(1, 3600, commands.BucketType.user)
async def espionar(ctx, alvo: discord.Member = None):
    await ctx.send("⚠️ Use `/espionar` — tem mais informações e autocompletar!", delete_after=8)

@espionar.error
async def espionar_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        m = int(error.retry_after // 60)
        s = int(error.retry_after % 60)
        await ctx.send(f"🕵️ Agentes em campo. Aguarde **{m}m {s}s** para nova operação.")


@bot.command(name="resumo")
async def resumo(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} não tem um império.")
    imp     = dados["imperios"][id_u]
    poder   = sum(imp.get(k,0)*LOJA_UNIDADES[k][1] for k in LOJA_UNIDADES) + imp.get("recrutas",0)
    n_plan  = len(imp.get("planetas",[]))
    prod    = sum(imp.get("fabricas",{}).get(k,0)*v for k,v in TIPOS_FABRICAS.items())
    aliados = [dados["imperios"][a]["nome"] for a in imp.get("aliancas",[]) if a in dados["imperios"]]
    embed   = discord.Embed(title=f"📋  {imp['nome']}", description=f"*{imp.get('descricao','—')}*", color=get_cor(imp))
    vassalagem = imp.get("vassalagem")
    status_pol = f"🔗 Vassalo de **{vassalagem['nome_soberano']}**" if vassalagem else "🆓 Soberano"
    embed.add_field(name="📊 Status", value=(
        f"💰 `{formatar_creditos(imp['pib'])}`\n"
        f"💎 `{formatar_numero(imp['minerios'])}` min.\n"
        f"📈 `+{formatar_numero(prod)}/turno`\n"
        f"⚔️ `{formatar_numero(poder)}` pts\n"
        f"🪐 `{n_plan}` planeta(s)\n"
        f"🤝 `{', '.join(aliados) or 'Nenhuma aliança'}`\n"
        f"{status_pol}"
    ), inline=True)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="comparar")
async def comparar(ctx, membro: discord.Member = None):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    if not membro:
        return await ctx.send("Uso: `!comparar @membro`")
    id_alvo = str(membro.id)
    if not imperio_existe(id_alvo):
        return await ctx.send(f"{membro.display_name} não tem um império.")
    meu   = dados["imperios"][id_u]
    outro = dados["imperios"][id_alvo]
    def bar(v1, v2, tam=8):
        if v1+v2 == 0: return "░"*tam, "░"*tam
        p1 = round(v1/(v1+v2)*tam)
        return "█"*p1+"░"*(tam-p1), "█"*(tam-p1)+"░"*p1
    poder_meu   = sum(meu.get(k,0)*LOJA_UNIDADES[k][1]   for k in LOJA_UNIDADES) + meu.get("recrutas",0)
    poder_outro = sum(outro.get(k,0)*LOJA_UNIDADES[k][1] for k in LOJA_UNIDADES) + outro.get("recrutas",0)
    prod_meu    = sum(meu.get("fabricas",{}).get(k,0)*v   for k,v in TIPOS_FABRICAS.items())
    prod_outro  = sum(outro.get("fabricas",{}).get(k,0)*v for k,v in TIPOS_FABRICAS.items())
    b_pib  = bar(meu["pib"],      outro["pib"])
    b_min  = bar(meu["minerios"], outro["minerios"])
    b_mil  = bar(poder_meu,       poder_outro)
    b_prod = bar(prod_meu,        prod_outro)
    b_plan = bar(len(meu.get("planetas",[])), len(outro.get("planetas",[])))
    embed = discord.Embed(title=f"⚖️  Comparação Imperial", description=f"{SEP_PADRAO}\n**{meu['nome']}**  vs  **{outro['nome']}**\n{SEP_PADRAO}", color=COR_PRIMARIA)
    linhas = [
        f"💰 PIB      `{b_pib[0]}`  ×  `{b_pib[1]}`",
        f"💎 Min.     `{b_min[0]}`  ×  `{b_min[1]}`",
        f"⚔️ Militar  `{b_mil[0]}`  ×  `{b_mil[1]}`",
        f"🏭 Produção `{b_prod[0]}` ×  `{b_prod[1]}`",
        f"🪐 Planetas `{b_plan[0]}` ×  `{b_plan[1]}`",
    ]
    embed.add_field(name="Comparação", value="\n".join(linhas), inline=False)
    embed.add_field(name=f"💰 {meu['nome']}",   value=formatar_creditos(meu["pib"]),        inline=True)
    embed.add_field(name=f"💰 {outro['nome']}", value=formatar_creditos(outro["pib"]),       inline=True)
    embed.add_field(name="\u200b",              value="\u200b",                             inline=True)
    embed.add_field(name=f"⚔️ Poder",           value=formatar_numero(poder_meu)+" pts",   inline=True)
    embed.add_field(name=f"⚔️ Poder",           value=formatar_numero(poder_outro)+" pts", inline=True)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {ctx.author.display_name} vs {membro.display_name}")
    await ctx.send(embed=embed)


@bot.command(name="previsao")
async def previsao(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} não tem um império.")
    imp = dados["imperios"][id_u]
    imp.setdefault("tecnologias", {a: 0 for a in AREAS_TECH})
    prod_base       = sum(imp.get("fabricas",{}).get(k,0)*v for k,v in TIPOS_FABRICAS.items())
    prod_industrial = int(prod_base * bonus_tech(imp,"industrial"))
    pib_bonus       = int(20_000_000 * bonus_tech(imp,"economico"))
    buff = imp.get("buff_guerra",{})
    nerf = imp.get("nerf_guerra",{})
    min_buff = int((10+prod_industrial)*buff.get("industrial",0)/100)
    pib_buff = int(pib_bonus*buff.get("economico",0)/100)
    min_nerf = int((10+prod_industrial)*nerf.get("industrial",0)/100)
    pib_nerf = int(pib_bonus*nerf.get("economico",0)/100)
    plan_pib = plan_min = plan_pop = 0
    for dp in imp.get("planetas_data",{}).values():
        b = calcular_bonus_planeta(dp)
        plan_pib += b.get("pib",0)
        plan_min += b.get("minerios",0)
        plan_pop += b.get("populacao",0)
    vassalagem = imp.get("vassalagem")
    tributo_pib = int((pib_bonus+pib_buff-pib_nerf+plan_pib) * vassalagem["tributo"] / 100) if vassalagem else 0
    total_min = 10 + prod_industrial + min_buff - min_nerf + plan_min
    total_pib = pib_bonus + pib_buff - pib_nerf + plan_pib - tributo_pib
    embed = discord.Embed(title=f"🔭  Previsão do Próximo Turno  ·  {imp['nome']}", description=f"{SEP_PADRAO}\n*Estimativa de produção no próximo `/turno`.*\n{SEP_PADRAO}", color=get_cor(imp))
    embed.add_field(name="💰 PIB",      value=f"+{formatar_creditos(total_pib)}",   inline=True)
    embed.add_field(name="💎 Minérios", value=f"+{formatar_numero(total_min)}",     inline=True)
    embed.add_field(name="👥 Pop.",     value=f"+{formatar_numero(plan_pop)}",      inline=True)
    detalhes = f"🏭 Fábricas: +{formatar_numero(prod_industrial)} min.\n📈 Economia: +{formatar_creditos(pib_bonus)}\n"
    if plan_min or plan_pib:  detalhes += f"🪐 Planetas: +{formatar_numero(plan_min)} min. / +{formatar_creditos(plan_pib)}\n"
    if buff:                  detalhes += f"🔺 Buff guerra ativo\n"
    if nerf:                  detalhes += f"🔻 Nerf guerra ativo\n"
    if tributo_pib:           detalhes += f"💸 Tributo vassalagem: -{formatar_creditos(tributo_pib)}\n"
    embed.add_field(name="📋 Detalhes", value=detalhes, inline=False)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="diario")
async def diario(ctx, *, texto: str = None):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    if not texto:
        return await ctx.send("Uso: `!diario <texto do evento>`")
    if len(texto) > 500:
        return await ctx.send("❌ O diário não pode ter mais de 500 caracteres.")
    imp = dados["imperios"][id_u]
    registrar_historico(id_u, f"📖 [Diário] {texto}")
    salvar(dados)
    embed = discord.Embed(title=f"📖  Registro Imperial  ·  {imp['nome']}", description=f"{SEP_PADRAO}\n*{texto}*\n{SEP_PADRAO}", color=get_cor(imp))
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="planetas")
async def planetas_cmd(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} não tem um império registrado.")
    imp           = dados["imperios"][id_u]
    lista_plan    = imp.get("planetas", [])
    planetas_data = imp.get("planetas_data", {})
    if not lista_plan:
        return await ctx.send("📭 Nenhum planeta registrado.")
    embed = discord.Embed(title=f"🌌  Território Planetário  ·  {imp['nome']}", description=f"{SEP_TERRIT}\n*Domínios do império no cosmos.*\n{SEP_TERRIT}", color=get_cor(imp))
    bonus_total = {}
    for nome in lista_plan:
        dados_p = planetas_data.get(nome, {"nivel":"desconhecido","tipo":None,"recurso":None})
        nivel   = dados_p.get("nivel","desconhecido")
        tipo    = dados_p.get("tipo")
        recurso = dados_p.get("recurso")
        if nivel == "desconhecido":
            valor = "❓ Desconhecido — use `!colonizar` para explorar"
        elif nivel == "colonia_pendente":
            valor = "🚀 Expedição em andamento — aguardando ADM revelar"
        else:
            info_n = NIVEIS_PLANETA.get(nivel, {})
            info_t = TIPOS_PLANETA.get(tipo, {}) if tipo else {}
            bonus  = calcular_bonus_planeta(dados_p)
            for k,v in bonus.items():
                bonus_total[k] = bonus_total.get(k,0) + v
            bonus_str = " · ".join(f"+{v:,} {k}/turno".replace(",",".") for k,v in bonus.items()) if bonus else "Nenhum"
            rec_str   = f" · 💎 {recurso}" if recurso else ""
            valor = (
                f"{info_n.get('emoji','?')} {info_n.get('nome','?')}  ·  "
                f"{info_t.get('emoji','?')} {info_t.get('nome','?')}{rec_str}\n"
                f"📊 {bonus_str}"
            )
        embed.add_field(name=f"🪐 {nome}", value=valor, inline=False)
    if bonus_total:
        total_str = " · ".join(f"+{v:,} {k}/turno".replace(",",".") for k,v in bonus_total.items())
        embed.add_field(name="\u200b", value=SEP_PADRAO, inline=False)
        embed.add_field(name="📊 Bônus Total dos Planetas", value=total_str, inline=False)
    embed.set_footer(text=f"{RODAPE_TERRIT}  ·  {alvo.display_name}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="colonizar")
async def colonizar(ctx, *, nome: str = None):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    if not nome:
        return await ctx.send("Uso: `!colonizar <nome do planeta>`")
    imp = dados["imperios"][id_u]
    if nome not in imp.get("planetas", []):
        return await ctx.send(f"❌ **{nome}** não pertence ao seu império.")
    dados_p = imp.get("planetas_data", {}).get(nome, {})
    if dados_p.get("nivel", "desconhecido") != "desconhecido":
        nivel_atual = NIVEIS_PLANETA.get(dados_p["nivel"], {}).get("nome", "?")
        return await ctx.send(f"❌ **{nome}** já é uma {nivel_atual}!")
    custo_pib = NIVEIS_PLANETA["colonia"]["custo_pib"]
    custo_min = NIVEIS_PLANETA["colonia"]["custo_min"]
    sem = []
    if imp["pib"]      < custo_pib: sem.append(f"💰 Precisa {formatar_creditos(custo_pib)}, tem {formatar_creditos(imp['pib'])}")
    if imp["minerios"] < custo_min: sem.append(f"💎 Precisa {formatar_numero(custo_min)} min., tem {formatar_numero(imp['minerios'])}")
    if sem:
        return await ctx.send("❌ Recursos insuficientes:\n" + "\n".join(sem))
    imp["pib"]      -= custo_pib
    imp["minerios"] -= custo_min
    imp.setdefault("planetas_data", {})[nome] = {"nivel":"colonia_pendente","tipo":None,"recurso":None}
    registrar_historico(id_u, f"🚀 Expedição de colonização enviada para {nome}")
    salvar(dados)
    embed = discord.Embed(title="🚀  Expedição de Colonização Enviada!", description=f"{SEP_TERRIT}\n*Suas naves partem em direção ao desconhecido...*\n{SEP_TERRIT}", color=COR_PRIMARIA)
    embed.add_field(name="🪐 Destino",    value=f"**{nome}**",                                                        inline=True)
    embed.add_field(name="💸 Custo",      value=f"💰 {formatar_creditos(custo_pib)}\n💎 {formatar_numero(custo_min)} min.", inline=True)
    embed.add_field(name="⏳ Aguardando", value="O ADM irá revelar o planeta em breve!",                               inline=False)
    embed.set_image(url=BANNER_TERRIT)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  Use !planetas para ver seu território")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="desenvolver")
async def desenvolver(ctx, *, nome: str = None):
    id_u = str(ctx.author.id)
    if not imperio_existe(id_u):
        return await ctx.send("Você não tem um império registrado.")
    if not nome:
        return await ctx.send("Uso: `!desenvolver <nome do planeta>`")
    imp     = dados["imperios"][id_u]
    dados_p = imp.get("planetas_data", {}).get(nome)
    if not dados_p:
        return await ctx.send(f"❌ **{nome}** não foi revelado ainda.")
    nivel_atual = dados_p.get("nivel", "desconhecido")
    if nivel_atual in ("desconhecido", "colonia_pendente"):
        return await ctx.send(f"❌ **{nome}** ainda não foi colonizado/revelado.")
    progressao = ["colonia", "cidade", "capital"]
    if nivel_atual not in progressao or progressao.index(nivel_atual) >= len(progressao) - 1:
        return await ctx.send(f"✨ **{nome}** já está no nível máximo — Capital!")
    prox_nivel = progressao[progressao.index(nivel_atual) + 1]
    if prox_nivel == "capital":
        for n, p in imp.get("planetas_data", {}).items():
            if p.get("nivel") == "capital" and n != nome:
                return await ctx.send(f"❌ Você já tem uma Capital: **{n}**!")
    custo_pib = NIVEIS_PLANETA[prox_nivel]["custo_pib"]
    custo_min = NIVEIS_PLANETA[prox_nivel]["custo_min"]
    sem = []
    if imp["pib"]      < custo_pib: sem.append(f"💰 Precisa {formatar_creditos(custo_pib)}, tem {formatar_creditos(imp['pib'])}")
    if imp["minerios"] < custo_min: sem.append(f"💎 Precisa {formatar_numero(custo_min)} min., tem {formatar_numero(imp['minerios'])}")
    if sem:
        return await ctx.send("❌ Recursos insuficientes:\n" + "\n".join(sem))
    imp["pib"]      -= custo_pib
    imp["minerios"] -= custo_min
    dados_p["nivel"] = prox_nivel
    registrar_historico(id_u, f"Planeta {nome} evoluído para {NIVEIS_PLANETA[prox_nivel]['nome']}")
    salvar(dados)
    info_n    = NIVEIS_PLANETA[prox_nivel]
    bonus     = calcular_bonus_planeta(dados_p)
    bonus_txt = "\n".join(f"+{v:,} {k}/turno".replace(",",".") for k,v in bonus.items()) if bonus else "Nenhum"
    embed = discord.Embed(title=f"{info_n['emoji']}  Planeta Desenvolvido!", description=f"*{nome} avança para um novo patamar.*\n{SEP_PADRAO}", color=COR_SUCESSO)
    embed.add_field(name="🪐 Planeta",     value=nome,           inline=True)
    embed.add_field(name="📈 Novo Nível",  value=info_n["nome"], inline=True)
    embed.add_field(name="📊 Bônus/Turno", value=bonus_txt,      inline=True)
    embed.add_field(name="📦 Reservas",    value=f"💰 {formatar_creditos(imp['pib'])} | 💎 {formatar_numero(imp['minerios'])} min.", inline=False)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {imp['nome']}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


@bot.command(name="guerras")
async def guerras_cmd(ctx, membro: discord.Member = None):
    alvo = membro or ctx.author
    id_u = str(alvo.id)
    if not imperio_existe(id_u):
        return await ctx.send(f"{alvo.display_name} não tem um império.")
    imp  = dados["imperios"][id_u]
    hist = imp.get("historico_guerras", [])
    vit  = sum(1 for h in hist if h["resultado"] == "vitória")
    der  = sum(1 for h in hist if h["resultado"] == "derrota")
    emp  = sum(1 for h in hist if h["resultado"] == "empate")
    embed = discord.Embed(title=f"⚔️  Dossiê de Guerra  ·  {imp['nome']}", description=f"{SEP_PADRAO}\n*Registro completo de conflitos, alianças e status político.*\n{SEP_PADRAO}", color=get_cor(imp))
    embed.add_field(name="📊 Placar Geral", value=f"⚔️ Vitórias: **{vit}**  ·  🏳️ Derrotas: **{der}**  ·  🤝 Empates: **{emp}**", inline=False)
    vassalagem = imp.get("vassalagem")
    if vassalagem:
        icons = {"vassalo":"🔗","fantoche":"🤖","ocupado":"🏴"}
        ic = icons.get(vassalagem["tipo"],"🔗")
        embed.add_field(name=f"{ic}  Status Político", value=f"{ic} **{vassalagem['tipo'].title()}** de **{vassalagem['nome_soberano']}**\n💸 Tributo: `{vassalagem['tributo']}%`/turno\n📅 Desde: {vassalagem.get('desde','?')}", inline=False)
    vassalos = [dados["imperios"].get(v,{}).get("nome","?") for v in imp.get("vassalos",[]) if v in dados["imperios"]]
    if vassalos:
        embed.add_field(name="👑  Vassalos Controlados", value="\n".join(f"🔗 **{n}**" for n in vassalos), inline=False)
    aliados = [dados["imperios"].get(a,{}).get("nome","?") for a in imp.get("aliancas",[]) if a in dados["imperios"]]
    if aliados:
        embed.add_field(name="🤝  Alianças Ativas", value="\n".join(f"🤝 **{n}**" for n in aliados), inline=False)
    if hist:
        linhas = []
        for h in hist[:10]:
            icons_r = {"vitória":"⚔️","derrota":"🏳️","empate":"🤝"}
            linhas.append(f"{icons_r.get(h['resultado'],'📋')} **{h['resultado'].title()}** vs **{h['adversario']}**\n　📅 {h['data']}  ·  *{h.get('tipo','—')}*")
        embed.add_field(name=f"📜  Histórico  ({len(hist)} total)", value="\n".join(linhas), inline=False)
    else:
        embed.add_field(name="📜  Histórico", value="Nenhum conflito registrado.", inline=False)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  {alvo.display_name}")
    thumbnail_empire(embed, imp)
    await ctx.send(embed=embed)


# ==============================
# AJUDA
# ==============================

@bot.command(name="ajuda")
async def ajuda(ctx):
    # ── Embed 1 — Capa ───────────────────────────────────────────────
    capa = discord.Embed(
        title="🌌  Sistema Galáctico de Impérios",
        description=(
            "```\n"
            "  ⬡  MANUAL DO COMANDANTE  ⬡\n"
            "```\n"
            "*Construa seu império, expanda seus territórios,\n"
            "domine a galáxia ou forje alianças eternas.*\n\n"
            "**Prefixo de comandos:** `!comando`\n"
            "**Slash commands ADM:** `/comando`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=COR_PRIMARIA,
    )
    capa.set_footer(text="⬡ Sistema Galáctico  ·  Role para ver todos os módulos")
    await ctx.send(embed=capa)

    # ── Embed 2 — Perfil & Império ────────────────────────────────────
    e_perfil = discord.Embed(
        title="👤  Módulo I  —  Perfil & Império",
        description="*Gerencie a identidade e os registros do seu império.*",
        color=0x5B21B6,
    )
    e_perfil.add_field(
        name="📋  Visualização",
        value=(
            "`!perfil` · `!status` — Perfil resumido do seu império\n"
            "`!perfil @membro` — Ver o perfil de outro comandante\n"
            "`!ficha` — Dossiê completo com todos os detalhes\n"
            "`!resumo` — Status compacto em formato rápido\n"
            "`!historico` — Últimos 20 registros imperiais"
        ),
        inline=False,
    )
    e_perfil.add_field(
        name="🎨  Personalização",
        value=(
            "`!setar_brasao` → abre painel para trocar o brasão\n"
            "`/alterar_brasao` — Slash command para o mesmo\n"
            "`/editar_perfil` *(ADM)* — Edita descrição, cor e brasão"
        ),
        inline=False,
    )
    e_perfil.add_field(
        name="📊  Rankings",
        value=(
            "`!ranking` — 🥇 Top 10 impérios por PIB\n"
            "`!ranking_militar` — ⚔️ Top 10 por poder de combate\n"
            "`!poder_militar` — Ver poder detalhado de um império\n"
            "`!comparar @membro` — Confronto lado a lado"
        ),
        inline=False,
    )
    e_perfil.add_field(
        name="📖  Roleplay",
        value="`!diario <texto>` — Registra um evento no arquivo imperial",
        inline=False,
    )
    e_perfil.set_footer(text="⬡ Módulo I / VI")
    await ctx.send(embed=e_perfil)

    # ── Embed 3 — Economia ────────────────────────────────────────────
    e_econ = discord.Embed(
        title="💰  Módulo II  —  Economia & Produção",
        description="*Gerencie recursos, construa fábricas e expanda sua frota.*",
        color=COR_OURO,
    )
    e_econ.add_field(
        name="🛒  Mercado",
        value=(
            "`!loja` — Ver catálogo completo de unidades e fábricas\n"
            "`!comprar <unidade> <qtd>` — Adquirir unidades militares\n"
            "`!construir <fábrica>` — Construir infraestrutura industrial"
        ),
        inline=False,
    )
    e_econ.add_field(
        name="⛏️  Mineração",
        value=(
            "`!minar` — Extração manual de minérios\n"
            "⏳ *Cooldown: 20 minutos por extração*"
        ),
        inline=True,
    )
    e_econ.add_field(
        name="🔭  Planejamento",
        value=(
            "`!previsao` — Estimativa de produção do próximo turno\n"
            "`!meus_projetos` — Ver projetos pendentes"
        ),
        inline=True,
    )
    e_econ.add_field(
        name="🏭  Fábricas disponíveis",
        value=(
            "`fabrica_pequena` · `fabrica_media` · `fabrica_grande`\n"
            "`fabrica_continental` · `mundo_forja` *(requer sacrifício)*"
        ),
        inline=False,
    )
    e_econ.set_footer(text="⬡ Módulo II / VI")
    await ctx.send(embed=e_econ)

    # ── Embed 4 — Diplomacia & Comércio ──────────────────────────────
    e_diplo = discord.Embed(
        title="🤝  Módulo III  —  Diplomacia & Comércio",
        description="*Negocie, forje alianças e movimente recursos entre impérios.*",
        color=COR_COMERCIO,
    )
    e_diplo.add_field(
        name="💱  Transações",
        value=(
            "`!tratar @membro pib/minerios <qtd>` — Enviar recursos\n"
            "`!cobrar @membro pib/minerios <qtd> <motivo>` — Cobrança interativa\n"
            "↳ *O destinatário recebe botões de ✅ Aceitar / ❌ Recusar*"
        ),
        inline=False,
    )
    e_diplo.add_field(
        name="🤝  Alianças",
        value=(
            "`!aliancas` — Ver suas alianças ativas\n"
            "`!aliancas @membro` — Ver alianças de outro império"
        ),
        inline=True,
    )
    e_diplo.add_field(
        name="🔬  Tecnologia",
        value=(
            "`!tecnologias` — Ver seus níveis de tech\n"
            "`!tecnologias @membro` — Ver tech de outro"
        ),
        inline=True,
    )
    e_diplo.set_footer(text="⬡ Módulo III / VI")
    await ctx.send(embed=e_diplo)

    # ── Embed 5 — Território & Planetas ──────────────────────────────
    e_territ = discord.Embed(
        title="🪐  Módulo IV  —  Território & Planetas",
        description="*Expanda seu domínio pelo cosmos, colonize e desenvolva mundos.*",
        color=COR_TERRITORIO,
    )
    e_territ.add_field(
        name="🗺️  Mapa",
        value=(
            "`!mapa` — Gera o mapa galáctico atualizado\n"
            "`/mapa_grade` — Ver referência da grade A–Q / 1–18"
        ),
        inline=False,
    )
    e_territ.add_field(
        name="🪐  Gestão de Planetas",
        value=(
            "`!planetas` — Ver todos os seus planetas e bônus\n"
            "`!planetas @membro` — Ver planetas de outro império\n"
            "`!colonizar <planeta>` — Enviar expedição de colonização\n"
            "`!desenvolver <planeta>` — Evoluir: Colônia → Cidade → Capital"
        ),
        inline=False,
    )
    e_territ.add_field(
        name="📈  Níveis de Planeta",
        value=(
            "🏕️ **Colônia** → bônus básico por turno\n"
            "🏙️ **Cidade** → bônus dobrado\n"
            "👑 **Capital** → bônus quadruplicado *(1 por império)*"
        ),
        inline=False,
    )
    e_territ.set_footer(text="⬡ Módulo IV / VI")
    await ctx.send(embed=e_territ)

    # ── Embed 6 — Guerra & Espionagem ─────────────────────────────────
    e_guerra = discord.Embed(
        title="⚔️  Módulo V  —  Guerra & Espionagem",
        description="*Declare guerras, envie ultimatos e infiltre agentes inimigos.*",
        color=COR_MILITAR,
    )
    e_guerra.add_field(
        name="📨  Diplomacia de Crise",
        value=(
            "`!ultimato @membro <exigência>` — Enviar ultimato formal\n"
            "↳ *1 hora para aceitar ou recusar*\n"
            "`!render` — Declarar rendição na guerra atual"
        ),
        inline=False,
    )
    e_guerra.add_field(
        name="⚔️  Registros de Guerra",
        value=(
            "`!guerras` — Histórico de guerras, alianças e vassalagem\n"
            "`!guerras @membro` — Ver dossiê de outro império\n"
            "`/status_guerras` — Listar conflitos ativos"
        ),
        inline=True,
    )
    e_guerra.add_field(
        name="🕵️  Espionagem",
        value=(
            "`!espionar @membro` — Operação de inteligência\n"
            "⏳ *Cooldown: 1 hora · chance varia com tech*"
        ),
        inline=True,
    )
    e_guerra.add_field(
        name="🗺️  Batalha",
        value=(
            "`!status_batalha` — Ver status da batalha no canal atual\n"
            "`!mapa_guerra` — Mapa com conflitos ativos"
        ),
        inline=False,
    )
    e_guerra.set_footer(text="⬡ Módulo V / VI")
    await ctx.send(embed=e_guerra)

    # ── Embed 7 — ADM ─────────────────────────────────────────────────
    e_adm = discord.Embed(
        title="🛡️  Módulo VI  —  Painel do Administrador",
        description="*Comandos exclusivos para o Conselho dos Administradores.*",
        color=0x1E3A5F,
    )
    e_adm.add_field(
        name="👑  Gestão de Impérios",
        value=(
            "`/criar_imperio` · `/editar_perfil` · `/remover_imperio`\n"
            "`/turno` — Processar produção de todos\n"
            "`/censo` — Relatório geral · `/sancao` — Bloquear jogador"
        ),
        inline=False,
    )
    e_adm.add_field(
        name="💰  Recursos",
        value=(
            "`/dar_recursos` · `/definir_recursos` · `/transferir`\n"
            "`/definir_fabricas` · `/dar_fabrica` · `/recrutar`\n"
            "`/evento` · `/evento_narrativo`"
        ),
        inline=False,
    )
    e_adm.add_field(
        name="🔬  Tecnologia & Projetos",
        value=(
            "`/definir_tech` · `/registrar_projeto`\n"
            "`/concluir_projeto` · `/ver_projetos`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="🪐  Território",
        value=(
            "`/adicionar_planeta` · `/revelar_planeta`\n"
            "`/desenvolver_planeta` · `/destruir_planeta`\n"
            "`/transferir_planeta`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="🤝  Diplomacia",
        value=(
            "`/formar_alianca` · `/dissolver_alianca`\n"
            "`/registrar_tratado` · `/tornar_vassalo`\n"
            "`/libertar_vassalo`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="⚔️  Guerra",
        value=(
            "`/declarar_guerra` · `/assinar_paz`\n"
            "`/registrar_vitoria` · `/buff_guerra` · `/nerf_guerra`\n"
            "`/remover_buff` · `/adicionar_movimento` · `/limpar_movimentos`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="🗺️  Batalha Tática",
        value=(
            "`/criar_batalha` · `/adicionar_frota` · `/mover_frota`\n"
            "`/remover_frota` · `/atualizar_mapa_batalha` · `/finalizar_batalha`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="🌐  Mapa Galáctico",
        value=(
            "`/definir_fundo` · `/mapear_territorio`\n"
            "`/mapear_territorio_forcar` · `/verificar_colisoes`\n"
            "`/remover_territorio_mapa` · `/listar_mapa` · `/resetar_mapa`"
        ),
        inline=True,
    )
    e_adm.add_field(
        name="\u200b",
        value=(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Que o cosmos guie suas decisões, Comandante.*"
        ),
        inline=False,
    )
    e_adm.set_footer(text=f"⬡ Módulo VI / VI  ·  {RODAPE_PADRAO}")
    await ctx.send(embed=e_adm)


# ==============================
# EVENTOS
# ==============================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argumento faltando. Use `!ajuda` para ver o uso correto.")
        return
    raise error

_atualizar_mapa = None

# ── /ultimato ─────────────────────────────────────────────────────────
@bot.tree.command(name="ultimato", description="Envia um ultimato formal a outro império (1h para responder)")
@app_commands.describe(alvo="Império alvo do ultimato", exigencia="O que você exige do adversário")
async def slash_ultimato(interaction, alvo: discord.Member, exigencia: str):
    from guerra import ViewUltimato, carregar_guerras, salvar_guerras
    id_emissor = str(interaction.user.id)
    id_alvo    = str(alvo.id)
    if not imperio_existe(id_emissor):
        return await interaction.response.send_message("Você não tem um império registrado.", ephemeral=True)
    if not imperio_existe(id_alvo):
        return await interaction.response.send_message(f"{alvo.display_name} não tem um império.", ephemeral=True)
    if id_emissor == id_alvo:
        return await interaction.response.send_message("Você não pode enviar ultimato a si mesmo.", ephemeral=True)

    imp_emissor = dados["imperios"][id_emissor]
    imp_alvo    = dados["imperios"][id_alvo]

    registrar_historico(id_emissor, f"📨 Ultimato enviado a {imp_alvo['nome']}: {exigencia}")
    salvar(dados)

    cfg_guerra = carregar_guerras()

    embed = discord.Embed(
        title="📨  ULTIMATO RECEBIDO",
        description=f"{SEP_PADRAO}\n*As negociações chegaram ao limite. Uma resposta é exigida.*\n{SEP_PADRAO}",
        color=COR_OURO,
    )
    embed.add_field(name="⚔️ Emissor",     value=f"{interaction.user.mention}\n**{imp_emissor['nome']}**", inline=True)
    embed.add_field(name="🎯 Destinatário", value=f"{alvo.mention}\n**{imp_alvo['nome']}**",               inline=True)
    embed.add_field(name="📜 Exigência",    value=exigencia,                                                inline=False)
    embed.add_field(name="⏳ Prazo",        value="Você tem **1 hora** para aceitar ou recusar.",           inline=False)
    embed.set_image(url=BANNER_EVENTO)
    embed.set_footer(text=f"{RODAPE_PADRAO}  ·  Expira em 1 hora")

    view = ViewUltimato(id_emissor, id_alvo, exigencia, dados, salvar, cfg_guerra, atualizar_mapa)
    await interaction.response.send_message(content=f"📨 {alvo.mention} você recebeu um ultimato!", embed=embed, view=view)

@bot.event
async def on_ready():
    global _atualizar_mapa
    resultado = setup_mapa(bot, dados, salvar)
    if isinstance(resultado, tuple):
        _, _atualizar_mapa = resultado
    setup_guerra(bot, dados, salvar, atualizar_mapa)
    setup_batalha(bot, dados, salvar)

    # Sincroniza comandos slash em todos os servidores
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot logado como {bot.user}")
        print(f"   Slash commands sincronizados: {len(synced)}")
        print(f"   Impérios carregados: {len(dados.get('imperios', {}))}")
        # Lista os comandos registrados
        for cmd in synced:
            print(f"   /{cmd.name}")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

async def atualizar_mapa():
    if _atualizar_mapa:
        from mapa import carregar_mapa
        cfg = carregar_mapa()
        await _atualizar_mapa(bot, cfg, dados.get("imperios", {}))

# ── !sync — força sincronização dos slash commands ────────────────────
@bot.command(name="sync")
async def sync(ctx):
    cargos = [c.name.lower() for c in ctx.author.roles]
    if not ("adm" in cargos or "administrador" in cargos or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Sem permissão.")
    msg = await ctx.send("🔄 Sincronizando comandos slash...")
    try:
        synced = await bot.tree.sync()
        await msg.edit(content=f"✅ **{len(synced)} comandos** sincronizados! Aguarde até 1 min para aparecerem.")
        print(f"[sync] {len(synced)} comandos:")
        for cmd in synced:
            print(f"  /{cmd.name}")
    except Exception as e:
        await msg.edit(content=f"❌ Erro: `{e}`")

# ── !limpar_mapa — remove todos os territórios ───────────────────────
@bot.command(name="limpar_mapa")
async def limpar_mapa(ctx):
    cargos = [c.name.lower() for c in ctx.author.roles]
    if not ("adm" in cargos or "administrador" in cargos or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Sem permissão.")
    from mapa import carregar_mapa, salvar_mapa
    cfg_mapa = carregar_mapa()
    total = len(cfg_mapa.get("territorios", {}))
    if total == 0:
        return await ctx.send("📭 O mapa já está vazio.")
    cfg_mapa["territorios"] = {}
    cfg_mapa["msg_id"]      = None
    salvar_mapa(cfg_mapa)
    embed = discord.Embed(
        title="🗑️  Mapa Limpo",
        description=f"**{total}** território(s) removido(s).",
        color=0x7F1D1D
    )
    embed.set_footer(text=RODAPE_ADM)
    await ctx.send(embed=embed)
    await atualizar_mapa()

# ── !atualizar_mapa — força atualização do canal ─────────────────────
@bot.command(name="atualizar_mapa")
async def cmd_atualizar_mapa(ctx):
    cargos = [c.name.lower() for c in ctx.author.roles]
    if not ("adm" in cargos or "administrador" in cargos or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Sem permissão.")
    msg = await ctx.send("🔄 Atualizando mapa...")
    await atualizar_mapa()
    from mapa import carregar_mapa
    cfg_mapa = carregar_mapa()
    total    = len(cfg_mapa.get("territorios", {}))
    embed = discord.Embed(
        title="✅  Mapa Atualizado",
        description=f"Mapa gerado com **{total}** território(s).",
        color=0x3B0764
    )
    embed.set_footer(text=RODAPE_ADM)
    await msg.edit(content=None, embed=embed)

# ==============================
# TOKEN
# ==============================
bot.run(TOKEN)