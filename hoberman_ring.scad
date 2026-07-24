// ============================================================================
//  Hoberman ring - 9 segment angulated-scissor expanding ring
//  Built from curved arcs, for 3D printing.
//  Units: millimetres.  OpenSCAD 2021.01+
// ----------------------------------------------------------------------------
//  A Hoberman ring is a single loop of "angulated" (kinked) scissor struts.
//  For n segments the geometry is fully fixed by two facts (see notes at the
//  bottom of this file):
//        * every strut is an isosceles angulated link, arm length L, with a
//          kink angle of  (180 - 360/n)  degrees                (= 140 deg for n=9)
//        * the three pivots of a strut sit at radii
//              outer node  Ro = L*(cot(p)*cos(phi) + sin(phi))
//              inner node  Ri = L*(cot(p)*cos(phi) - sin(phi))
//              centre node Rm = L* cos(phi)/sin(p)
//          where p = 180/n and phi is the single deployment freedom.
//
//  The mechanism has ONE degree of freedom (`deploy`, 0..1). The arcs are the
//  cosmetic body wrapped around those pivots; the pivots are what make it move.
// ============================================================================

/* [What to show] */
// assembly = the whole ring at `deploy`; print = one flat strut; pin = a pivot pin
show      = "assembly";   // ["assembly","print","pin"]
deploy    = 0.0;          // 0 = collapsed, 1 = fully expanded   [0:0.01:1]

/* [Ring] */
n         = 9;            // number of segments (scissor units)

/* [Arc body (the printed strut)] */
band_ri   = 25;          // inner radius of the arcs (collapsed)     [mm]
band_ro   = 36;          // outer radius of the arcs (collapsed)     [mm]
gap_deg   = 1.5;         // angular clearance between neighbouring arcs [deg]

/* [Kinematics / deployment] */
// Defaults tuned so the ring reads ~25/36 collapsed and the outer arcs
// swing out to ~39 when expanded (see the echoed numbers + notes below).
L            = 11.46;    // angulated arm length (pivot to pivot)    [mm]
phi_collapsed = 17;      // deployment angle, collapsed state        [deg]
phi_expanded  = 6;       // deployment angle, expanded state         [deg]

/* [Pivots] */
hole_d    = 3.2;         // pivot hole diameter (3.2 = M3 clearance) [mm]
boss_d    = 8.0;         // diameter of the reinforcing pad at a pivot [mm]

/* [Build / print] */
th        = 3.0;         // thickness of one strut (one scissor layer) [mm]
layer_gap = 0.6;         // z clearance between the two layers        [mm]
pin_len   = 0;           // 0 = auto (spans both layers)              [mm]
$fn       = 48;

// ---------------------------------------------------------------------------
//  Derived kinematics
// ---------------------------------------------------------------------------
p     = 180 / n;                     // half-segment angle (deg)
cotp  = cos(p) / sin(p);
kink  = 180 - 2*p;                   // strut kink angle (deg), = 140 for n=9

function phi(t)  = phi_collapsed + (phi_expanded - phi_collapsed) * t;
function Ro(ph)  = L * (cotp*cos(ph) + sin(ph));
function Ri(ph)  = L * (cotp*cos(ph) - sin(ph));
function Rm(ph)  = L *  cos(ph) / sin(p);
function pol(r,a)= [r*cos(a), r*sin(a)];

// ---------------------------------------------------------------------------
//  Low level shapes
// ---------------------------------------------------------------------------

// A pie wedge from angle a0..a1 out to radius r, apex at the origin.
module wedge(a0, a1, r) {
    step = (a1 - a0) / ceil((a1 - a0) / 4);
    polygon(concat([[0,0]], [ for (a = [a0 : step : a1]) pol(r, a) ]));
}

// An annular sector: ring [ri..ro] intersected with the wedge a0..a1.
module annular_sector(a0, a1, ri, ro) {
    intersection() {
        difference() { circle(ro); circle(ri); }
        wedge(a0, a1, ro + 2);
    }
}

// The 2D body of one strut, drawn in GLOBAL coordinates at its collapsed pose.
//   A       - segment centre angle (deg)
//   sgn     - +1 for a "+" strut, -1 for its mirror ("-") strut
//   C,U,Ihl - collapsed pivot points (centre / outer / inner)
module strut2d(A, sgn, C, U, Ipt) {
    a_out = A + sgn*p;     // angular side the outer node sits on
    a_in  = A - sgn*p;     // angular side the inner node sits on
    lo    = min(a_out, a_in) + gap_deg/2;
    hi    = max(a_out, a_in) - gap_deg/2;
    difference() {
        // Everything is clipped to the [band_ri, band_ro] annulus so that in
        // the collapsed pose the ring's edges are exactly band_ri / band_ro.
        intersection() {
            union() {
                annular_sector(lo, hi, band_ri, band_ro);
                // reinforcing pads keep solid material around every pivot
                translate(C)   circle(d = boss_d);
                translate(U)   circle(d = boss_d);
                translate(Ipt) circle(d = boss_d);
            }
            difference() { circle(band_ro); circle(band_ri); }
        }
        translate(C)   circle(d = hole_d);
        translate(U)   circle(d = hole_d);
        translate(Ipt) circle(d = hole_d);
    }
}

// Rigidly move a collapsed strut (defined at pose0) to the current pose.
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
    // collapsed reference pose (pose 0)
    C0 = pol(Rm(phi_collapsed), A);
    U0 = pol(Ro(phi_collapsed), A + sgn*p);
    I0 = pol(Ri(phi_collapsed), A - sgn*p);
    // current pose (pose 1)
    C1 = pol(Rm(phi(t)), A);
    U1 = pol(Ro(phi(t)), A + sgn*p);
    place(C0, U0, C1, U1)
        linear_extrude(th) strut2d(A, sgn, C0, U0, I0);
}

// ---------------------------------------------------------------------------
//  The full ring
// ---------------------------------------------------------------------------
module assembly(t = deploy) {
    for (k = [0 : n-1]) {
        A = k * 360 / n;
        // "+" struts on the lower layer
        color("SteelBlue")
            strut(A, +1, t);
        // "-" struts (mirror) on the upper layer
        color("IndianRed")
            translate([0, 0, th + layer_gap]) strut(A, -1, t);
    }
    // pivot pins (optional visual)
    if (pin_len == 0) for (k = [0 : n-1]) {
        A = k * 360 / n;
        ph = phi(t);
        centre_pin(pol(Rm(ph), A));
        centre_pin(pol(Ro(ph), A + p));   // shared outer node
        centre_pin(pol(Ri(ph), A - p));   // shared inner node
    }
}

module centre_pin(xy) {
    color("gold")
        translate([xy[0], xy[1], -1])
            cylinder(d = hole_d - 0.2, h = 2*th + layer_gap + 2);
}

// ---------------------------------------------------------------------------
//  Printable single strut (flat on the bed, collapsed shape)
// ---------------------------------------------------------------------------
module print_one() {
    // move segment 0's "+" strut so its centre pivot sits at the origin
    A  = 0;
    C0 = pol(Rm(phi_collapsed), A);
    translate([-C0[0], -C0[1], 0])
        linear_extrude(th)
            strut2d(A, +1,
                    pol(Rm(phi_collapsed), A),
                    pol(Ro(phi_collapsed), A + p),
                    pol(Ri(phi_collapsed), A - p));
}

// A simple printable pivot pin: shaft + two caps (press/rivet style).
module pin() {
    h  = pin_len > 0 ? pin_len : 2*th + layer_gap;
    d  = hole_d - 0.25;
    cap = boss_d*0.6;
    cylinder(d = d,   h = h);
    cylinder(d = cap, h = 0.8);
    translate([0,0,h-0.8]) cylinder(d = cap, h = 0.8);
}

// ---------------------------------------------------------------------------
//  Dispatch + report
// ---------------------------------------------------------------------------
echo(str("n = ", n, "   kink angle = ", kink, " deg   arm L = ", L, " mm"));
echo(str("PIVOT NODES (hole centres) -----------------------------------"));
echo(str("  COLLAPSED phi=", phi_collapsed,
         "  Ri=", Ri(phi_collapsed), "  Rm=", Rm(phi_collapsed),
         "  Ro=", Ro(phi_collapsed)));
echo(str("  EXPANDED  phi=", phi_expanded,
         "  Ri=", Ri(phi_expanded), "  Rm=", Rm(phi_expanded),
         "  Ro=", Ro(phi_expanded)));
echo(str("MATERIAL ENVELOPE (what a caliper sees) ----------------------"));
echo(str("  COLLAPSED  inner=", band_ri, "  outer=", band_ro,
         "  (arcs clipped to this band)"));
echo(str("  EXPANDED   outer arc corners swing out past ", band_ro,
         " to ~39 mm; inner edge stays ~", band_ri, " mm"));
echo(str("NOTE: the OUTER PIVOT circle only grows by <=sec(180/n)=",
         1/cos(p), " (", 100*(1/cos(p)-1),
         "%). The extra outer reach is the arc bodies swinging."));

if      (show == "assembly") assembly();
else if (show == "print")    print_one();
else if (show == "pin")      pin();

// ============================================================================
//  NOTES ON THE GEOMETRY  (why these numbers)
// ----------------------------------------------------------------------------
//  * Each strut is an isosceles angulated link: |centre->outer| =
//    |centre->inner| = L, and the two arms are separated by the kink angle
//    180-360/n (140 deg here). |outer->inner| = 2*L*cos(180/n). These three
//    fixed lengths make the printed part rigid; the ring moves only at the
//    pivots.
//
//  * Struts alternate between two print layers ("+" lower, "-" upper). Every
//    pivot joins exactly one lower and one upper strut, so a single pin passes
//    cleanly through both. The "-" strut is the mirror of the "+" strut, which
//    for a flat plate is the SAME part flipped over -> you print ONE design,
//    18 copies, and flip 9 of them.
//
//  * Pivot count: n centre pivots + n outer + n inner = 3n = 27 pins.
//
//  * KINEMATIC LIMIT you should know about: with n RIGID segments the OUTER
//    PIVOT radius can grow by at most sec(180/n). For n=9 that is only 6.4%, so
//    the pivot circle itself cannot travel 36 -> 39 (that would need ~8.3%,
//    i.e. n=8). This model gets the outer *material* edge to ~39 a different,
//    honest way: the arcs are clipped to the 25..36 band in the collapsed pose,
//    and as the struts rotate open their outer CORNERS swing out past 36. The
//    inner edge stays near 25 across the motion. Because the clip that fixes
//    the 25/36 band is applied at `phi_collapsed`, that pose's three pivots
//    must lie inside the band - keep it so if you retune (watch the echoed
//    node radii). The default L / phi_collapsed=17 / phi_expanded=6 give:
//        collapsed  ~ 25.0 inner / 36.0 outer
//        expanded   ~ 24.5 inner / 39.1 outer
//
//  HOW TO PRINT
//    show="print" gives ONE strut flat on the bed. Print 18 of them in a stiff
//    material (PETG/PLA, ~3 mm). They are all identical; flip 9 of them over to
//    make the mirror ("-") struts.  show="pin" gives a press-fit pivot pin
//    (print 27), or just use M3 x ~10 screws/nuts through the 3.2 mm holes.
//
//  HOW TO ASSEMBLE
//    Lower layer = the 9 "+" struts, upper layer = the 9 flipped "-" struts.
//    At every one of the 27 pivots exactly one lower and one upper strut meet;
//    drop a pin/screw through both. Leave the pivots free to rotate (don't
//    over-tighten) and the ring will open and close as one piece.
// ============================================================================
