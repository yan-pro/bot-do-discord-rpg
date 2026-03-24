"""
Sistema de Guerra - guerra.py
Integrado ao main.py via setup_guerra(bot, dados, salvar)
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json
import os
import math

ARQUIVO_GUERRA = "guerra_config.json"

COR_GUERRA   = 0x7F1D1D
COR_PAZ      = 0x3B0764
COR_ALERTA   = 0x7C3AED
COR_BUFF     = 0x1E3A5F
COR_NERF     = 0x4C0519
COR_ULTIMATO = 0x78350F
RODAPE_ADM   = "Conselho dos Administradores"
SEP          = "░▒▓█  Sistema Galáctico  █▓▒░"

BANNER_GUERRA = "https://i.imgur.com/QUmYDqY.jpg"
BANNER_PAZ    = "https://i.imgur.com/WqLuVnO.jpg"


# ==============================
# ARQUIVO DE GUERRAS
# ==============================
def carregar_guerras():
    if not os.path.exists(ARQUIVO_GUERRA):
        return {"guerras": [], "movimentos": []}
    with open(ARQUIVO_GUERRA, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {"guerras": [], "movimentos": []}

def salvar_guerras(cfg):
    with open(ARQUIVO_GUERRA, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def tem_permissao_adm(interaction):
    cargos = [c.name.lower() for c in interaction.user.roles]
    return "adm" in cargos or "administrador" in cargos or interaction.user.guild_permissions.administrator

def guerra_existe(cfg, id1, id2):
    for g in cfg["guerras"]:
        ids = {g["atacante"], g["defensor"]}
        if {id1, id2} == ids:
            return g
    return None

def get_imperio_por_id(dados, user_id):
    return dados["imperios"].get(str(user_id))

def get_imperio_por_nome(dados, nome):
    for id_u, imp in dados["imperios"].items():
        if imp["nome"].lower() == nome.lower():
            return id_u, imp
    return None, None

def registrar_historico(dados, id_u, evento):
    imp = dados["imperios"].get(id_u)
    if not imp:
        return
    entrada = f"[{datetime.now().strftime('%d/%m %H:%M')}] {evento}"
    if "historico" not in imp:
        imp["historico"] = []
    imp["historico"].insert(0, entrada)
    imp["historico"] = imp["historico"][:20]


# ==============================
# VIEW - ULTIMATO COM BOTOES
# ==============================
class ViewUltimato(discord.ui.View):
    def __init__(self, id_emissor, id_alvo, exigencia, dados_ref, salvar_fn, cfg_guerra, atualizar_mapa_fn):
        super().__init__(timeout=3600)  # 1 hora
        self.id_emissor      = id_emissor
        self.id_alvo         = id_alvo
        self.exigencia       = exigencia
        self.dados_ref       = dados_ref
        self.salvar_fn       = salvar_fn
        self.cfg_guerra      = cfg_guerra
        self.atualizar_mapa  = atualizar_mapa_fn
        self.encerrado       = False

    async def _encerrar(self, interaction, aceito):
        if self.encerrado:
            return await interaction.response.send_message("Este ultimato já foi respondido.", ephemeral=True)
        if str(interaction.user.id) != self.id_alvo:
            return await interaction.response.send_message("Apenas o destinatário pode responder.", ephemeral=True)
        self.encerrado = True
        for item in self.children:
            item.disabled = True
        imp_emissor = self.dados_ref["imperios"].get(self.id_emissor, {})
        imp_alvo    = self.dados_ref["imperios"].get(self.id_alvo, {})
        if aceito:
            registrar_historico(self.dados_ref, self.id_emissor, f"Ultimato aceito por {imp_alvo.get('nome','?')}")
            registrar_historico(self.dados_ref, self.id_alvo,    f"Aceitou ultimato de {imp_emissor.get('nome','?')}: {self.exigencia}")
            self.salvar_fn(self.dados_ref)
            embed = discord.Embed(
                title="✅  Ultimato Aceito",
                description=f"**{imp_alvo.get('nome','?')}** aceitou os termos.\n{SEP}",
                color=COR_PAZ
            )
            embed.add_field(name="📜 Termos Aceitos", value=self.exigencia, inline=False)
            embed.set_footer(text=RODAPE_ADM)
        else:
            registrar_historico(self.dados_ref, self.id_emissor, f"Ultimato RECUSADO por {imp_alvo.get('nome','?')}")
            registrar_historico(self.dados_ref, self.id_alvo,    f"Recusou ultimato de {imp_emissor.get('nome','?')}")
            self.salvar_fn(self.dados_ref)
            embed = discord.Embed(
                title="❌  Ultimato Recusado",
                description=f"**{imp_alvo.get('nome','?')}** recusou os termos. As consequências serão definidas pelo RP.",
                color=COR_GUERRA
            )
            embed.set_footer(text=RODAPE_ADM)
        await interaction.response.edit_message(embed=embed, view=self)
        if self.atualizar_mapa:
            await self.atualizar_mapa()

    @discord.ui.button(label="✅ Aceitar", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction, button):
        await self._encerrar(interaction, True)

    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction, button):
        await self._encerrar(interaction, False)


# ==============================
# GERAR MAPA DE GUERRA
# ==============================
def gerar_mapa_guerra(cfg_mapa, cfg_guerra, dados_imperios):
    """Gera o mapa galáctico com indicadores de guerra."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io, random, math as _math
    except ImportError:
        return None

    MAPA_W, MAPA_H = 2000, 1333
    COLS, ROWS      = 9, 8
    CW, CH          = MAPA_W / COLS, MAPA_H / ROWS
    COLUNAS         = [chr(ord('A') + i) for i in range(COLS)]

    def grade_xy(cel):
        ci = COLUNAS.index(cel[0])
        ri = int(cel[1:]) - 1
        return (int(CW*ci + CW/2), int(CH*ri + CH/2))

    def hex_rgb(h):
        h = h.lstrip("#")
        if len(h) != 6: return (108,33,168)
        return tuple(int(h[i:i+2],16) for i in (0,2,4))

    # Carrega fundo
    if os.path.exists("mapa_fundo.png"):
        base = Image.open("mapa_fundo.png").convert("RGBA")
        base = base.resize((MAPA_W, MAPA_H), Image.LANCZOS)
    else:
        base = Image.new("RGBA", (MAPA_W, MAPA_H), (8,4,20,255))

    overlay = Image.new("RGBA", (MAPA_W, MAPA_H), (0,0,0,0))
    draw    = ImageDraw.Draw(overlay)

    try:
        fn = ImageFont.truetype("arial.ttf", 18)
        fs = ImageFont.truetype("arial.ttf", 14)
        fb = ImageFont.truetype("arial.ttf", 22)
    except:
        fn = fs = fb = ImageFont.load_default()

    # Mapeia id_u → centro do território
    def centro_imperio(id_u):
        imp      = dados_imperios.get(id_u, {})
        planetas = cfg_mapa.get("territorios", {})
        pts = [
            (info["x"], info["y"])
            for nome, info in planetas.items()
            if nome in imp.get("planetas", []) or nome in imp.get("sistemas", [])
        ]
        if pts:
            return (sum(p[0] for p in pts)//len(pts), sum(p[1] for p in pts)//len(pts))
        return None

    # Linhas de guerra (vermelho pulsante)
    for g in cfg_guerra.get("guerras", []):
        id_at = g["atacante"]
        id_df = g["defensor"]
        c_at  = centro_imperio(id_at)
        c_df  = centro_imperio(id_df)
        if not c_at or not c_df:
            continue
        x1,y1 = c_at
        x2,y2 = c_df
        # Linha principal vermelha
        draw.line([(x1,y1),(x2,y2)], fill=(200,30,30,200), width=4)
        # Borda exterior mais suave
        draw.line([(x1,y1),(x2,y2)], fill=(255,80,80,80), width=8)
        # Ícone de espadas no meio
        mx, my = (x1+x2)//2, (y1+y2)//2
        draw.ellipse([mx-18,my-18,mx+18,my+18], fill=(150,20,20,220), outline=(255,60,60,255), width=2)
        draw.text((mx,my), "⚔", fill=(255,200,200,255), font=fn, anchor="mm")
        # Nomes
        imp_at = dados_imperios.get(id_at, {})
        imp_df = dados_imperios.get(id_df, {})
        draw.text((x1, y1-25), f"⚔ {imp_at.get('nome','?')}", fill=(255,100,100,220), font=fs, anchor="mm")
        draw.text((x2, y2-25), f"🛡 {imp_df.get('nome','?')}", fill=(100,180,255,220), font=fs, anchor="mm")

    # Setas de movimentação
    for mov in cfg_guerra.get("movimentos", []):
        cel_orig = mov.get("origem")
        cel_dest = mov.get("destino")
        cor_hex  = mov.get("cor", "FFFF00")
        label    = mov.get("label", "")
        if not cel_orig or not cel_dest:
            continue
        try:
            x1,y1 = grade_xy(cel_orig)
            x2,y2 = grade_xy(cel_dest)
        except:
            continue
        r,g,b = hex_rgb(cor_hex)
        # Linha da seta
        draw.line([(x1,y1),(x2,y2)], fill=(r,g,b,200), width=3)
        # Ponta da seta
        ang = _math.atan2(y2-y1, x2-x1)
        tam = 20
        ax1 = int(x2 - tam*_math.cos(ang-0.4))
        ay1 = int(y2 - tam*_math.sin(ang-0.4))
        ax2 = int(x2 - tam*_math.cos(ang+0.4))
        ay2 = int(y2 - tam*_math.sin(ang+0.4))
        draw.polygon([(x2,y2),(ax1,ay1),(ax2,ay2)], fill=(r,g,b,230))
        if label:
            draw.text(((x1+x2)//2, (y1+y2)//2 - 12), label, fill=(r,g,b,220), font=fs, anchor="mm")

    # Status de guerras no canto
    guerras = cfg_guerra.get("guerras", [])
    if guerras:
        lx,ly = 10, MAPA_H - len(guerras)*30 - 50
        draw.rectangle([lx-5,ly-5,lx+340,ly+len(guerras)*30+35], fill=(20,5,5,210), outline=(180,40,40,200))
        draw.text((lx+165,ly+3), "EM GUERRA", fill=(255,80,80,255), font=fn, anchor="mt")
        gy = ly + 25
        for g in guerras:
            n_at = dados_imperios.get(g["atacante"],{}).get("nome","?")
            n_df = dados_imperios.get(g["defensor"], {}).get("nome","?")
            draw.text((lx+5, gy), f"⚔ {n_at}  vs  {n_df}", fill=(255,150,150,230), font=fs)
            gy += 26

    final = Image.alpha_composite(base, overlay).convert("RGB")
    buf = __import__("io").BytesIO()
    final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ==============================
# SETUP
# ==============================
def setup_guerra(bot, dados_ref, salvar_fn, atualizar_mapa_fn=None):
    cfg = carregar_guerras()

    # ── /declarar_guerra ─────────────────────────────────────────────
    @bot.tree.command(name="declarar_guerra", description="[ADM] Declara guerra entre dois impérios")
    @app_commands.describe(atacante="Jogador atacante", defensor="Jogador defensor", motivo="Motivo da guerra")
    async def slash_declarar_guerra(interaction, atacante: discord.Member, defensor: discord.Member, motivo: str = "Conflito galáctico"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_at = str(atacante.id)
        id_df = str(defensor.id)
        if id_at == id_df:
            return await interaction.response.send_message("Um império não pode declarar guerra a si mesmo.", ephemeral=True)
        for mid in [id_at, id_df]:
            if mid not in dados_ref["imperios"]:
                return await interaction.response.send_message(f"Imperio não encontrado.", ephemeral=True)
        if guerra_existe(cfg, id_at, id_df):
            return await interaction.response.send_message("Estes impérios já estão em guerra!", ephemeral=True)

        imp_at = dados_ref["imperios"][id_at]
        imp_df = dados_ref["imperios"][id_df]
        cfg["guerras"].append({
            "atacante": id_at,
            "defensor": id_df,
            "motivo":   motivo,
            "inicio":   datetime.now().strftime("%d/%m/%Y %H:%M"),
            "buffs":    {},
            "nerfs":    {},
        })
        salvar_guerras(cfg)
        registrar_historico(dados_ref, id_at, f"⚔️ GUERRA declarada contra {imp_df['nome']} — {motivo}")
        registrar_historico(dados_ref, id_df, f"⚔️ GUERRA recebida de {imp_at['nome']} — {motivo}")
        salvar_fn(dados_ref)

        embed = discord.Embed(
            title="⚔️  GUERRA DECLARADA",
            description=f"{SEP}\n*O cosmos treme com o rugido das frotas em batalha.*\n{SEP}",
            color=COR_GUERRA
        )
        embed.add_field(name="⚔️ Atacante",  value=f"{atacante.mention}\n**{imp_at['nome']}**", inline=True)
        embed.add_field(name="🛡️ Defensor",  value=f"{defensor.mention}\n**{imp_df['nome']}**", inline=True)
        embed.add_field(name="📜 Motivo",     value=motivo, inline=False)
        embed.add_field(name="🗺️ Mapa",       value="O conflito já aparece no mapa galáctico.", inline=False)
        embed.set_image(url=BANNER_GUERRA)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        await interaction.response.send_message(
            content=f"⚔️ {atacante.mention} declarou guerra a {defensor.mention}!",
            embed=embed
        )
        if atualizar_mapa_fn:
            await atualizar_mapa_fn()

    # ── /assinar_paz ─────────────────────────────────────────────────
    @bot.tree.command(name="assinar_paz", description="[ADM] Encerra a guerra entre dois impérios")
    @app_commands.describe(imp1="Primeiro jogador", imp2="Segundo jogador", termos="Termos da paz")
    async def slash_assinar_paz(interaction, imp1: discord.Member, imp2: discord.Member, termos: str = "Paz sem condições"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id1 = str(imp1.id)
        id2 = str(imp2.id)
        g   = guerra_existe(cfg, id1, id2)
        if not g:
            return await interaction.response.send_message("Estes impérios não estão em guerra.", ephemeral=True)

        cfg["guerras"].remove(g)
        # Remove movimentos relacionados
        cfg["movimentos"] = [m for m in cfg["movimentos"] if m.get("id_at") not in {id1,id2} and m.get("id_df") not in {id1,id2}]
        # Remove buffs/nerfs de guerra de ambos
        for mid in [id1, id2]:
            imp = dados_ref["imperios"].get(mid, {})
            imp.pop("buff_guerra", None)
            imp.pop("nerf_guerra", None)
        salvar_guerras(cfg)

        n1 = dados_ref["imperios"].get(id1,{}).get("nome","?")
        n2 = dados_ref["imperios"].get(id2,{}).get("nome","?")
        registrar_historico(dados_ref, id1, f"🕊️ Paz assinada com {n2} — {termos}")
        registrar_historico(dados_ref, id2, f"🕊️ Paz assinada com {n1} — {termos}")
        salvar_fn(dados_ref)

        embed = discord.Embed(
            title="🕊️  TRATADO DE PAZ ASSINADO",
            description=f"{SEP}\n*A galáxia respira aliviada. O conflito chegou ao fim.*\n{SEP}",
            color=COR_PAZ
        )
        embed.add_field(name="🏛️ Impérios",   value=f"**{n1}**  ×  **{n2}**", inline=False)
        embed.add_field(name="📜 Termos",      value=termos, inline=False)
        embed.set_image(url=BANNER_PAZ)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        await interaction.response.send_message(
            content=f"🕊️ {imp1.mention} e {imp2.mention} assinaram paz!",
            embed=embed
        )
        if atualizar_mapa_fn:
            await atualizar_mapa_fn()

    # ── /buff_guerra ──────────────────────────────────────────────────
    @bot.tree.command(name="buff_guerra", description="[ADM] Aplica bônus de produção de guerra a um império")
    @app_commands.describe(
        membro   = "Jogador",
        tipo     = "Tipo do buff",
        pct      = "Porcentagem de bônus (ex: 50 = +50%)",
        descricao= "Motivo do buff"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="⚔️ Produção Militar (+unidades/turno)", value="militar"),
        app_commands.Choice(name="🏭 Produção Industrial (+minérios)",     value="industrial"),
        app_commands.Choice(name="💰 Economia de Guerra (+PIB/turno)",     value="economico"),
        app_commands.Choice(name="🪖 Recrutamento (+recrutas/turno)",      value="recrutas"),
    ])
    async def slash_buff_guerra(interaction, membro: discord.Member, tipo: str, pct: int, descricao: str = "Mobilização de guerra"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_u = str(membro.id)
        if id_u not in dados_ref["imperios"]:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        if pct <= 0 or pct > 500:
            return await interaction.response.send_message("Porcentagem deve ser entre 1 e 500.", ephemeral=True)

        imp = dados_ref["imperios"][id_u]
        if "buff_guerra" not in imp:
            imp["buff_guerra"] = {}
        imp["buff_guerra"][tipo] = pct
        registrar_historico(dados_ref, id_u, f"🔺 Buff de guerra: {tipo} +{pct}% — {descricao}")
        salvar_fn(dados_ref)

        icons = {"militar":"⚔️","industrial":"🏭","economico":"💰","recrutas":"🪖"}
        embed = discord.Embed(
            title=f"🔺  Buff de Guerra Aplicado",
            description=f"*As indústrias de guerra operam em capacidade máxima.*",
            color=COR_BUFF
        )
        embed.add_field(name=f"{icons[tipo]} Tipo",     value=tipo.title(),    inline=True)
        embed.add_field(name="📈 Bônus",                value=f"+{pct}%",      inline=True)
        embed.add_field(name="📝 Motivo",               value=descricao,       inline=True)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {imp['nome']}")
        await interaction.response.send_message(
            content=f"🔺 {membro.mention} recebeu buff de guerra!",
            embed=embed
        )

    # ── /nerf_guerra ──────────────────────────────────────────────────
    @bot.tree.command(name="nerf_guerra", description="[ADM] Aplica penalidade de dano de guerra a um império")
    @app_commands.describe(
        membro    = "Jogador penalizado",
        tipo      = "O que foi danificado",
        pct       = "Porcentagem de perda (ex: 75 = -75%)",
        estrutura = "O que foi atacado (ex: Mundo Forja, Capital, etc)",
        descricao = "Descrição do dano"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🏭 Produção Industrial (-minérios/turno)", value="industrial"),
        app_commands.Choice(name="💰 Economia (-PIB/turno)",                 value="economico"),
        app_commands.Choice(name="🪖 Capacidade Militar (-recrutas)",        value="recrutas"),
        app_commands.Choice(name="🔬 Tecnologia (congelada)",                value="tecnologia"),
        app_commands.Choice(name="🌐 Geral (todos os recursos)",             value="geral"),
    ])
    async def slash_nerf_guerra(interaction, membro: discord.Member, tipo: str, pct: int, estrutura: str = "Estrutura danificada", descricao: str = "Dano de combate"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_u = str(membro.id)
        if id_u not in dados_ref["imperios"]:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        if pct <= 0 or pct > 100:
            return await interaction.response.send_message("Porcentagem deve ser entre 1 e 100.", ephemeral=True)

        imp = dados_ref["imperios"][id_u]
        if "nerf_guerra" not in imp:
            imp["nerf_guerra"] = {}
        imp["nerf_guerra"][tipo] = pct
        registrar_historico(dados_ref, id_u, f"🔻 Nerf de guerra: {estrutura} -{pct}% {tipo} — {descricao}")
        salvar_fn(dados_ref)

        icons = {"industrial":"🏭","economico":"💰","recrutas":"🪖","tecnologia":"🔬","geral":"🌐"}
        embed = discord.Embed(
            title=f"🔻  Dano de Guerra Aplicado",
            description=f"*{estrutura} foi severamente danificada.*",
            color=COR_NERF
        )
        embed.add_field(name=f"{icons[tipo]} Área Danificada", value=tipo.title(),  inline=True)
        embed.add_field(name="📉 Penalidade",                  value=f"-{pct}%",    inline=True)
        embed.add_field(name="🏗️ Estrutura",                   value=estrutura,     inline=True)
        embed.add_field(name="📝 Descrição",                   value=descricao,     inline=False)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {imp['nome']}")
        await interaction.response.send_message(
            content=f"🔻 {membro.mention} sofreu dano de guerra!",
            embed=embed
        )

    # ── /remover_buff ─────────────────────────────────────────────────
    @bot.tree.command(name="remover_buff", description="[ADM] Remove buff ou nerf de guerra de um império")
    @app_commands.describe(membro="Jogador", tipo="buff ou nerf")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Remover BUFF", value="buff"),
        app_commands.Choice(name="Remover NERF", value="nerf"),
        app_commands.Choice(name="Remover AMBOS", value="ambos"),
    ])
    async def slash_remover_buff(interaction, membro: discord.Member, tipo: str):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_u = str(membro.id)
        if id_u not in dados_ref["imperios"]:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        imp = dados_ref["imperios"][id_u]
        if tipo in ("buff","ambos"):
            imp.pop("buff_guerra", None)
        if tipo in ("nerf","ambos"):
            imp.pop("nerf_guerra", None)
        registrar_historico(dados_ref, id_u, f"Efeitos de guerra removidos: {tipo}")
        salvar_fn(dados_ref)
        embed = discord.Embed(title="⚙️  Efeitos de Guerra Removidos", color=COR_ALERTA)
        embed.add_field(name="Removido", value=tipo.upper(), inline=True)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {imp['nome']}")
        await interaction.response.send_message(embed=embed)

    # ── /adicionar_movimento ──────────────────────────────────────────
    @bot.tree.command(name="adicionar_movimento", description="[ADM] Adiciona seta de movimentação no mapa de guerra")
    @app_commands.describe(
        origem  = "Célula de origem (ex: D4)",
        destino = "Célula de destino (ex: E5)",
        label   = "Nome da força/frota",
        cor     = "Cor da seta em hex (ex: FF0000)",
    )
    async def slash_adicionar_movimento(interaction, origem: str, destino: str, label: str = "", cor: str = "FF4444"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        cfg["movimentos"].append({"origem": origem.upper(), "destino": destino.upper(), "label": label, "cor": cor})
        salvar_guerras(cfg)
        embed = discord.Embed(title="🗺️  Movimento Registrado", color=COR_GUERRA)
        embed.add_field(name="📍 Origem",  value=origem.upper(),  inline=True)
        embed.add_field(name="🎯 Destino", value=destino.upper(), inline=True)
        embed.add_field(name="🏷️ Frota",   value=label or "—",    inline=True)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed)
        if atualizar_mapa_fn:
            await atualizar_mapa_fn()

    # ── /limpar_movimentos ────────────────────────────────────────────
    @bot.tree.command(name="limpar_movimentos", description="[ADM] Remove todas as setas de movimentação do mapa")
    async def slash_limpar_movimentos(interaction):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        cfg["movimentos"] = []
        salvar_guerras(cfg)
        await interaction.response.send_message("🗺️ Movimentos limpos do mapa.")
        if atualizar_mapa_fn:
            await atualizar_mapa_fn()

    # ── /status_guerras ───────────────────────────────────────────────
    @bot.tree.command(name="status_guerras", description="Lista todos os conflitos ativos")
    async def slash_status_guerras(interaction):
        guerras = cfg.get("guerras", [])
        if not guerras:
            embed = discord.Embed(title="🕊️  Nenhum Conflito Ativo", description="A galáxia está em paz.", color=COR_PAZ)
            return await interaction.response.send_message(embed=embed)
        embed = discord.Embed(
            title="⚔️  Conflitos Galácticos Ativos",
            description=f"{SEP}\n*{len(guerras)} guerra(s) em andamento.*\n{SEP}",
            color=COR_GUERRA
        )
        for g in guerras:
            n_at = dados_ref["imperios"].get(g["atacante"],{}).get("nome","?")
            n_df = dados_ref["imperios"].get(g["defensor"], {}).get("nome","?")
            embed.add_field(
                name=f"⚔️ {n_at}  vs  {n_df}",
                value=f"📜 {g.get('motivo','?')}\n📅 Início: {g.get('inicio','?')}",
                inline=False
            )
        embed.set_image(url=BANNER_GUERRA)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed)

    # ── !ultimato ─────────────────────────────────────────────────────
    @bot.command(name="ultimato")
    async def ultimato(ctx, alvo: discord.Member = None, *, exigencia: str = None):
        id_emissor = str(ctx.author.id)
        if id_emissor not in dados_ref["imperios"]:
            return await ctx.send("Você não tem um império registrado.")
        if not alvo or not exigencia:
            return await ctx.send("Uso: `!ultimato @membro <exigência>`\nEx: `!ultimato @Fulano Retire suas tropas de Kepler-7`")
        if alvo.id == ctx.author.id:
            return await ctx.send("Você não pode enviar ultimato a si mesmo.")
        id_alvo = str(alvo.id)
        if id_alvo not in dados_ref["imperios"]:
            return await ctx.send(f"{alvo.display_name} não tem um império registrado.")

        imp_emissor = dados_ref["imperios"][id_emissor]
        imp_alvo    = dados_ref["imperios"][id_alvo]
        registrar_historico(dados_ref, id_emissor, f"📨 Ultimato enviado a {imp_alvo['nome']}: {exigencia}")
        salvar_fn(dados_ref)

        embed = discord.Embed(
            title="📨  ULTIMATO RECEBIDO",
            description=f"{SEP}\n*As negociações chegaram ao limite. Uma resposta é exigida.*\n{SEP}",
            color=COR_ULTIMATO
        )
        embed.add_field(name="⚔️ Emissor",    value=f"{ctx.author.mention}\n**{imp_emissor['nome']}**", inline=True)
        embed.add_field(name="🎯 Destinatário",value=f"{alvo.mention}\n**{imp_alvo['nome']}**",         inline=True)
        embed.add_field(name="📜 Exigência",   value=exigencia,                                          inline=False)
        embed.add_field(name="⏳ Prazo",       value="Responda antes que seja tarde demais...",           inline=False)
        embed.set_image(url=BANNER_GUERRA)
        embed.set_footer(text="Sistema Galáctico  ·  Expira em 1 hora")

        view = ViewUltimato(id_emissor, id_alvo, exigencia, dados_ref, salvar_fn, cfg, atualizar_mapa_fn)
        await ctx.send(content=f"📨 {alvo.mention} você recebeu um ultimato!", embed=embed, view=view)

    # ── !render ───────────────────────────────────────────────────────
    @bot.command(name="render")
    async def render(ctx):
        id_u = str(ctx.author.id)
        if id_u not in dados_ref["imperios"]:
            return await ctx.send("Você não tem um império registrado.")
        em_guerra = [g for g in cfg["guerras"] if id_u in (g["atacante"],g["defensor"])]
        if not em_guerra:
            return await ctx.send("❌ Seu império não está em nenhuma guerra ativa.")

        imp = dados_ref["imperios"][id_u]
        if len(em_guerra) == 1:
            g      = em_guerra[0]
            id_opp = g["defensor"] if g["atacante"] == id_u else g["atacante"]
            n_opp  = dados_ref["imperios"].get(id_opp,{}).get("nome","?")
        else:
            nomes = [dados_ref["imperios"].get(g["defensor"] if g["atacante"]==id_u else g["atacante"],{}).get("nome","?") for g in em_guerra]
            return await ctx.send(f"Você está em múltiplas guerras: {', '.join(nomes)}\nContate o ADM para registrar a rendição.")

        # Registra rendição no histórico de guerras do império
        if "historico_guerras" not in imp:
            imp["historico_guerras"] = []
        imp["historico_guerras"].insert(0, {
            "resultado":  "derrota",
            "adversario": n_opp,
            "data":       datetime.now().strftime("%d/%m/%Y"),
            "tipo":       "rendição",
        })
        opp = dados_ref["imperios"].get(id_opp, {})
        if "historico_guerras" not in opp:
            opp["historico_guerras"] = []
        opp["historico_guerras"].insert(0, {
            "resultado":  "vitória",
            "adversario": imp["nome"],
            "data":       datetime.now().strftime("%d/%m/%Y"),
            "tipo":       "rendição aceita",
        })
        registrar_historico(dados_ref, id_u,   f"🏳️ RENDIÇÃO declarada contra {n_opp}")
        registrar_historico(dados_ref, id_opp, f"🏳️ {imp['nome']} se rendeu!")
        salvar_fn(dados_ref)

        embed = discord.Embed(
            title="🏳️  RENDIÇÃO DECLARADA",
            description=f"{SEP}\n*{imp['nome']} baixa suas armas diante do cosmos.*\n{SEP}",
            color=COR_GUERRA
        )
        embed.add_field(name="🏳️ Rendido",       value=f"**{imp['nome']}**", inline=True)
        embed.add_field(name="⚔️ Vencedor",       value=f"**{n_opp}**",      inline=True)
        embed.add_field(name="📋 Próximos Passos",
            value="O ADM irá definir os termos — use `/tornar_vassalo` para aplicar a vassalagem.", inline=False)
        embed.set_image(url=BANNER_GUERRA)
        embed.set_footer(text="Sistema Galáctico  ·  Aguardando resolução do ADM")
        await ctx.send(content=f"@everyone 🏳️ **{imp['nome']}** se rendeu!", embed=embed)

    # ── /tornar_vassalo ───────────────────────────────────────────────
    @bot.tree.command(name="tornar_vassalo", description="[ADM] Torna um império vassalo/fantoche de outro")
    @app_commands.describe(
        vassalo   = "Império que foi derrotado",
        soberano  = "Império que controla o vassalo",
        tipo      = "Tipo de submissão",
        tributo   = "Porcentagem do PIB pago como tributo por turno (ex: 20)",
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🔗 Vassalo (paga tributo, mantém autonomia)", value="vassalo"),
        app_commands.Choice(name="🤖 Fantoche (controlado diretamente)",        value="fantoche"),
        app_commands.Choice(name="🏴 Ocupado (território sob ocupação)",        value="ocupado"),
    ])
    async def slash_tornar_vassalo(interaction, vassalo: discord.Member, soberano: discord.Member, tipo: str, tributo: int = 20):
        if not _adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_v = str(vassalo.id); id_s = str(soberano.id)
        for mid in [id_v, id_s]:
            if mid not in dados_ref["imperios"]:
                return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        if tributo < 0 or tributo > 100:
            return await interaction.response.send_message("Tributo deve ser entre 0 e 100%.", ephemeral=True)

        imp_v = dados_ref["imperios"][id_v]
        imp_s = dados_ref["imperios"][id_s]

        # Aplica status de vassalagem
        imp_v["vassalagem"] = {
            "tipo":     tipo,
            "soberano": id_s,
            "nome_soberano": imp_s["nome"],
            "tributo":  tributo,
            "desde":    datetime.now().strftime("%d/%m/%Y"),
        }
        # Soberano registra o vassalo
        if "vassalos" not in imp_s:
            imp_s["vassalos"] = []
        if id_v not in imp_s["vassalos"]:
            imp_s["vassalos"].append(id_v)

        registrar_historico(dados_ref, id_v, f"🔗 Tornou-se {tipo} de {imp_s['nome']} — tributo: {tributo}%/turno")
        registrar_historico(dados_ref, id_s, f"👑 {imp_v['nome']} tornou-se seu {tipo}")
        salvar_fn(dados_ref)

        icons = {"vassalo":"🔗","fantoche":"🤖","ocupado":"🏴"}
        embed = discord.Embed(
            title=f"{icons[tipo]}  {tipo.title()} Estabelecido",
            description=f"{SEP}\n*O cosmos testemunha a submissão de **{imp_v['nome']}**.*\n{SEP}",
            color=0x4C0519
        )
        embed.add_field(name=f"{icons[tipo]} {tipo.title()}", value=f"**{imp_v['nome']}**",  inline=True)
        embed.add_field(name="👑 Soberano",                   value=f"**{imp_s['nome']}**",  inline=True)
        embed.add_field(name="💸 Tributo",                    value=f"{tributo}% do PIB/turno", inline=True)
        embed.add_field(name="📋 Efeitos",
            value=f"• {imp_v['nome']} paga {tributo}% do PIB gerado por turno\n"
                  f"• Aparece como {tipo} no perfil\n"
                  f"• Use `/libertar_vassalo` para remover", inline=False)
        embed.set_footer(text=SEP)
        await interaction.response.send_message(content=f"@everyone {icons[tipo]} **{imp_v['nome']}** agora é {tipo} de **{imp_s['nome']}**!", embed=embed)
        if atualizar_mapa_fn:
            await atualizar_mapa_fn()

    # ── /libertar_vassalo ─────────────────────────────────────────────
    @bot.tree.command(name="libertar_vassalo", description="[ADM] Remove o status de vassalo de um império")
    @app_commands.describe(membro="Império a ser libertado", motivo="Motivo da libertação")
    async def slash_libertar_vassalo(interaction, membro: discord.Member, motivo: str = "Libertação"):
        if not _adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_v = str(membro.id)
        if id_v not in dados_ref["imperios"]:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        imp_v = dados_ref["imperios"][id_v]
        vassalagem = imp_v.get("vassalagem")
        if not vassalagem:
            return await interaction.response.send_message(f"**{imp_v['nome']}** não é vassalo de ninguém.", ephemeral=True)

        id_s  = vassalagem.get("soberano")
        imp_s = dados_ref["imperios"].get(id_s, {})
        if id_s and "vassalos" in imp_s and id_v in imp_s["vassalos"]:
            imp_s["vassalos"].remove(id_v)
        del imp_v["vassalagem"]
        registrar_historico(dados_ref, id_v, f"🆓 Libertado de {imp_s.get('nome','?')} — {motivo}")
        if id_s: registrar_historico(dados_ref, id_s, f"🆓 {imp_v['nome']} foi libertado — {motivo}")
        salvar_fn(dados_ref)

        embed = discord.Embed(title="🆓  Império Libertado", description=f"**{imp_v['nome']}** recuperou sua soberania.", color=0x1E3A5F)
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)
        embed.set_footer(text=SEP)
        await interaction.response.send_message(embed=embed)

    # ── /registrar_vitoria ────────────────────────────────────────────
    @bot.tree.command(name="registrar_vitoria", description="[ADM] Registra manualmente uma vitória/derrota no histórico")
    @app_commands.describe(
        membro     = "Império",
        resultado  = "Vitória ou derrota",
        adversario = "Nome do adversário",
        descricao  = "Descrição do conflito",
    )
    @app_commands.choices(resultado=[
        app_commands.Choice(name="⚔️ Vitória",  value="vitória"),
        app_commands.Choice(name="🏳️ Derrota",  value="derrota"),
        app_commands.Choice(name="🤝 Empate",   value="empate"),
    ])
    async def slash_registrar_vitoria(interaction, membro: discord.Member, resultado: str, adversario: str, descricao: str = ""):
        if not _adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        id_u = str(membro.id)
        if id_u not in dados_ref["imperios"]:
            return await interaction.response.send_message("Império não encontrado.", ephemeral=True)
        imp = dados_ref["imperios"][id_u]
        if "historico_guerras" not in imp:
            imp["historico_guerras"] = []
        imp["historico_guerras"].insert(0, {
            "resultado":  resultado,
            "adversario": adversario,
            "data":       datetime.now().strftime("%d/%m/%Y"),
            "tipo":       descricao or "Conflito galáctico",
        })
        salvar_fn(dados_ref)
        embed = discord.Embed(title="📋  Registro de Guerra Adicionado", color=COR_GUERRA)
        embed.add_field(name="🏛️ Império",    value=imp["nome"],  inline=True)
        embed.add_field(name="📊 Resultado",  value=resultado,    inline=True)
        embed.add_field(name="⚔️ Adversário", value=adversario,   inline=True)
        embed.set_footer(text=SEP)
        await interaction.response.send_message(embed=embed)

    return cfg


# ── Auxiliar local ────────────────────────────────────────────────────
def _adm(interaction):
    cargos = [c.name.lower() for c in interaction.user.roles]
    return "adm" in cargos or "administrador" in cargos or interaction.user.guild_permissions.administrator
    @bot.command(name="mapa_guerra")
    async def mapa_guerra_cmd(ctx):
        from mapa import carregar_mapa
        cfg_mapa = carregar_mapa()
        buf = gerar_mapa_guerra(cfg_mapa, cfg, dados_ref.get("imperios",{}))
        if not buf:
            return await ctx.send("Pillow não instalado ou nenhuma guerra ativa.")
        embed = discord.Embed(
            title="⚔️  Mapa de Guerra Galáctico",
            description=f"{SEP}\n*Conflitos ativos e movimentações de frota.*",
            color=COR_GUERRA
        )
        embed.add_field(name="⚔️ Guerras Ativas", value=str(len(cfg.get("guerras",[]))), inline=True)
        embed.add_field(name="🗺️ Movimentos",      value=str(len(cfg.get("movimentos",[]))), inline=True)
        embed.set_footer(text="Sistema Galáctico  ·  Use /adicionar_movimento para setas")
        f = discord.File(buf, filename="mapa_guerra.png")
        embed.set_image(url="attachment://mapa_guerra.png")
        await ctx.send(file=f, embed=embed)

    return cfg