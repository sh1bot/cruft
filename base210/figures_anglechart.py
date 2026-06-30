def esc(s): return ''.join({'&':'&amp;','<':'&lt;','>':'&gt;'}.get(c,c if ord(c)<128 else f'&#{ord(c)};') for c in str(s))
def txt(x,y,s,size=11,col="#111",anchor="middle",weight="normal"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{col}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>'
BLUE="#27e"; ORANGE="#e80"; GREEN="#1a7"
W,H=760,430
L,R,T,B=58,150,52,52
pw,ph=W-L-R, H-T-B
def X(n): return L + n/30*pw
def Y(deg): return T + (1-deg/360)*ph
N=list(range(31))
fives=[72*(n%5) for n in N]; sixes=[60*(n%6) for n in N]; gap=[12*(n%30) for n in N]
def series(vals,color,name,yoff):
    out=[]
    # polyline, broken where it wraps (value drops)
    seg=[]
    def flush():
        if len(seg)>=2:
            pts=" ".join(f"{X(n):.1f},{Y(v):.1f}" for n,v in seg)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6"/>')
    for n,v in zip(N,vals):
        if seg and v < seg[-1][1]:
            flush(); seg=[]
        seg.append((n,v))
    flush()
    for n,v in zip(N,vals):
        out.append(f'<circle cx="{X(n):.1f}" cy="{Y(v):.1f}" r="2.6" fill="{color}"/>')
    out.append(txt(W-R+12,yoff,name,11,color,"start"))
    return "\n".join(out)
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">',
   f'<rect width="{W}" height="{H}" fill="white"/>',
   txt(W/2,26,"Hand angles vs value n (0–30): two sawtooths, and their clockwise difference",13,"#111","middle","bold")]
# axes & gridlines
for deg in range(0,361,60):
    s.append(f'<line x1="{L}" y1="{Y(deg):.1f}" x2="{L+pw}" y2="{Y(deg):.1f}" stroke="#eee"/>')
    s.append(txt(L-8,Y(deg)+3,f"{deg}°",10,"#555","end"))
for n in range(0,31,5):
    s.append(f'<line x1="{X(n):.1f}" y1="{T}" x2="{X(n):.1f}" y2="{T+ph}" stroke="#f3f3f3"/>')
    s.append(txt(X(n),T+ph+16,n,10,"#555"))
s.append(f'<rect x="{L}" y="{T}" width="{pw}" height="{ph}" fill="none" stroke="#ccc"/>')
s.append(txt(W/2,H-12,"value n",11,"#333"))
s.append(txt(16,T+ph/2,"angle",11,"#333"))  # left label (kept simple)
# series
s.append(series(sixes,ORANGE,"6-hand = 60·(n mod 6)",T+ph/2-16))
s.append(series(fives,BLUE,"5-hand = 72·(n mod 5)",T+ph/2))
s.append(series(gap,GREEN,"gap (6→5) = 12·(n mod 30)",T+ph/2+16))
s.append('</svg>')
out="figures/base210_anglechart.svg"
open(out,"w").write("\n".join(s))
import xml.dom.minidom as M; M.parseString("\n".join(s)); print("XML OK")
print("gap is monotone 0,12,...,348 then wraps:", gap[:4], "...", gap[28:])
