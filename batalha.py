"""
Sistema de Batalha - batalha.py
Integrado ao main.py via setup_batalha(bot, dados, salvar)

Comandos:
  /criar_batalha   — ADM cria batalha no post do forum
  /adicionar_frota — ADM adiciona frota ao mapa
  /mover_frota     — ADM move frota no grid
  /remover_frota   — ADM remove frota
  /atualizar_mapa_batalha — ADM atualiza a imagem no post
  /finalizar_batalha — ADM encerra a batalha
  !status_batalha  — jogador ve o status da batalha no canal atual
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import json, os, io, math, random

ARQUIVO_BATALHA = "batalha_config.json"

COR_BATALHA  = 0x7F1D1D
COR_TERRESTRE= 0x3B1A08
COR_SUCESSO  = 0x1A3B0A
COR_ALERTA   = 0x7C3AED
RODAPE_ADM   = "Conselho dos Administradores"
SEP          = "░▒▓█  Sistema Galáctico  █▓▒░"

# Grid de batalha
GRID_COLS = 5   # I II III IV V
GRID_ROWS = 4   # 1 2 3 4
COL_LABELS = ["I","II","III","IV","V"]

# Grid terrestre diferente
GRID_COLS_T = 6
GRID_ROWS_T = 5
COL_LABELS_T = ["A","B","C","D","E","F"]


def carregar_batalhas():
    if not os.path.exists(ARQUIVO_BATALHA):
        return {"batalhas": {}}
    with open(ARQUIVO_BATALHA,"r",encoding="utf-8") as f:
        try: return json.load(f)
        except: return {"batalhas": {}}

def salvar_batalhas(cfg):
    with open(ARQUIVO_BATALHA,"w",encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def tem_permissao_adm(interaction):
    cargos = [c.name.lower() for c in interaction.user.roles]
    return "adm" in cargos or "administrador" in cargos or interaction.user.guild_permissions.administrator

def hex_rgb(h):
    h=h.lstrip("#")
    if len(h)!=6: return (108,33,168)
    return tuple(int(h[i:i+2],16) for i in (0,2,4))


# ==============================
# GERAR IMAGEM DE BATALHA
# ==============================
def gerar_mapa_batalha(batalha: dict) -> io.BytesIO | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    modo      = batalha.get("modo", "espacial")
    terrestre = (modo == "terrestre")

    BW, BH   = 1000, 700
    GC       = GRID_COLS_T if terrestre else GRID_COLS
    GR       = GRID_ROWS_T if terrestre else GRID_ROWS
    CL       = COL_LABELS_T if terrestre else COL_LABELS
    BCW, BCH = (BW-160)/GC, (BH-80)/GR
    OX, OY   = 40, 50   # offset do grid

    # Fundo
    if terrestre:
        # Terreno marrom/verde
        base = Image.new("RGBA",(BW,BH),(12,8,4,255))
        d0   = ImageDraw.Draw(base)
        rng  = random.Random(batalha.get("seed",42))
        # Manchas de terreno
        for _ in range(80):
            tx=rng.randint(0,BW); ty=rng.randint(0,BH)
            tw=rng.randint(20,80); th=rng.randint(15,50)
            tg=rng.randint(15,45)
            d0.ellipse([tx,ty,tx+tw,ty+th],fill=(tg,tg+10,tg-5,60))
    else:
        # Fundo espacial
        base = Image.new("RGBA",(BW,BH),(5,3,16,255))
        d0   = ImageDraw.Draw(base)
        rng  = random.Random(batalha.get("seed",42))
        for _ in range(350):
            sx=rng.randint(0,BW); sy=rng.randint(0,BH)
            sb=rng.randint(70,220); sr=rng.randint(1,2)
            d0.ellipse([sx-sr,sy-sr,sx+sr,sy+sr],fill=(sb,sb,sb,110))

    ov = Image.new("RGBA",(BW,BH),(0,0,0,0))
    dw = ImageDraw.Draw(ov)

    try:
        fn=ImageFont.truetype("arial.ttf",14); fs=ImageFont.truetype("arial.ttf",11)
        fb=ImageFont.truetype("arial.ttf",18); fw=ImageFont.truetype("arial.ttf",13)
        ft=ImageFont.truetype("arial.ttf",22)
    except:
        fn=fs=fb=fw=ft=ImageFont.load_default()

    # ── Grade ──────────────────────────────────────────────────────
    cor_grade = (60,50,30,80) if terrestre else (70,60,110,60)
    for ci in range(GC+1):
        gx=int(OX+BCW*ci)
        dw.line([(gx,OY),(gx,OY+BCH*GR)],fill=cor_grade,width=1)
    for ri in range(GR+1):
        gy=int(OY+BCH*ri)
        dw.line([(OX,gy),(OX+BCW*GC,gy)],fill=cor_grade,width=1)

    # Rótulos grade
    for ci,lbl in enumerate(CL):
        gx=int(OX+BCW*ci+BCW/2)
        dw.text((gx,OY-18),lbl,fill=(160,150,200,180),font=fs,anchor="mm")
    for ri in range(GR):
        gy=int(OY+BCH*ri+BCH/2)
        dw.text((OX-15,gy),str(ri+1),fill=(160,150,200,180),font=fs,anchor="mm")

    # ── Objetivo central ──────────────────────────────────────────
    planeta = batalha.get("planeta","?")
    cx = int(OX+BCW*GC/2)
    cy = int(OY+BCH*GR/2)
    if terrestre:
        # Base militar no centro
        dw.rectangle([cx-20,cy-20,cx+20,cy+20],fill=(60,40,10,200),outline=(200,150,50,230),width=3)
        dw.rectangle([cx-24,cy-24,cx+24,cy+24],fill=None,outline=(200,150,50,100),width=1)
        dw.text((cx,cy),"🏰",fill=(255,200,80,255),font=fs,anchor="mm")
    else:
        dw.ellipse([cx-20,cy-20,cx+20,cy+20],fill=(70,55,15,200),outline=(255,215,0,230),width=3)
        dw.ellipse([cx-25,cy-25,cx+25,cy+25],fill=None,outline=(255,215,0,100),width=2)
        dw.text((cx,cy),"★",fill=(255,230,100,255),font=fn,anchor="mm")
    dw.text((cx,cy-30),planeta,fill=(255,230,130,240),font=fn,anchor="mb")
    dw.text((cx,cy+26),"OBJETIVO",fill=(255,80,80,190),font=fs,anchor="mt")

    # Zona de conflito
    zr=int(min(BCW,BCH)*0.8)
    dw.ellipse([cx-zr,cy-zr,cx+zr,cy+zr],fill=(130,20,20,12),outline=(255,50,50,45),width=1)

    # ── Frotas ────────────────────────────────────────────────────
    frotas = batalha.get("frotas", {})
    for fid, frota in frotas.items():
        col  = frota.get("col",0)  # 0-based
        row  = frota.get("row",0)
        nome = frota.get("nome","Frota")
        lado = frota.get("lado","atacante")  # atacante ou defensor
        tipo = frota.get("tipo","espacial")  # espacial ou terrestre
        cor  = frota.get("cor","CC1111")
        desc = frota.get("desc","")

        fx = int(OX+BCW*col+BCW/2)
        fy = int(OY+BCH*row+BCH/2)
        r,g,b = hex_rgb(cor)

        if lado=="atacante":
            # Triângulo apontando para o centro
            simbolo="▲"; borda=(255,120,120,230)
        else:
            # Triângulo invertido
            simbolo="▼"; borda=(150,120,255,230)

        if tipo=="terrestre":
            # Quadrado para unidade terrestre
            dw.rectangle([fx-13,fy-13,fx+13,fy+13],fill=(r,g,b,210),outline=borda,width=2)
            dw.text((fx,fy),"⬛" if lado=="defensor" else "⬜",fill=(255,255,255,220),font=fs,anchor="mm")
        else:
            dw.ellipse([fx-13,fy-13,fx+13,fy+13],fill=(r,g,b,210),outline=borda,width=2)
            dw.text((fx,fy),simbolo,fill=(255,255,255,230),font=fs,anchor="mm")

        # Nome da frota
        dw.text((fx,fy+15),nome[:12],fill=(r,g,b,220),font=fs,anchor="mt")
        if desc:
            dw.text((fx,fy+26),desc[:14],fill=(200,190,220,160),font=fs,anchor="mt")

        # Seta de intenção de movimento se tiver destino
        dest_col = frota.get("dest_col")
        dest_row = frota.get("dest_row")
        if dest_col is not None and dest_row is not None:
            dx2=int(OX+BCW*dest_col+BCW/2)
            dy2=int(OY+BCH*dest_row+BCH/2)
            ang=math.atan2(dy2-fy,dx2-fx)
            # Linha tracejada de intenção
            dist=math.sqrt((dx2-fx)**2+(dy2-fy)**2)
            steps=int(dist/12)
            for i in range(steps):
                if i%2==0:
                    px1=int(fx+i*(dx2-fx)/steps); py1=int(fy+i*(dy2-fy)/steps)
                    px2b=int(fx+(i+1)*(dx2-fx)/steps); py2b=int(fy+(i+1)*(dy2-fy)/steps)
                    dw.line([(px1,py1),(px2b,py2b)],fill=(r,g,b,140),width=2)
            t=12
            a1=(int(dx2-t*math.cos(ang-.4)),int(dy2-t*math.sin(ang-.4)))
            a2=(int(dx2-t*math.cos(ang+.4)),int(dy2-t*math.sin(ang+.4)))
            dw.polygon([(dx2,dy2),a1,a2],fill=(r,g,b,180))

    # ── Painel lateral ────────────────────────────────────────────
    px,py = BW-155, 50
    dw.rectangle([px-5,py-5,px+152,py+BH-100],fill=(5,2,15,218),outline=(90,30,30,200),width=1)
    
    # Título
    modo_txt = "INVASÃO TERRESTRE" if terrestre else "BATALHA ESPACIAL"
    dw.text((px+72,py+3),modo_txt,fill=(255,100,100,255),font=fs,anchor="mt")
    dw.line([(px,py+18),(px+150,py+18)],fill=(120,30,30,150),width=1)

    # Info da batalha
    dw.text((px+3,py+24),"Setor:",fill=(180,170,210,200),font=fs)
    dw.text((px+50,py+24),batalha.get("setor","?"),fill=(220,215,245,230),font=fs)
    dw.text((px+3,py+38),"Objetivo:",fill=(180,170,210,200),font=fs)
    dw.text((px+3,py+50),planeta[:18],fill=(255,225,120,220),font=fs)
    dw.line([(px,py+64),(px+150,py+64)],fill=(80,70,110,120),width=1)

    # Atacante
    at_nome = batalha.get("atacante","?")
    at_cor  = batalha.get("cor_atacante","CC1111")
    r2,g2,b2=hex_rgb(at_cor)
    dw.text((px+3,py+70),"⚔ ATACANTE",fill=(255,80,80,240),font=fs)
    dw.text((px+3,py+83),at_nome[:18],fill=(r2,g2,b2,220),font=fs)
    n_at=len([f for f in frotas.values() if f.get("lado")=="atacante"])
    dw.text((px+3,py+96),f"{n_at} unidade(s)",fill=(200,170,170,200),font=fs)
    dw.line([(px,py+110),(px+150,py+110)],fill=(80,70,110,120),width=1)

    # Defensor
    df_nome = batalha.get("defensor","?")
    df_cor  = batalha.get("cor_defensor","7711BB")
    r3,g3,b3=hex_rgb(df_cor)
    dw.text((px+3,py+116),"🛡 DEFENSOR",fill=(160,120,255,240),font=fs)
    dw.text((px+3,py+129),df_nome[:18],fill=(r3,g3,b3,220),font=fs)
    n_df=len([f for f in frotas.values() if f.get("lado")=="defensor"])
    dw.text((px+3,py+142),f"{n_df} unidade(s)",fill=(180,150,220,200),font=fs)
    dw.line([(px,py+156),(px+150,py+156)],fill=(80,70,110,120),width=1)

    # Legenda
    dw.text((px+3,py+162),"▲ Atacante",fill=(255,150,150,200),font=fs)
    dw.text((px+3,py+175),"▼ Defensor",fill=(180,150,255,200),font=fs)
    dw.text((px+3,py+188),"★ Objetivo",fill=(255,215,80,200),font=fs)
    dw.text((px+3,py+201),"-→ Movimento",fill=(180,180,200,200),font=fs)

    # Turno de batalha
    turno = batalha.get("turno",1)
    dw.line([(px,py+218),(px+150,py+218)],fill=(80,70,110,120),width=1)
    dw.text((px+72,py+224),f"TURNO {turno}",fill=(200,180,255,220),font=fn,anchor="mt")

    # ── Cabeçalho ────────────────────────────────────────────────
    dw.rectangle([0,0,BW-160,42],fill=(10,4,22,230))
    titulo_batalha = batalha.get("nome","Batalha")
    dw.text(((BW-160)//2,4),f"⚔  {titulo_batalha}  ⚔",fill=(255,80,80,255),font=ft,anchor="mt")
    dw.line([(0,42),(BW-160,42)],fill=(180,30,30,180),width=2)

    # Timestamp
    agora=datetime.now().strftime("%d/%m %H:%M")
    dw.text((5,BH-18),f"Atualizado: {agora}",fill=(120,115,150,160),font=fs)

    final = Image.alpha_composite(base,ov).convert("RGB")
    buf   = io.BytesIO()
    final.save(buf,format="PNG",optimize=True)
    buf.seek(0)
    return buf


# ==============================
# SETUP
# ==============================
def setup_batalha(bot, dados_ref, salvar_fn):
    cfg = carregar_batalhas()

    def get_id_canal(interaction):
        return str(interaction.channel_id)

    # ── /criar_batalha ────────────────────────────────────────────
    @bot.tree.command(name="criar_batalha", description="[ADM] Cria mapa de batalha no post atual do fórum")
    @app_commands.describe(
        nome     = "Nome da batalha (ex: Batalha de Nexus)",
        setor    = "Setor do mapa galáctico (ex: H5)",
        atacante = "Jogador atacante",
        defensor = "Jogador defensor",
        planeta  = "Planeta/objetivo em disputa",
        modo     = "Tipo de batalha",
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="🚀 Espacial",          value="espacial"),
        app_commands.Choice(name="⚔️ Invasão Terrestre", value="terrestre"),
    ])
    async def slash_criar_batalha(interaction, nome: str, setor: str, atacante: discord.Member, defensor: discord.Member, planeta: str, modo: str = "espacial"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        id_at = str(atacante.id)
        id_df = str(defensor.id)
        imp_at = dados_ref["imperios"].get(id_at, {})
        imp_df = dados_ref["imperios"].get(id_df, {})
        cor_at = imp_at.get("cor","CC1111")
        cor_df = imp_df.get("cor","7711BB")

        canal_id = get_id_canal(interaction)
        batalha_id = f"{canal_id}"

        cfg["batalhas"][batalha_id] = {
            "nome":          nome,
            "setor":         setor.upper(),
            "atacante":      imp_at.get("nome", atacante.display_name),
            "defensor":      imp_df.get("nome", defensor.display_name),
            "cor_atacante":  cor_at,
            "cor_defensor":  cor_df,
            "planeta":       planeta,
            "modo":          modo,
            "frotas":        {},
            "turno":         1,
            "msg_id":        None,
            "seed":          random.randint(1,9999),
            "criado_em":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        salvar_batalhas(cfg)

        await interaction.response.defer()
        buf   = gerar_mapa_batalha(cfg["batalhas"][batalha_id])
        modo_emoji = "⚔️" if modo=="terrestre" else "🚀"
        embed = discord.Embed(
            title=f"{modo_emoji}  {nome}",
            description=f"{SEP}\n*O destino de **{planeta}** será decidido aqui.*\n{SEP}",
            color=COR_TERRESTRE if modo=="terrestre" else COR_BATALHA
        )
        embed.add_field(name="📍 Setor",      value=setor.upper(),              inline=True)
        embed.add_field(name="🎯 Objetivo",   value=planeta,                    inline=True)
        embed.add_field(name="🔄 Modo",       value=modo.title(),               inline=True)
        embed.add_field(name="⚔️ Atacante",   value=f"{atacante.mention}\n**{imp_at.get('nome','?')}**", inline=True)
        embed.add_field(name="🛡️ Defensor",   value=f"{defensor.mention}\n**{imp_df.get('nome','?')}**", inline=True)
        embed.add_field(name="📋 Comandos",
            value="`/adicionar_frota` — Adicionar unidade\n`/mover_frota` — Mover unidade\n`/atualizar_mapa_batalha` — Atualizar imagem\n`/finalizar_batalha` — Encerrar",
            inline=False)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  Turno 1  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        if buf:
            f    = discord.File(buf, filename="batalha.png")
            embed.set_image(url="attachment://batalha.png")
            msg  = await interaction.followup.send(file=f, embed=embed)
        else:
            msg  = await interaction.followup.send(embed=embed)

        cfg["batalhas"][batalha_id]["msg_id"] = msg.id
        salvar_batalhas(cfg)

    # ── /adicionar_frota ──────────────────────────────────────────
    @bot.tree.command(name="adicionar_frota", description="[ADM] Adiciona uma frota/unidade ao mapa de batalha")
    @app_commands.describe(
        nome  = "Nome da frota (ex: Esquadrão Alpha)",
        lado  = "Atacante ou defensor",
        col   = "Coluna no grid (1-5 espacial / 1-6 terrestre)",
        row   = "Linha no grid (1-4 espacial / 1-5 terrestre)",
        tipo  = "Tipo de unidade",
        desc  = "Descrição curta (ex: 3 cruzadores)",
    )
    @app_commands.choices(
        lado=[
            app_commands.Choice(name="⚔️ Atacante", value="atacante"),
            app_commands.Choice(name="🛡️ Defensor", value="defensor"),
        ],
        tipo=[
            app_commands.Choice(name="🚀 Frota Espacial",    value="espacial"),
            app_commands.Choice(name="🛡️ Unidade Terrestre", value="terrestre"),
            app_commands.Choice(name="💣 Bombardeiro",        value="bombardeiro"),
            app_commands.Choice(name="🔭 Reconhecimento",    value="reconhecimento"),
        ]
    )
    async def slash_adicionar_frota(interaction, nome: str, lado: str, col: int, row: int, tipo: str = "espacial", desc: str = ""):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        canal_id = get_id_canal(interaction)
        if canal_id not in cfg["batalhas"]:
            return await interaction.response.send_message("❌ Nenhuma batalha ativa neste canal.", ephemeral=True)

        batalha = cfg["batalhas"][canal_id]
        modo    = batalha.get("modo","espacial")
        gc      = GRID_COLS_T if modo=="terrestre" else GRID_COLS
        gr      = GRID_ROWS_T if modo=="terrestre" else GRID_ROWS

        if not (1<=col<=gc) or not (1<=row<=gr):
            return await interaction.response.send_message(f"❌ Posição inválida. Grid: {gc} colunas × {gr} linhas.", ephemeral=True)

        cor = batalha.get("cor_atacante","CC1111") if lado=="atacante" else batalha.get("cor_defensor","7711BB")
        fid = f"f{len(batalha['frotas'])+1}"
        batalha["frotas"][fid] = {
            "nome": nome, "lado": lado, "col": col-1, "row": row-1,
            "tipo": tipo, "desc": desc, "cor": cor,
        }
        salvar_batalhas(cfg)

        embed = discord.Embed(title="✅  Frota Adicionada", color=COR_BATALHA)
        embed.add_field(name="🏷️ Nome",   value=nome,         inline=True)
        embed.add_field(name="⚔️ Lado",   value=lado.title(), inline=True)
        embed.add_field(name="📍 Posição",value=f"{(GRID_COLS_T if modo=='terrestre' else COL_LABELS)[col-1]}{row}", inline=True)
        if desc:
            embed.add_field(name="📋 Desc", value=desc, inline=True)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  Use /atualizar_mapa_batalha para ver no mapa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /mover_frota ──────────────────────────────────────────────
    @bot.tree.command(name="mover_frota", description="[ADM] Move uma frota para nova posição no grid")
    @app_commands.describe(
        frota_id = "ID da frota (f1, f2...)",
        col      = "Nova coluna",
        row      = "Nova linha",
        marcar_destino = "Apenas marca destino sem mover (intenção de movimento)",
    )
    async def slash_mover_frota(interaction, frota_id: str, col: int, row: int, marcar_destino: bool = False):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        canal_id = get_id_canal(interaction)
        if canal_id not in cfg["batalhas"]:
            return await interaction.response.send_message("❌ Nenhuma batalha ativa.", ephemeral=True)
        batalha = cfg["batalhas"][canal_id]
        if frota_id not in batalha["frotas"]:
            ids = ", ".join(batalha["frotas"].keys()) or "nenhuma"
            return await interaction.response.send_message(f"❌ Frota não encontrada. Frotas: {ids}", ephemeral=True)

        frota = batalha["frotas"][frota_id]
        if marcar_destino:
            frota["dest_col"] = col-1
            frota["dest_row"] = row-1
            acao = "Destino marcado"
        else:
            frota["col"] = col-1
            frota["row"] = row-1
            frota.pop("dest_col",None)
            frota.pop("dest_row",None)
            acao = "Frota movida"
        salvar_batalhas(cfg)

        modo = batalha.get("modo","espacial")
        cl   = COL_LABELS_T if modo=="terrestre" else COL_LABELS
        embed = discord.Embed(title=f"🔄  {acao}", color=COR_BATALHA)
        embed.add_field(name="🏷️ Frota",     value=frota["nome"], inline=True)
        embed.add_field(name="📍 Nova Pos.",  value=f"{cl[col-1]}{row}", inline=True)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  Use /atualizar_mapa_batalha")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /remover_frota ────────────────────────────────────────────
    @bot.tree.command(name="remover_frota", description="[ADM] Remove uma frota do mapa de batalha")
    @app_commands.describe(frota_id="ID da frota (f1, f2...)", motivo="Motivo (destruída, recuou...)")
    async def slash_remover_frota(interaction, frota_id: str, motivo: str = "Destruída em combate"):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        canal_id = get_id_canal(interaction)
        if canal_id not in cfg["batalhas"]:
            return await interaction.response.send_message("❌ Nenhuma batalha ativa.", ephemeral=True)
        batalha = cfg["batalhas"][canal_id]
        if frota_id not in batalha["frotas"]:
            return await interaction.response.send_message("❌ Frota não encontrada.", ephemeral=True)
        nome_frota = batalha["frotas"][frota_id]["nome"]
        del batalha["frotas"][frota_id]
        salvar_batalhas(cfg)
        embed = discord.Embed(title="💥  Frota Removida", color=COR_BATALHA)
        embed.add_field(name="🏷️ Frota",  value=nome_frota, inline=True)
        embed.add_field(name="📋 Motivo", value=motivo,     inline=True)
        embed.set_footer(text=RODAPE_ADM)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /atualizar_mapa_batalha ───────────────────────────────────
    @bot.tree.command(name="atualizar_mapa_batalha", description="[ADM] Atualiza a imagem do mapa de batalha no post")
    @app_commands.describe(avancar_turno="Avança o contador de turno")
    async def slash_atualizar_batalha(interaction, avancar_turno: bool = False):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        canal_id = get_id_canal(interaction)
        if canal_id not in cfg["batalhas"]:
            return await interaction.response.send_message("❌ Nenhuma batalha ativa neste canal.", ephemeral=True)

        batalha = cfg["batalhas"][canal_id]
        if avancar_turno:
            batalha["turno"] += 1
        salvar_batalhas(cfg)

        await interaction.response.defer()
        buf = gerar_mapa_batalha(batalha)
        if not buf:
            return await interaction.followup.send("❌ Erro ao gerar imagem.", ephemeral=True)

        modo_emoji = "⚔️" if batalha.get("modo")=="terrestre" else "🚀"
        embed = discord.Embed(
            title=f"{modo_emoji}  {batalha['nome']}  —  Turno {batalha['turno']}",
            description=f"{SEP}\n*O campo de batalha evolui...*",
            color=COR_TERRESTRE if batalha.get("modo")=="terrestre" else COR_BATALHA
        )
        embed.add_field(name="⚔️ Atacante",  value=batalha["atacante"], inline=True)
        embed.add_field(name="🛡️ Defensor",  value=batalha["defensor"], inline=True)
        embed.add_field(name="🎯 Objetivo",  value=batalha["planeta"],  inline=True)
        n_at=len([f for f in batalha["frotas"].values() if f.get("lado")=="atacante"])
        n_df=len([f for f in batalha["frotas"].values() if f.get("lado")=="defensor"])
        embed.add_field(name="📊 Forças", value=f"⚔️ {n_at} unidade(s)  ·  🛡️ {n_df} unidade(s)", inline=False)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  Turno {batalha['turno']}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        f = discord.File(io.BytesIO(buf.read()), filename="batalha.png")
        embed.set_image(url="attachment://batalha.png")

        # Tenta editar a mensagem original, senão posta nova
        msg_id = batalha.get("msg_id")
        if msg_id:
            try:
                msg_orig = await interaction.channel.fetch_message(int(msg_id))
                await msg_orig.delete()
            except:
                pass
        nova_msg = await interaction.followup.send(file=f, embed=embed)
        cfg["batalhas"][canal_id]["msg_id"] = nova_msg.id
        salvar_batalhas(cfg)

    # ── /finalizar_batalha ────────────────────────────────────────
    @bot.tree.command(name="finalizar_batalha", description="[ADM] Encerra a batalha e declara vencedor")
    @app_commands.describe(
        vencedor = "Quem venceu",
        resultado= "Descrição do resultado",
    )
    @app_commands.choices(vencedor=[
        app_commands.Choice(name="⚔️ Atacante venceu", value="atacante"),
        app_commands.Choice(name="🛡️ Defensor venceu", value="defensor"),
        app_commands.Choice(name="🤝 Empate / Retirada", value="empate"),
    ])
    async def slash_finalizar_batalha(interaction, vencedor: str, resultado: str = ""):
        if not tem_permissao_adm(interaction):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)
        canal_id = get_id_canal(interaction)
        if canal_id not in cfg["batalhas"]:
            return await interaction.response.send_message("❌ Nenhuma batalha ativa.", ephemeral=True)

        batalha = cfg["batalhas"][canal_id]
        n_at    = batalha["atacante"]
        n_df    = batalha["defensor"]

        if vencedor=="atacante":    venc_txt=f"⚔️ {n_at}"; cor=0x7F1D1D
        elif vencedor=="defensor":  venc_txt=f"🛡️ {n_df}"; cor=0x1E3A5F
        else:                       venc_txt="🤝 Empate";  cor=0x3B3B3B

        embed = discord.Embed(
            title=f"🏁  BATALHA ENCERRADA  —  {batalha['nome']}",
            description=f"{SEP}\n*Os canhões silenciam. O destino de **{batalha['planeta']}** foi decidido.*\n{SEP}",
            color=cor
        )
        embed.add_field(name="🏆 Vencedor",   value=venc_txt,                   inline=True)
        embed.add_field(name="🎯 Objetivo",   value=batalha["planeta"],          inline=True)
        embed.add_field(name="🔄 Turnos",     value=str(batalha["turno"]),       inline=True)
        embed.add_field(name="⚔️ Atacante",   value=n_at,                        inline=True)
        embed.add_field(name="🛡️ Defensor",   value=n_df,                        inline=True)
        if resultado:
            embed.add_field(name="📜 Resultado", value=resultado, inline=False)
        embed.set_footer(text=f"{RODAPE_ADM}  ·  {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        del cfg["batalhas"][canal_id]
        salvar_batalhas(cfg)
        await interaction.response.send_message(content="@everyone", embed=embed)

    # ── !status_batalha ───────────────────────────────────────────
    @bot.command(name="status_batalha")
    async def status_batalha(ctx):
        canal_id = str(ctx.channel.id)
        if canal_id not in cfg["batalhas"]:
            return await ctx.send("❌ Nenhuma batalha ativa neste canal.")
        batalha = cfg["batalhas"][canal_id]
        frotas  = batalha.get("frotas",{})
        n_at    = len([f for f in frotas.values() if f.get("lado")=="atacante"])
        n_df    = len([f for f in frotas.values() if f.get("lado")=="defensor"])
        embed   = discord.Embed(
            title=f"⚔️  {batalha['nome']}",
            description=f"{SEP}\nTurno **{batalha['turno']}**  ·  Setor **{batalha['setor']}**\n{SEP}",
            color=COR_BATALHA
        )
        embed.add_field(name="🎯 Objetivo",  value=batalha["planeta"],  inline=True)
        embed.add_field(name="🔄 Modo",      value=batalha["modo"].title(), inline=True)
        embed.add_field(name="\u200b",       value="\u200b",            inline=True)
        embed.add_field(name=f"⚔️ {batalha['atacante']}", value=f"{n_at} unidade(s)", inline=True)
        embed.add_field(name=f"🛡️ {batalha['defensor']}", value=f"{n_df} unidade(s)", inline=True)
        if frotas:
            linhas=[]
            for fid,f in frotas.items():
                modo=batalha.get("modo","espacial")
                cl=COL_LABELS_T if modo=="terrestre" else COL_LABELS
                pos=f"{cl[f['col']]}{f['row']+1}"
                linhas.append(f"`{fid}` {f['nome']} [{f['lado'][:3]}] @ {pos}")
            embed.add_field(name="🗺️ Unidades em Campo", value="\n".join(linhas), inline=False)
        embed.set_footer(text=f"Sistema Galáctico  ·  Use /atualizar_mapa_batalha para atualizar")
        await ctx.send(embed=embed)

    return cfg