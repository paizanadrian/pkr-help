# poker_click_images_full.py
import random
import urllib.parse
from collections import Counter, defaultdict
from itertools import combinations

import streamlit as st
from st_clickable_images import clickable_images

# ============ SETUP ============
st.set_page_config(page_title="Texas Hold'em – River, adversari multipli + preview", layout="wide")

# --- Config pachet cărți (cu "10", nu "T") ---
SUITS = ["S", "H", "C", "D"]  # ♠ ♥ ♣ ♦
SUIT_SYMBOL = {"S": "♠", "H": "❤️", "C": "♣", "D": "♦️", "Q": "?"}
SUIT_COLOR = {"S": "#111827", "H": "#b91c1c", "C": "#111827", "D": "#b91c1c", "Q": "#111827"}  # negru/roșu
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]  # A e ultimul
RVAL = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14
DECK = [r + s for s in SUITS for r in RANKS]

# --- Helpers rank/suit corecte pentru "10" ---
def split_card(c: str):
    """Întoarce (rank, suit) dintr-un cod ca '10H', 'AS', '9D'."""
    return c[:-1], c[-1]

def pretty(c: str) -> str:
    r, s = split_card(c)
    return f"{r}{SUIT_SYMBOL[s]}"

# --- SVG (data URI) pentru o carte; w,h mai mari pentru preview ---
def svg_card(rank: str, suit: str, selected: bool, w: int = 120, h: int = 190) -> str:

    sym = SUIT_SYMBOL[suit]
    fg = SUIT_COLOR[suit]
    stroke = "#10b981" if selected else "rgba(0,0,0,0.25)"
    opacity = "0.6" if selected else "1.0"

    face_sz = max(24, int(0.285 * h))
    small_sz = max(12, int(0.126 * h))
    rx = max(10, int(0.084 * w))
    pad = max(4, int(0.028 * h))
    wrect = w - 2 * pad
    hrect = h - 2 * pad
    x_small_l, y_small_l = int(0.14 * w), int(0.26 * h)
    x_small_r, y_small_r = int(0.72 * w), int(0.80 * h)
    x_face, y_face = int(0.38 * w), int(0.57 * h)

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
      <defs>
        <style>
          .face {{ font: 700 {face_sz}px system-ui, -apple-system, Segoe UI, Roboto; fill:{fg}; }}
          .small {{ font: 700 {small_sz}px system-ui, -apple-system, Segoe UI, Roboto; fill:{fg}; }}
        </style>
      </defs>
      <rect x="{pad}" y="{pad}" rx="{rx}" ry="{rx}" width="{wrect}" height="{hrect}"
            fill="white" stroke="{stroke}" stroke-width="5" opacity="{opacity}"/>
      <text x="{x_small_l}" y="{y_small_l}" class="small">{rank}</text>
      <text x="{x_small_r}" y="{y_small_r}" class="small" transform="rotate(180,{x_small_r},{y_small_r})">{rank}</text>
      <text x="{x_face}" y="{y_face}" class="face">{sym}</text>
    </svg>
    """
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)

# ============ HAND EVALUATOR (7 cărți) ============
CAT_RANK = {
    "high": 1, "pair": 2, "two_pair": 3, "trips": 4, "straight": 5,
    "flush": 6, "full": 7, "quads": 8, "straight_flush": 9,
}

def best_straight(vals):
    u = sorted(set(vals), reverse=True)
    if {14, 5, 4, 3, 2}.issubset(set(vals)):  # A-5 (wheel)
        return 5
    for i in range(len(u) - 4):
        if u[i] - u[i + 4] == 4:
            return u[i]
    return None

def eval7(cards7):
    ranks = [RVAL[split_card(c)[0]] for c in cards7]
    suits = [split_card(c)[1] for c in cards7]
    cnt = Counter(ranks)

    # Straight flush?
    suit_counts = Counter(suits)
    flush_suit = next((s for s, c in suit_counts.items() if c >= 5), None)
    if flush_suit:
        vals = [r for r, s in zip(ranks, suits) if s == flush_suit]
        sf = best_straight(vals)
        if sf:
            return (CAT_RANK["straight_flush"], sf)

    # Quads
    if 4 in cnt.values():
        four = max([r for r, c in cnt.items() if c == 4])
        kicker = max([r for r, c in cnt.items() if r != four])
        return (CAT_RANK["quads"], four, kicker)

    # Full house
    trips = sorted([r for r, c in cnt.items() if c == 3], reverse=True)
    pairs = sorted([r for r, c in cnt.items() if c == 2], reverse=True)
    if trips and (len(trips) >= 2 or pairs):
        t = trips[0]
        p = trips[1] if len(trips) >= 2 else pairs[0]
        return (CAT_RANK["full"], t, p)

    # Flush
    if flush_suit:
        top5 = tuple(sorted([r for r, s in zip(ranks, suits) if s == flush_suit], reverse=True)[:5])
        return (CAT_RANK["flush"],) + top5

    # Straight
    st_high = best_straight(ranks)
    if st_high:
        return (CAT_RANK["straight"], st_high)

    # Trips
    if trips:
        t = trips[0]
        kick = tuple(sorted([r for r in ranks if r != t], reverse=True)[:2])
        return (CAT_RANK["trips"], t) + kick

    # Two pair
    if len(pairs) >= 2:
        p1, p2 = pairs[:2]
        top, low = max(p1, p2), min(p1, p2)
        kicker = max([r for r in ranks if r != p1 and r != p2])
        return (CAT_RANK["two_pair"], top, low, kicker)

    # One pair
    if len(pairs) == 1:
        p = pairs[0]
        kick = tuple(sorted([r for r in ranks if r != p], reverse=True)[:3])
        return (CAT_RANK["pair"], p) + kick

    # High card
    return (CAT_RANK["high"],) + tuple(sorted(ranks, reverse=True)[:5])

def label_from_score(score):
    inv = {v: k for k, v in CAT_RANK.items()}
    return inv[score[0]]

RO_LABEL = {
    "high": "High card", "pair": "Pereche", "two_pair": "Două perechi", "trips": "Trei de un fel",
    "straight": "Chintă", "flush": "Culoare", "full": "Full", "quads": "Careu", "straight_flush": "Chintă de culoare",
}

# Afișare tiebreakere scurt
RINV = {v: k for k, v in RVAL.items()}  # 2..14 -> "2".. "A"
def rank_ro(val: int) -> str:
    return RINV[val]

def format_hero_score(score: tuple) -> str:
    cat = score[0]; rest = score[1:]
    if cat == CAT_RANK["straight_flush"]:
        return f"la {rank_ro(rest[0])}"
    if cat == CAT_RANK["quads"]:
        return f"(4x {rank_ro(rest[0])} + kicker {rank_ro(rest[1])})"
    if cat == CAT_RANK["full"]:
        return f"({rank_ro(rest[0])} peste {rank_ro(rest[1])})"
    if cat == CAT_RANK["flush"]:
        return " " + " ".join(rank_ro(v) for v in rest)
    if cat == CAT_RANK["straight"]:
        return f"la {rank_ro(rest[0])}"
    if cat == CAT_RANK["trips"] and len(rest) == 3:
        t, k1, k2 = rest
        return f"({rank_ro(t)} + {rank_ro(k1)} {rank_ro(k2)})"
    if cat == CAT_RANK["two_pair"] and len(rest) == 3:
        p1, p2, k = rest
        hi, lo = rank_ro(p1), rank_ro(p2)
        return f"({hi} și {lo} + kicker {rank_ro(k)})"
    if cat == CAT_RANK["pair"] and len(rest) == 4:
        p, k1, k2, k3 = rest
        return f"({rank_ro(p)} + {rank_ro(k1)} {rank_ro(k2)} {rank_ro(k3)})"
    return " " + " ".join(rank_ro(v) for v in rest)

# ============ STATE ============
if "selected" not in st.session_state:
    st.session_state.selected = []  # 2 (ale tale) + 5 board = 7
if "last_idx" not in st.session_state:
    st.session_state.last_idx = {s: -1 for s in SUITS}  # debounce pe fiecare rând
if "ui_version" not in st.session_state:
    st.session_state.ui_version = 0  # remount clickable_images după reset

# ============ SIDEBAR ============
st.sidebar.header("Setări masă")
total_players = st.sidebar.number_input("Număr total jucători", min_value=2, max_value=10, value=6, step=1)
use_mc = st.sidebar.checkbox("Monte Carlo (deal fără înlocuire)", value=True)
mc_trials = st.sidebar.slider("Runde simulare", 1_000, 100_000, 20_000, step=1_000)
st.sidebar.markdown("---")
st.sidebar.markdown("### Ordinea mâinilor câștigătoare:")
legend_txt = (
    "1) Chintă roială\n"
    "2) Chintă de culoare\n"
    "3) Careu\n"
    "4) Full\n"
    "5) Culoare\n"
    "6) Chintă\n"
    "7) Trei de un fel\n"
    "8) Două perechi\n"
    "9) O pereche\n"
    "10) Carte mare"
)
st.sidebar.text(legend_txt)
st.sidebar.markdown("---")
# ============ HEADER + PREVIEW ============
sel = st.session_state.selected
hole, board_all = sel[:2], sel[2:7]

left, right = st.columns([1, 1])

with left:
    st.markdown(f"**Cărțile tale (2):** {' '.join(pretty(c) for c in hole) if hole else '-'}")
    st.markdown(f"**Board (5):** {' '.join(pretty(c) for c in board_all) if board_all else '-'}")

    # --- dacă avem 7 cărți, calculează M/W/T sus ---
    M = W = T = None
    if len(sel) == 7:
        hero_hole = sel[:2]
        board = sel[2:7]
        hero_score = eval7(hero_hole + board)
        remaining = [c for c in DECK if c not in sel]
        all_pairs = list(combinations(remaining, 2))
        M = len(all_pairs)
        wins = ties = 0
        for a, b in all_pairs:
            sc = eval7([a, b] + board)
            if sc > hero_score:
                wins += 1
            elif sc == hero_score:
                ties += 1
        W, T = wins, ties
        st.markdown(
            f"**Combinații posibile pentru 1 adversar:** {M:,}  ·  "
            f"**Te bat:** {W:,}  ·  **Egal:** {T:,}"
        )
        hero_label = label_from_score(hero_score)
        st.success(f"🃏 Mâna ta pe river: **{RO_LABEL[hero_label]}** {format_hero_score(hero_score)}")

    else:
        st.markdown("**Combinații posibile:** –  ·  **Te bat:** –  ·  **Egal:** –")

    # --- Monte Carlo sus-stânga + Pie chart ---
    def render_pie(prob_red: float):
        import matplotlib.pyplot as plt
        prob_red = max(0.0, min(1.0, prob_red))
        prob_green = 1.0 - prob_red
        fig, ax = plt.subplots(figsize=(1.2, 1.2))
        ax.pie(
            [prob_red, prob_green],
            labels=[f"Pierd ({prob_red*100:.1f}%)", f"Castig ({prob_green*100:.1f}%)"],
            colors=["#ef4444", "#10b981"],  # roșu / verde
            startangle=90,
            counterclock=False,
            wedgeprops={"linewidth": 0.8, "edgecolor": "white"},
            labeldistance=1.25  # mută textul mai spre exterior

        )
        plt.setp(ax.texts, fontsize=4)
        ax.axis("equal")
        # Donut opțional:
        # centre = plt.Circle((0, 0), 0.70, fc="white"); fig.gca().add_artist(centre)
        st.pyplot(fig, use_container_width=False)

    if len(sel) == 7:
        k_opps = max(0, total_players - 1)

        # aprox. analitică (fallback)
        p1_win = (W / M) if M else 0.0
        p1_tie = (T / M) if M else 0.0
        p_any_beats_approx = 1 - (1 - p1_win) ** k_opps if k_opps > 0 else 0.0
        p_any_tieonly_approx = ((1 - p1_win) ** k_opps - (1 - p1_win - p1_tie) ** k_opps) if k_opps > 0 else 0.0

        # dacă Monte Carlo e activ și există adversari
        p_red = p_any_beats_approx
        if use_mc and k_opps > 0:
            hits = ties_mc = 0
            rem = [c for c in DECK if c not in sel]
            for _ in range(mc_trials):
                deck = rem[:]
                random.shuffle(deck)
                someone_beats = False
                someone_ties = False
                for i in range(k_opps):
                    a, b = deck[2 * i], deck[2 * i + 1]
                    sc = eval7([a, b] + board_all)
                    if sc > hero_score:
                        someone_beats = True
                        break
                    elif sc == hero_score:
                        someone_ties = True
                if someone_beats:
                    hits += 1
                elif someone_ties:
                    ties_mc += 1
            p_mc_beats = hits / mc_trials if mc_trials else 0.0
            p_mc_tieonly = ties_mc / mc_trials if mc_trials else 0.0
            st.markdown(
                f"**Prob. ≥1 adversar te bate:** {p_mc_beats*100:.2f}%  \n"
                f"**Prob. egal (și nimeni nu te bate):** {p_mc_tieonly*100:.2f}%"
            )
            p_red = p_mc_beats
        else:
            st.markdown(
                f"**Prob. ≥1 adversar te bate (aprox.):** {p_any_beats_approx*100:.2f}%  \n"
                f"**Prob. egal (și nimeni nu te bate) (aprox.):** {p_any_tieonly_approx*100:.2f}%"
            )

        # Pie chart sub probabilități
        render_pie(p_red)
    else:
        st.markdown(
            "**Prob. ≥1 adversar te bate:** –  \n"
            "**Prob. egal (și nimeni nu te bate):** –"
        )

with right:
    st.markdown("**CARTILE TALE + Flop, River, Turn**")
    # Rând 1: HOLE (2)
    row1 = st.container()
    with row1:
        cols = st.columns(2)
        for i in range(2):
            with cols[i]:
                if i < len(hole):
                    r, s = split_card(hole[i])
                    st.markdown(f"<img src='{svg_card(r, s, True, w=90, h=120)}'/>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<img src='{svg_card('?', 'Q', False, w=90, h=120)}'/>", unsafe_allow_html=True)
    st.divider()
    # Rând 2: BOARD complet (5)
    row2 = st.container()
    with row2:
        cols = st.columns(5)
        for i in range(5):
            with cols[i]:
                if i < len(board_all):
                    r, s = split_card(board_all[i])
                    st.markdown(f"<img src='{svg_card(r, s, True, w=90, h=120)}'/>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<img src='{svg_card('?', 'Q', False, w=90, h=120)}'/>", unsafe_allow_html=True)

# RESET cu remount (fix pentru „dublu click” fantomă după reset)
if st.button("🔄 Resetare selecție"):
    st.session_state.selected = []
    st.session_state.last_idx = {s: -1 for s in SUITS}
    st.session_state.ui_version += 1  # remount clickable_images
    st.rerun()

st.divider()

# ============ GRID CLICKABIL (4 rânduri) ============
ui_v = st.session_state.ui_version
pending = []  # cardurile apăsate în acest ciclu
sel = st.session_state.selected  # recitește după posibil reset

for s in SUITS:
    imgs, ids = [], []
    for r in RANKS:
        c = r + s
        imgs.append(svg_card(r, s, c in sel, w=140, h=190))
        ids.append(c)

    idx = clickable_images(
        imgs,
        titles=ids,
        div_style={"display": "grid", "gridTemplateColumns": "repeat(13, 1fr)", "gap": "8px"},
        img_style={"margin": "0", "width": "50%", "height": "auto", "borderRadius": "12px"},
        key=f"row_{s}_{ui_v}",  # include ui_version: remount după reset
    )

    # Debounce pe rând: procesează doar dacă indexul e nou față de ultimul
    if isinstance(idx, int) and idx > -1 and idx != st.session_state.last_idx.get(s, -1):
        st.session_state.last_idx[s] = idx
        pending.append(ids[idx])

# aplică toate click-urile ca toggle, apoi un singur rerun
updated = False
for c in pending:
    if c in st.session_state.selected:
        st.session_state.selected.remove(c)
        updated = True
    else:
        if len(st.session_state.selected) < 7:
            st.session_state.selected.append(c)
            updated = True

if updated:
    st.rerun()

st.divider()

# ============ AFIȘARE MÂNA TA + LISTĂ ÎNVINGĂTOARE ============
if len(st.session_state.selected) == 7:
    hero_hole = st.session_state.selected[:2]
    board = st.session_state.selected[2:7]
    hero_score = eval7(hero_hole + board)
    hero_label = label_from_score(hero_score)

    # Afișează clar mâna ta pe river
    st.success(f"🃏 Mâna ta pe river: **{RO_LABEL[hero_label]}** {format_hero_score(hero_score)}")

    # (Optional) Lista mâinilor câștigătoare pe categorii
    remaining = [c for c in DECK if c not in st.session_state.selected]
    all_pairs = list(combinations(remaining, 2))
    wins_by_cat = defaultdict(list)
    for a, b in all_pairs:
        sc = eval7([a, b] + board)
        if sc > hero_score:
            wins_by_cat[label_from_score(sc)].append((a, b))

    st.subheader("Mâini posibile câștigătoare (1 adversar) – grupate")
    order = ["straight_flush", "quads", "full", "flush", "straight", "trips", "two_pair", "pair", "high"]
    for cat in order:
        if wins_by_cat.get(cat):
            ro = RO_LABEL[cat]
            hands = wins_by_cat[cat]
            st.markdown(f"**{ro} — {len(hands)} combinații**")
            with st.expander("Vezi exemple"):
                show = min(120, len(hands))
                st.write(", ".join(f"{pretty(a)} {pretty(b)}" for (a, b) in hands[:show]) + (" ..." if len(hands) > show else ""))
