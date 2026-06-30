# Two dials in the (5,6) subsystem. 5-dial steps 72 deg/unit, 6-dial 60 deg/unit.
# Relative offset (5-dial minus 6-dial), measured one consistent way:
def theta(a):
    r5, r6 = a % 5, a % 6
    return (72*r5 - 60*r6) % 360

# Claim A: the relative pointer angle linearly encodes the mod-30 magnitude,
#          12 deg per unit (the dials drift apart 72-60=12 deg each count).
print("theta(a) == 12*(a mod 30) for all a:", all(theta(a) == 12*(a % 30) for a in range(210)))

# Claim B: carry (mod 30) == the two relative angles summing to a full turn.
def carry_by_angle(a, b, c):
    return 1 if theta(a) + theta(b) + 12*c >= 360 else 0
def carry_true(a, b, c):
    return 1 if (a % 30) + (b % 30) + c >= 30 else 0
print("carry == [theta_a + theta_b + 12*c >= 360] for all a,b,c:",
      all(carry_by_angle(a,b,c) == carry_true(a,b,c)
          for a in range(210) for b in range(210) for c in (0,1)))

# Refinement: d1 = (r5 - r6) mod 6 is only the COARSE 60-deg part of the angle.
# theta = 60*d1 + 12*r5, so judging carry from d1 alone fails near boundaries:
def d1(a): return (a%5 - a%6) % 6
bad_pairs=[]
for a in range(30):
    for b in range(30):
        if (1 if d1(a)+d1(b) >= 6 else 0) != carry_true(a,b,0):
            bad_pairs.append((a,b,d1(a),d1(b)))
print(f"d1-alone disagrees with true carry in {len(bad_pairs)} of 900 (5,6)-pairs; e.g.:",
      bad_pairs[:3])
print("  (because theta = 60*d1 + 12*r5: the 12*r5 fine part matters at the edge)")
