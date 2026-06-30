N=210; C=3; GRID=N*C
ML,TM,RM,BM = 56,56,20,58
W,H = ML+GRID+RM, TM+GRID+BM

def trip(d): return (d%5, d%6, d%7)
d0=lambda d:d%5; d1=lambda d:(d//5)%6; d2=lambda d:d//30

def make_svg(order, key, title, subtitle, k0name, fname):
    # black runs for x>y
    runs=[]
    for i in range(N):
        j=0
        while j<N:
            if order[i]>order[j]:
                k=j
                while k<N and order[i]>order[k]: k+=1
                runs.append((ML+j*C, TM+i*C, (k-j)*C)); j=k
            else: j+=1
    # boundaries from key changes
    majors=[0]; minors=[]
    for idx in range(1,N):
        a,b=key(order[idx-1]),key(order[idx])
        if a[0]!=b[0]: majors.append(idx)
        elif a[1]!=b[1]: minors.append(idx)
    blocks=majors+[N]
    s=[]
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif">')
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<rect x="{ML}" y="{TM}" width="{GRID}" height="{GRID}" fill="white" stroke="#000" stroke-width="1"/>')
    # black cells
    s.append('<g fill="#111">')
    for x,y,w in runs: s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{C}"/>')
    s.append('</g>')
    # minor gridlines
    s.append('<g stroke="#9bb7e0" stroke-width="0.6">')
    for idx in minors:
        p=idx*C
        s.append(f'<line x1="{ML+p}" y1="{TM}" x2="{ML+p}" y2="{TM+GRID}"/>')
        s.append(f'<line x1="{ML}" y1="{TM+p}" x2="{ML+GRID}" y2="{TM+p}"/>')
    s.append('</g>')
    # major gridlines + block labels
    s.append('<g stroke="#d23" stroke-width="1.1">')
    for idx in majors[1:]:
        p=idx*C
        s.append(f'<line x1="{ML+p}" y1="{TM}" x2="{ML+p}" y2="{TM+GRID}"/>')
        s.append(f'<line x1="{ML}" y1="{TM+p}" x2="{ML+GRID}" y2="{TM+p}"/>')
    s.append('</g>')
    s.append('<g fill="#d23" font-size="9" text-anchor="middle">')
    for bi in range(len(blocks)-1):
        a,b=blocks[bi],blocks[bi+1]
        v=key(order[a])[0]; mid=ML+(a+b)/2*C
        s.append(f'<text x="{mid}" y="{TM-3}">{v}</text>')
        s.append(f'<text x="{ML-8}" y="{TM+(a+b)/2*C+3}" text-anchor="end">{v}</text>')
    s.append('</g>')
    # titles / axis labels
    s.append(f'<text x="{ML}" y="22" font-size="15" font-weight="bold" fill="#111">{title}</text>')
    s.append(f'<text x="{ML}" y="40" font-size="11" fill="#555">{subtitle}</text>')
    s.append(f'<text x="{ML+GRID/2}" y="{H-8}" font-size="11" text-anchor="middle" fill="#333">y  (columns)   - red numbers: {k0name} block</text>')
    s.append(f'<text x="14" y="{TM+GRID/2}" font-size="11" text-anchor="middle" fill="#333" transform="rotate(-90 14 {TM+GRID/2})">x  (rows)</text>')
    s.append(f'<text x="{W-RM}" y="40" font-size="10" text-anchor="end" fill="#555">black: x &gt; y</text>')
    s.append('</svg>')
    open(fname,"w").write("\n".join(s))
    return len("\n".join(s)), len(majors), len(minors)

# validate on magnitude first
order=sorted(range(N),key=lambda d:(d2(d),d1(d),d0(d)))
info=make_svg(order, lambda d:(d2(d),d1(d),d0(d)),
        "base-210:  x > y   (magnitude order)",
        "rows/cols sorted by (d2, d1, d0) = true magnitude",
        "d2", "figures/panel_magnitude.svg")
print("magnitude svg:", info, "bytes/majors/minors")

D="figures/"
panels=[
 ("sig1_residue", lambda d:(d%5,d%6,d%7), "base-210:  x > y   (residue order - the plaid)",
    "rows/cols sorted lexically by (r5, r6, r7); major lines: r5 changes, minor: r6", "r5"),
 ("sig2_d2", lambda d:(d2(d),d%5,d%6,d%7), "base-210:  x > y   (sorted by d2, then residue)",
    "leading digit d2 (30s) sorts the coarse blocks; scramble remains inside each 30-block", "d2"),
 ("sig3_d2d1", lambda d:(d2(d),d1(d),d%5,d%6,d%7), "base-210:  x > y   (sorted by d2, d1, then residue)",
    "adding d1 (5s) shrinks the scramble to 5-blocks; nearly clean", "d2"),
 ("comp1_residue", lambda d:(d%7,d%6,d%5), "base-210:  x > y   (residue order, r7 leading)",
    "computation-order start: (r7, r6, r5) = (r7, r6, d0)", "r7"),
 ("comp2_d1", lambda d:(d%7,d1(d),d0(d)), "base-210:  x > y   (r7, d1, d0)",
    "r6 replaced by d1 (must be computed first); coarse order still scrambled by r7", "r7"),
]
for name,key,title,sub,k0 in panels:
    order=sorted(range(N),key=key)
    info=make_svg(order,key,title,sub,k0,D+f"panel_{name}.svg")
    print(f"{name}: {info[0]} bytes, {info[1]} majors, {info[2]} minors")
