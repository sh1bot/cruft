import math
def esc(s): return ''.join({'&':'&amp;','<':'&lt;','>':'&gt;'}.get(c,c if ord(c)<128 else f'&#{ord(c)};') for c in str(s))
def pt(cx,cy,r,deg):
    a=math.radians(deg); return (cx+r*math.sin(a), cy-r*math.cos(a))
def arc(cx,cy,r,start,span,color,w):
    end=start+span; large=1 if (span%360)>180 else 0
    x0,y0=pt(cx,cy,r,start); x1,y1=pt(cx,cy,r,end)
    return f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{color}" stroke-width="{w}"/>'
def hand(cx,cy,L,deg,color,w=3):
    x,y=pt(cx,cy,L,deg); return f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>'
def north(cx,cy,r,deg,color,label):
    # small triangle just outside the circle pointing inward, + label
    tip=pt(cx,cy,r+2,deg); a=pt(cx,cy,r+12,deg-3.2); b=pt(cx,cy,r+12,deg+3.2)
    lp=pt(cx,cy,r+22,deg)
    return (f'<path d="M {tip[0]:.1f} {tip[1]:.1f} L {a[0]:.1f} {a[1]:.1f} L {b[0]:.1f} {b[1]:.1f} Z" fill="{color}"/>'
            f'<text x="{lp[0]:.1f}" y="{lp[1]+3:.1f}" font-size="9" fill="{color}" text-anchor="middle">{esc(label)}</text>')
def txt(x,y,s,size=11,col="#111",anchor="middle",weight="normal"):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{col}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>'
GREEN="#1a7"; PUR="#94c"; GREY="#999"; DARK="#333"
Rc=72; RA=48; RB=56; L6=64; L5=34
examples=[(7,11),(9,8),(13,20),(22,25)]
W=900; H=430; cy=185
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">',
   f'<rect width="{W}" height="{H}" fill="white"/>',
   txt(W/2,24,"Adding in the (5,6) subsystem: A stays put; B is rotated so its 6-hand meets A's 5-hand, laying the arcs end-to-end",13,"#111","middle","bold"),
   txt(W/2,42,"green = A's value (6→5, inner);  purple = B's value (6→5, outer).  Arcs overlapping past a full turn = carry.",10,"#555")]
for i,(a,b) in enumerate(examples):
    cx=130+i*215
    a5=72*(a%5); a6=60*(a%6); b5=72*(b%5); b6=60*(b%6)
    phi=(a5-b6)%360; b6r=(b6+phi)%360; b5r=(b5+phi)%360
    ta=(a5-a6)%360; tb=(b5-b6)%360; total=ta+tb; carry=total>=360; digit=(a+b)%30
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{Rc}" fill="none" stroke="#ddd" stroke-width="1.3"/>')
    s.append(north(cx,cy,Rc,0,DARK,"A 0"))            # A's 12 o'clock (real top)
    s.append(north(cx,cy,Rc,phi,PUR,"B 0"))           # B's rotated 12 o'clock
    # layer order: arcs, then long (6-)hands, then short (5-)hands -- so nothing is obscured
    s.append(arc(cx,cy,RA,a6,ta,GREEN,5))             # A value arc (inner)
    s.append(arc(cx,cy,RB,b6r,tb,PUR,5))              # B value arc (outer)
    s.append(hand(cx,cy,L6,a6,GREEN,3))               # A 6-hand (long)
    s.append(hand(cx,cy,L6,b6r,PUR,3))                # B 6-hand (long) -- sits on A's 5-hand
    s.append(hand(cx,cy,L5,a5,GREEN,2.5))             # A 5-hand (short)
    s.append(hand(cx,cy,L5,b5r,PUR,2.5))              # B 5-hand (short) -- the end
    s.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="{DARK}"/>')
    s.append(txt(cx,cy+Rc+26,f"{a} + {b} = {a+b}",12,"#111","middle","bold"))
    s.append(txt(cx,cy+Rc+43,f"{ta}° + {tb}° = {total}°",10,PUR))
    s.append(txt(cx,cy+Rc+59,("carry, digit "+str(digit)) if carry else "no carry",10,(PUR if carry else GREEN)))
s.append(txt(W/2,H-10,"Only the total arc (gap from A's 6-hand to B's 5-hand) is the result; the hand positions are not the sum's dial.",10,"#555"))
s.append('</svg>')
out="figures/base210_sums.svg"
open(out,"w").write("\n".join(s))
import xml.dom.minidom as M; M.parseString("\n".join(s)); print("XML OK")
for a,b in examples:
    a5,a6=72*(a%5),60*(a%6); phi=(a5-60*(b%6))%360
    print(f"{a}+{b}: phi={phi}, total={12*(a%30)+12*(b%30)}, carry={(a%30+b%30)>=30}")
