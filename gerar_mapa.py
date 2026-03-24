from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np
import math, random

W, H   = 3400, 2400
CX, CY = W // 2, H // 2
RNG    = random.Random(42)
NP     = np.random.default_rng(42)

GRADE_COLS = 17
GRADE_ROWS = 18
CELL_W     = W / GRADE_COLS
CELL_H     = H / GRADE_ROWS
COLUNAS    = [chr(ord('A') + i) for i in range(GRADE_COLS)]

# ── 1. Fundo base ────────────────────────────────────────────────────
base = Image.new("RGB", (W, H), (2, 3, 12))

# ── 2. Estrelas de fundo ─────────────────────────────────────────────
arr = np.array(base, dtype=np.float32)
for _ in range(6000):
    x = RNG.randint(0, W-1); y = RNG.randint(0, H-1)
    b = RNG.randint(35, 180)
    t = RNG.randint(0, 2)
    if t == 0:   arr[y,x] = [int(b*.7), int(b*.85), b]
    elif t == 1: arr[y,x] = [b, int(b*.9), int(b*.6)]
    else:        arr[y,x] = [b, b, b]
# Estrelas médias 2x2
for _ in range(500):
    x = RNG.randint(1, W-2); y = RNG.randint(1, H-2)
    b = RNG.randint(120, 220)
    c = RNG.choice([[int(b*.7),int(b*.85),b],[b,int(b*.9),int(b*.6)],[b,b,b]])
    arr[y:y+2, x:x+2] = c
base = Image.fromarray(arr.astype(np.uint8))

# ── 3. Galáxia — construída em camadas com blur ──────────────────────

# Camada A: disco suave
disc = Image.new("RGBA", (W, H), (0,0,0,0))
dd   = ImageDraw.Draw(disc)
for r in range(1150, 0, -8):
    t   = r / 1150
    rc  = int(180 * math.exp(-t*1.2) + 10)
    gc  = int(130 * math.exp(-t*1.5) + 5)
    bc  = int( 40 * math.exp(-t*2.0) + int(30*t))
    ac  = int( 80 * math.exp(-t*2.8))
    dd.ellipse([CX-r, CY-int(r*.68), CX+r, CY+int(r*.68)],
               fill=(rc, gc, bc, ac))
disc = disc.filter(ImageFilter.GaussianBlur(radius=18))

# Camada B: braços espirais — linhas contínuas com blur
arms = Image.new("RGBA", (W, H), (0,0,0,0))
ad   = ImageDraw.Draw(arms)

def spiral_pts(offset, n=4000, r_max=1100, tightness=3.7, flat=0.70):
    pts = []
    for i in range(n):
        frac  = i / n
        theta = offset + frac * math.pi * tightness
        r     = 30 + frac * r_max
        px    = CX + r * math.cos(theta)
        py    = CY + r * math.sin(theta) * flat
        pts.append((frac, px, py, r))
    return pts

BRACOS_DEF = [
    (0.0,        (130, 170, 255), 200, 3),
    (math.pi,    (125, 165, 250), 195, 3),
    (math.pi*.5, ( 90, 135, 220), 120, 2),
    (math.pi*1.5,( 90, 135, 220), 115, 2),
]

for (offset, cor, alph_max, thick) in BRACOS_DEF:
    pts = spiral_pts(offset)
    spread_base = 22
    for (frac, px, py, r) in pts:
        # spread cresce com r (braço alarga para fora)
        spread = spread_base + r * 0.05
        fade   = math.exp(-frac * 1.3) * (1 - math.exp(-frac * 12))
        for _ in range(4):
            perp   = math.atan2(py - CY, px - CX) + math.pi/2
            noise  = RNG.gauss(0, spread * 0.6)
            ex     = px + noise * math.cos(perp)
            ey     = py + noise * math.sin(perp)
            warmth = max(0, 1 - frac * 1.8)
            rc = min(255, int(cor[0]*fade + 200*warmth))
            gc = min(255, int(cor[1]*fade + 150*warmth))
            bc = min(255, int(cor[2]*fade +  60*warmth))
            ac = int(alph_max * fade * RNG.uniform(0.4, 1.0))
            ac = max(0, min(255, ac))
            sz = thick
            ad.ellipse([ex-sz, ey-sz, ex+sz, ey+sz], fill=(rc, gc, bc, ac))

# Blur forte nos braços para deixar suave/nebuloso
arms = arms.filter(ImageFilter.GaussianBlur(radius=4))

# Camada C: núcleo brilhante
core = Image.new("RGBA", (W, H), (0,0,0,0))
cd   = ImageDraw.Draw(core)
for r in range(300, 0, -2):
    t   = 1 - r/300
    rc  = int(255 * t**.28)
    gc  = int(235 * t**.40)
    bc  = int(160 * t**.75)
    ac  = int(240 * t**.18)
    cd.ellipse([CX-r, CY-int(r*.72), CX+r, CY+int(r*.72)],
               fill=(rc, gc, bc, ac))
# Ponto central
for r in range(55, 0, -1):
    t  = 1 - r/55
    ac = int(220 * t)
    cd.ellipse([CX-r, CY-r, CX+r, CY+r], fill=(255,248,210,ac))
core = core.filter(ImageFilter.GaussianBlur(radius=3))

# Estrelas dentro da galáxia
gstars = Image.new("RGBA", (W, H), (0,0,0,0))
gsd    = ImageDraw.Draw(gstars)
for _ in range(1800):
    angle = RNG.uniform(0, math.pi*2)
    r     = abs(RNG.gauss(0, 420))
    px    = CX + r * math.cos(angle)
    py    = CY + r * math.sin(angle) * 0.70
    if not (0 <= int(px) < W and 0 <= int(py) < H): continue
    b2 = RNG.randint(160, 255)
    col= RNG.choice([(b2,b2,b2),(int(b2*.7),int(b2*.85),b2),(b2,int(b2*.9),int(b2*.6))])
    sz = RNG.choice([1,1,1,1,2,2,3])
    gsd.ellipse([px-sz,py-sz,px+sz,py+sz], fill=(*col, RNG.randint(170,255)))

# Compõe tudo
result = base.convert("RGBA")
result = Image.alpha_composite(result, disc)
result = Image.alpha_composite(result, arms)
result = Image.alpha_composite(result, core)
result = Image.alpha_composite(result, gstars)
result = result.convert("RGB")

# ── 4. Nebulosa azul sutil nas bordas ────────────────────────────────
neb = Image.new("RGBA", (W, H), (0,0,0,0))
nd  = ImageDraw.Draw(neb)
for (nx,ny,nr,nc) in [
    (int(W*.09), int(H*.22), 380, (6,18,70)),
    (int(W*.14), int(H*.63), 300, (5,14,58)),
    (int(W*.87), int(H*.38), 320, (4,16,62)),
    (int(W*.74), int(H*.80), 340, (6,20,60)),
    (int(W*.42), int(H*.13), 270, (5,15,55)),
    (int(W*.60), int(H*.88), 250, (4,13,50)),
]:
    for dr in range(nr, 0, -18):
        t  = 1 - dr/nr
        ac = int(50 * math.exp(-t*4))
        nd.ellipse([nx-dr,ny-dr,nx+dr,ny+dr], fill=(nc[0],nc[1],nc[2],ac))
neb = neb.filter(ImageFilter.GaussianBlur(radius=70))
result = Image.alpha_composite(result.convert("RGBA"), neb).convert("RGB")

# ── 5. Estrelas destaque com difração ────────────────────────────────
hl  = Image.new("RGBA", (W, H), (0,0,0,0))
hd2 = ImageDraw.Draw(hl)
for (sx,sy,sc,ss) in [
    (int(W*.10),int(H*.13),(180,205,255),6),
    (int(W*.23),int(H*.11),(255,215,120),5),
    (int(W*.79),int(H*.10),(255,165, 80),6),
    (int(W*.06),int(H*.61),(255,195, 90),5),
    (int(W*.89),int(H*.59),(255,185, 80),6),
    (int(W*.92),int(H*.62),(200,225,255),4),
    (int(W*.30),int(H*.73),(255,205,100),4),
    (int(W*.61),int(H*.83),(180,215,255),4),
    (int(W*.14),int(H*.34),(165,205,255),4),
    (int(W*.86),int(H*.29),(255,205,125),5),
    (int(W*.50),int(H*.05),(200,220,255),3),
    (int(W*.72),int(H*.92),(255,200,110),3),
]:
    for r2 in range(ss*5, 0, -1):
        a2 = int(65 * (1-r2/(ss*5))**2)
        hd2.ellipse([sx-r2,sy-r2,sx+r2,sy+r2], fill=(*sc,a2))
    hd2.ellipse([sx-ss,sy-ss,sx+ss,sy+ss], fill=(*sc,255))
    for ln in [ss*9,ss*6,ss*3]:
        a3 = max(15, 150 - int((ln-ss*3)*12))
        hd2.line([(sx-ln,sy),(sx+ln,sy)], fill=(*sc,a3), width=1)
        hd2.line([(sx,sy-ln),(sx,sy+ln)], fill=(*sc,a3), width=1)
result = Image.alpha_composite(result.convert("RGBA"), hl).convert("RGB")

# ── 6. Grade + rótulos ───────────────────────────────────────────────
ov = Image.new("RGBA", (W, H), (0,0,0,0))
od = ImageDraw.Draw(ov)
CG = (220, 200, 120, 38)
for ci in range(GRADE_COLS+1):
    od.line([(int(CELL_W*ci),0),(int(CELL_W*ci),H)], fill=CG, width=1)
for ri in range(GRADE_ROWS+1):
    od.line([(0,int(CELL_H*ri)),(W,int(CELL_H*ri))], fill=CG, width=1)
try:
    fnt = ImageFont.truetype("arial.ttf", 44)
except:
    fnt = ImageFont.load_default()
CL = (232, 218, 172, 215)
for ci, letra in enumerate(COLUNAS):
    gx = int(CELL_W*ci + CELL_W/2)
    od.text((gx, 16), letra+".", fill=CL, font=fnt, anchor="mt")
for ri in range(GRADE_ROWS):
    gy = int(CELL_H*ri + CELL_H/2)
    od.text((20, gy), str(ri+1), fill=CL, font=fnt, anchor="lm")
result = Image.alpha_composite(result.convert("RGBA"), ov).convert("RGB")

# ── 7. Salva ─────────────────────────────────────────────────────────
import os
output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapa_fundo.png")
result.save(output, format="PNG", optimize=True)
print(f"✅ mapa_fundo.png salvo em: {output}")