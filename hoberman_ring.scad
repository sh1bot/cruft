// ============================================================================
//  Hoberman ring - 6 segment angulated-scissor expanding ring
//  A TRUE scissor: every load path runs pivot -> pivot, no floppy corners.
//  Units: millimetres.  OpenSCAD 2021.01+
// ----------------------------------------------------------------------------
//  A single flat loop of angulated scissor struts is governed by ONE freedom
//  `phi`. For n segments (p = 180/n) the three pivots of a strut sit at
//        outer node  Ro = L*(cot(p)*cos(phi) + sin(phi))
//        centre node Rm = L*      cos(phi)/sin(p)
//        inner node  Ri = L*(cot(p)*cos(phi) - sin(phi))
//  and every strut is a rigid isosceles link, arm length L, kink 180-360/n.
//
//  WHY SIX, AND WHAT MOVES
//  Ro = 2L*cos(phi-p) peaks at phi=p; Ri = 2L*cos(phi+p) falls with phi.
//  So over a single loop the inner and outer circles cannot grow by the SAME
//  proportion (they only would if n=2). What you CAN do, by running the strut
//  on the phi > p side and deploying toward phi = p, is make BOTH circles grow
//  at once - the ring opens from a nearly-closed disc into an open ring, and
//  the outer pivots really travel outward carrying load. Fewer segments give a
//  bigger outer stroke: the outer circle's full range is sec(p) = sec(180/n),
//  which is 15.5% at n=6 (vs only 6.4% at n=9) - enough for a real 36 -> 39.
//  The inner circle grows a lot MORE than the outer (that is unavoidable), and
//  the price of a real outer stroke is that the collapsed hole is small.
// ============================================================================

/* [What to show] */
show      = "assembly";   // ["assembly","print","pin"]
deploy    = 0.0;          // 0 = collapsed, 1 = fully expanded   [0:0.01:1]

/* [Ring] */
n         = 6;            // number of segments (scissor units)

/* [Kinematics / deployment] */
// Tuned so the outer PIVOT circle carries from ~33 -> ~36 (material ~36 -> ~39)
// while the inner circle opens up.  Read the echoed radii for exact values.
L            = 17.54;     // angulated arm length (pivot to pivot)    [mm]
phi_collapsed = 54.2;     // deployment angle, collapsed state        [deg]
phi_expanded  = 34;       // deployment angle, expanded state         [deg]

/* [Strut body (the printed arc)] */
beam_w    = 6.5;         // width of the load-bearing arc beam        [mm]
boss_d    = 8.0;         // diameter of the round pad at each pivot   [mm]
bow       = 0.16;        // arm curvature: sagitta as a fraction of the
                         //   arm chord (0 = straight bars, ~0.15 = gentle arc)
seg       = 24;          // arc smoothness (beads per arm)

/* [Pivots] */
hole_d    = 3.2;         // pivot hole diameter (3.2 = M3 clearance)  [mm]

/* [Build / print] */
th        = 3.0;         // thickness of one strut (one scissor layer) [mm]
layer_gap = 0.6;         // z clearance between the two layers          [mm]
pin_len   = 0;           // 0 = auto (spans both layers)                [mm]
$fn       = 48;

// ---------------------------------------------------------------------------
//  Derived kinematics
// ---------------------------------------------------------------------------
p     = 180 / n;                     // half-segment angle (deg)
cotp  = cos(p) / sin(p);
kink  = 180 - 2*p;                   // strut kink angle (deg), = 120 for n=6

function phi(t)  = phi_collapsed + (phi_expanded - phi_collapsed) * t;
function Ro(ph)  = L * (cotp*cos(ph) + sin(ph));
function Ri(ph)  = L * (cotp*cos(ph) - sin(ph));
function Rm(ph)  = L *  cos(ph) / sin(p);
function pol(r,a)= [r*cos(a), r*sin(a)];

// ---------------------------------------------------------------------------
//  Low level shapes
// ---------------------------------------------------------------------------

// Control point of a quadratic Bezier whose mid-curve sagitta = bow*|p1-p2|,
// bulging to the LEFT of p1->p2 (sign of `s` flips the side).
function ctrl(p1, p2, s) =
    let (m  = [(p1[0]+p2[0])/2, (p1[1]+p2[1])/2],
         d  = [p2[0]-p1[0], p2[1]-p1[1]],
         Lc = norm(d),
         nrm= [-d[1]/Lc, d[0]/Lc])
    [m[0] + nrm[0]*2*s*Lc, m[1] + nrm[1]*2*s*Lc];

function bez(p1, pc, p2, u) =
    [ for (k=[0,1]) pow(1-u,2)*p1[k] + 2*(1-u)*u*pc[k] + u*u*p2[k] ];

// A curved beam of constant width from p1 to p2 (a chain of hulled discs).
// This IS the load path - it connects two pivots directly.
module arc_beam(p1, p2, s) {
    pc  = ctrl(p1, p2, s);
    pts = [ for (i=[0:seg]) bez(p1, pc, p2, i/seg) ];
    for (i=[0:seg-1])
        hull() {
            translate(pts[i])   circle(d = beam_w);
            translate(pts[i+1]) circle(d = beam_w);
        }
}

// The 2D body of one strut, drawn in GLOBAL coordinates at its reference pose.
// It is two curved beams (inner-arm and outer-arm) meeting at the centre pivot,
// with a reinforcing pad at each of the three pivots. Nothing sticks out past
// a pivot, so the outer material edge is set by the OUTER PIVOT, not a corner.
module strut2d(C, U, Ipt, sgn) {
    difference() {
        union() {
            arc_beam(C, U,   sgn*bow);    // centre -> outer
            arc_beam(C, Ipt,-sgn*bow);    // centre -> inner
            translate(C)   circle(d = boss_d);
            translate(U)   circle(d = boss_d);
            translate(Ipt) circle(d = boss_d);
        }
        translate(C)   circle(d = hole_d);
        translate(U)   circle(d = hole_d);
        translate(Ipt) circle(d = hole_d);
    }
}

// Rigidly move a strut defined at its reference pose to the current pose.
// The link is rigid, so matching the centre pivot and the centre->outer
// direction carries all three pivots to the right place.
module place(C0, U0, C1, U1) {
    dth = atan2(U1[1]-C1[1], U1[0]-C1[0]) - atan2(U0[1]-C0[1], U0[0]-C0[0]);
    translate(C1) rotate(dth) translate(-C0) children();
}

// ---------------------------------------------------------------------------
//  One strut, extruded and placed at the requested deployment
// ---------------------------------------------------------------------------
module strut(A, sgn, t) {
    C0 = pol(Rm(phi_collapsed), A);
    U0 = pol(Ro(phi_collapsed), A + sgn*p);
    I0 = pol(Ri(phi_collapsed), A - sgn*p);
    C1 = pol(Rm(phi(t)), A);
    U1 = pol(Ro(phi(t)), A + sgn*p);
    place(C0, U0, C1, U1)
        linear_extrude(th) strut2d(C0, U0, I0, sgn);
}

// ---------------------------------------------------------------------------
//  The full ring
// ---------------------------------------------------------------------------
module assembly(t = deploy) {
    for (k = [0 : n-1]) {
        A = k * 360 / n;
        color("SteelBlue")                       strut(A, +1, t);   // lower
        color("IndianRed") translate([0,0,th+layer_gap]) strut(A, -1, t);  // upper
    }
    if (pin_len == 0) for (k = [0 : n-1]) {
        A = k * 360 / n;  ph = phi(t);
        pin_at(pol(Rm(ph), A));
        pin_at(pol(Ro(ph), A + p));   // shared outer node
        pin_at(pol(Ri(ph), A - p));   // shared inner node
    }
}

module pin_at(xy) {
    color("gold")
        translate([xy[0], xy[1], -1])
            cylinder(d = hole_d - 0.2, h = 2*th + layer_gap + 2);
}

// ---------------------------------------------------------------------------
//  Printable single strut (flat on the bed, reference shape)
// ---------------------------------------------------------------------------
module print_one() {
    C0 = pol(Rm(phi_collapsed), 0);
    U0 = pol(Ro(phi_collapsed), + p);
    I0 = pol(Ri(phi_collapsed), - p);
    translate([-C0[0], -C0[1], 0])
        linear_extrude(th) strut2d(C0, U0, I0, +1);
}

// A simple printable pivot pin: shaft + two caps (press/rivet style).
module pin() {
    h   = pin_len > 0 ? pin_len : 2*th + layer_gap;
    d   = hole_d - 0.25;
    cap = boss_d*0.55;
    cylinder(d = d,   h = h);
    cylinder(d = cap, h = 0.8);
    translate([0,0,h-0.8]) cylinder(d = cap, h = 0.8);
}

// ---------------------------------------------------------------------------
//  Dispatch + report
// ---------------------------------------------------------------------------
mo = boss_d/2;   // material overhang past a pivot (the boss radius)
echo(str("n = ", n, "   kink = ", kink, " deg   arm L = ", L, " mm"));
echo(str("PIVOT NODE RADII (the real load path) ------------------------"));
echo(str("  COLLAPSED phi=", phi_collapsed, "  Ri=", Ri(phi_collapsed),
         "  Rm=", Rm(phi_collapsed), "  Ro=", Ro(phi_collapsed)));
echo(str("  EXPANDED  phi=", phi_expanded,  "  Ri=", Ri(phi_expanded),
         "  Rm=", Rm(phi_expanded),  "  Ro=", Ro(phi_expanded)));
echo(str("MATERIAL EDGES (pivot radius +/- boss ", mo, " mm) ------------"));
echo(str("  COLLAPSED  inner~", max(0,Ri(phi_collapsed)-mo),
         "  outer~", Ro(phi_collapsed)+mo));
echo(str("  EXPANDED   inner~", max(0,Ri(phi_expanded)-mo),
         "  outer~", Ro(phi_expanded)+mo));
echo(str("Outer circle grows ", Ro(phi_expanded)-Ro(phi_collapsed),
         " mm; inner circle grows ", Ri(phi_expanded)-Ri(phi_collapsed), " mm."));
echo(str("Outer full range for n=", n, " = sec(180/n) = ", 1/cos(p),
         " (", 100*(1/cos(p)-1), "% )"));

if      (show == "assembly") assembly();
else if (show == "print")    print_one();
else if (show == "pin")      pin();

// ============================================================================
//  NOTES
// ----------------------------------------------------------------------------
//  * Load path: each strut is two curved beams meeting at the centre pivot,
//    joining inner<->centre<->outer directly. Outward push on the inner pins is
//    reacted at the outer pins THROUGH THE BEAMS - no unsupported corners.
//
//  * Two print layers: "+" struts (lower) and their mirror "-" struts (upper).
//    Every pivot joins one lower + one upper strut, so a single pin passes
//    through both. The "-" strut is just the "+" strut flipped over, so you
//    print ONE design: 12 copies, flip 6.  Pivot count = 3n = 18.
//
//  * Retuning: keep phi_expanded < phi_collapsed and both on the phi >= p side
//    (p = 30 deg here) to keep BOTH circles growing on deploy. Push phi_expanded
//    toward p for maximum outer radius; raise phi_collapsed for a smaller
//    collapsed hole + a longer stroke. The console echoes the exact radii.
//
//  HOW TO PRINT / ASSEMBLE
//    show="print" -> one flat strut (print 12, flip 6). show="pin" -> a press
//    pin (print 18) or use M3 screws through the 3.2 mm holes. Build the lower
//    ring of "+" struts, drop the "-" struts on top, pin every joint, and leave
//    the pivots free to rotate.
// ============================================================================
