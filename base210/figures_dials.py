import math
def pt(cx,cy,r,deg):
    a=math.radians(deg); return (cx+r*math.sin(a), cy-r*math.cos(a))
def arc(cx,cy,r,a0,a1,color,w):
    span=(a1-a0)%360
    large=1 if span>180 else 0
    x0,y0=pt(cx,cy,r,a0); x1,y1=pt(cx,cy,r,a1)
    return f'<path d="M {x0:.1f} {y0:.1f} A {r} {r} 0 {large} 1 {x1:.1f} {y1:.1f}" fill="none" stroke="{color}" stroke-width="{w}"/>'
def dial(cx,cy,r,n,ptr,label):
    s=[f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="white" stroke="#333" stroke-width="1.5"/>']
    for k in range(n):
        x0,y0=pt(cx,cy,r-1,k*360/n); x1,y1=pt(cx,cy,r-7,k*360/n)
        s.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#999" stroke-width="1"/>')
        lx,ly=pt(cx,cy,r-16,k*360/n)
        s.append(f'<text x="{lx:.1f}" y="{ly+3:.1f}" font-size="9" text-anchor="middle" fill="#777">{k}</text>')
    px,py=pt(cx,cy,r-8,ptr*360/n)
    s.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#d23" stroke-width="2.5"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#333"/>')
    s.append(f'<text x="{cx}" y="{cy+r+18}" font-size="12" text-anchor="middle" fill="#111">{label}</text>')
    return "\n".join(s)

W,H=860,640
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">']
s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
s.append('<text x="30" y="28" font-size="16" font-weight="bold">base-210 (5,6) subsystem: magnitude is the angle between the dials</text>')

# --- top: two dials for value 13, gap = 156 deg = 13*12 ---
v=13
s.append('<text x="30" y="58" font-size="12" fill="#555">value 13:  5-dial at r5=3 (3x72=216deg),  6-dial at r6=1 (1x60=60deg)</text>')
s.append(dial(150,150,70,5,v%5,"5-dial (r5=3)"))
s.append(dial(370,150,70,6,v%6,"6-dial (r6=1)"))
# gap illustration on a third "drift" circle
cx,cy,r=650,150,70
s.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="white" stroke="#333" stroke-width="1.5"/>')
for m in range(30):
    x0,y0=pt(cx,cy,r,m*12); x1,y1=pt(cx,cy,r-(8 if m%5==0 else 4),m*12)
    s.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#bbb" stroke-width="1"/>')
s.append(arc(cx,cy,r-14,0,156,"#1a7",6))
px,py=pt(cx,cy,r-8,156)
s.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="#1a7" stroke-width="2.5"/>')
s.append(f'<text x="{cx}" y="{cy+r+18}" font-size="12" text-anchor="middle">gap = 156deg = 13x12deg</text>')
s.append(f'<text x="{cx}" y="{cy+r+34}" font-size="11" text-anchor="middle" fill="#1a7">(30 ticks, 12deg each = the magnitude)</text>')

# --- bottom: carry = two gaps summing past a full turn ---
s.append('<text x="30" y="350" font-size="13" font-weight="bold">carry  =  the two gaps complete a full turn (360deg)</text>')
def turn(cx,cy,th_a,th_b,va,vb):
    out=[f'<circle cx="{cx}" cy="{cy}" r="80" fill="white" stroke="#333" stroke-width="1.5"/>']
    for m in range(30):
        x0,y0=pt(cx,cy,80,m*12); x1,y1=pt(cx,cy,80-(8 if m%5==0 else 4),m*12)
        out.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#ccc" stroke-width="1"/>')
    out.append(arc(cx,cy,66,0,th_a,"#27e",7))
    out.append(arc(cx,cy,54,th_a,(th_a+th_b)%360,"#d23",7))
    tot=th_a+th_b
    carry = tot>=360
    out.append(f'<text x="{cx}" y="{cy+108}" font-size="12" text-anchor="middle">{va}+{vb}: {th_a}+{th_b}={tot}deg</text>')
    msg = f"&#8805;360&#176; &#8594; CARRY, out {(tot-360)//12}" if carry else "&lt;360&#176; &#8594; no carry"
    out.append(f'<text x="{cx}" y="{cy+124}" font-size="12" text-anchor="middle" fill="{"#d23" if carry else "#1a7"}">{msg}</text>')
    return "\n".join(out)
s.append(turn(220,470,120,96,10,8))      # 10+8=18 <30, no carry
s.append(turn(620,470,156,240,13,20))    # 13+20=33 >=30, carry, out 3
s.append('</svg>')
open("figures/base210_dials.svg","w").write("\n".join(s))
print("wrote base210_dials.svg")
