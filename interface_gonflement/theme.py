"""Thèmes de l'interface : couleurs douces, contraste modéré.

  sombre : inspiré de la palette Nord (gris-bleu, accents pastel)
  clair  : fond sable, accents désaturés

`appliquer(racine, nom)` configure tous les styles ttk et renvoie la palette,
utilisée ensuite pour les widgets tk, la console et les courbes.
"""

from tkinter import ttk

PALETTES = {
    "sombre": dict(
        fond="#2e3440", panneau="#353c4a", champ="#3f4758", bord="#4c566a",
        texte="#e5e9f0", doux="#9aa5b8", accent="#88c0d0", accent2="#81a1c1",
        vert="#a3be8c", rouge="#bf616a", orange="#d08770", jaune="#ebcb8b",
        violet="#b48ead", texte_bouton="#2e3440", console="#272c36",
        grille="#434c5e"),
    "clair": dict(
        fond="#f3efe6", panneau="#faf8f3", champ="#ffffff", bord="#d6cfbf",
        texte="#3b3a36", doux="#7c766a", accent="#4f7ea8", accent2="#6c8fb3",
        vert="#5f8f4e", rouge="#b4534f", orange="#c07a45", jaune="#a8862f",
        violet="#8a6a9a", texte_bouton="#ffffff", console="#2f3136",
        grille="#e4ded1"),
}

POLICE = ("TkDefaultFont", 10)


def appliquer(racine, nom="sombre"):
    P = PALETTES.get(nom, PALETTES["sombre"])
    s = ttk.Style(racine)
    s.theme_use("clam")
    racine.configure(bg=P["fond"])

    s.configure(".", background=P["fond"], foreground=P["texte"], font=POLICE,
                bordercolor=P["bord"], lightcolor=P["fond"], darkcolor=P["fond"],
                troughcolor=P["panneau"], focuscolor=P["accent"],
                selectbackground=P["accent"], selectforeground=P["texte_bouton"],
                fieldbackground=P["champ"], insertcolor=P["texte"])
    s.configure("TFrame", background=P["fond"])
    s.configure("Carte.TFrame", background=P["panneau"], relief="flat")
    s.configure("TLabel", background=P["fond"], foreground=P["texte"])
    s.configure("Carte.TLabel", background=P["panneau"], foreground=P["doux"])
    s.configure("Valeur.TLabel", background=P["panneau"], foreground=P["accent"],
                font=("TkDefaultFont", 17, "bold"))
    s.configure("Petit.TLabel", foreground=P["doux"], font=("TkDefaultFont", 9))
    s.configure("Titre.TLabel", font=("TkDefaultFont", 11, "bold"))
    s.configure("TLabelframe", background=P["fond"], bordercolor=P["bord"],
                relief="solid", borderwidth=1)
    s.configure("TLabelframe.Label", background=P["fond"], foreground=P["accent"],
                font=("TkDefaultFont", 10, "bold"))

    # onglets
    s.configure("TNotebook", background=P["fond"], borderwidth=0, tabmargins=(6, 6, 6, 0))
    s.configure("TNotebook.Tab", background=P["panneau"], foreground=P["doux"],
                padding=(16, 6), borderwidth=0)
    s.map("TNotebook.Tab", background=[("selected", P["champ"])],
          foreground=[("selected", P["accent"])])

    # boutons
    s.configure("TButton", background=P["champ"], foreground=P["texte"],
                bordercolor=P["bord"], padding=(10, 4), relief="flat")
    s.map("TButton", background=[("disabled", P["panneau"]), ("active", P["bord"])],
          foreground=[("disabled", P["doux"])])
    for nom_style, coul in (("Go", "vert"), ("Danger", "rouge"), ("Accent", "accent")):
        s.configure(f"{nom_style}.TButton", background=P[coul], foreground=P["texte_bouton"],
                    font=("TkDefaultFont", 11, "bold"), padding=(12, 6))
        s.map(f"{nom_style}.TButton",
              background=[("disabled", P["panneau"]), ("active", P[coul])],
              foreground=[("disabled", P["doux"])])

    # champs
    s.configure("TEntry", fieldbackground=P["champ"], foreground=P["texte"],
                bordercolor=P["bord"], lightcolor=P["champ"], padding=3)
    s.map("TEntry", bordercolor=[("focus", P["accent"])])
    s.configure("TCombobox", fieldbackground=P["champ"], background=P["champ"],
                foreground=P["texte"], arrowcolor=P["accent"], bordercolor=P["bord"])
    s.map("TCombobox", fieldbackground=[("readonly", P["champ"]), ("disabled", P["panneau"])],
          foreground=[("disabled", P["doux"])])
    racine.option_add("*TCombobox*Listbox.background", P["champ"])
    racine.option_add("*TCombobox*Listbox.foreground", P["texte"])
    racine.option_add("*TCombobox*Listbox.selectBackground", P["accent"])
    racine.option_add("*TCombobox*Listbox.selectForeground", P["texte_bouton"])
    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(w, background=P["fond"], foreground=P["texte"],
                    indicatorbackground=P["champ"], indicatorforeground=P["texte_bouton"],
                    upperbordercolor=P["bord"], lowerbordercolor=P["bord"])
        s.map(w, indicatorbackground=[("selected", P["accent"])],
              background=[("active", P["fond"])])

    s.configure("Vertical.TScrollbar", background=P["panneau"], troughcolor=P["fond"],
                arrowcolor=P["doux"], bordercolor=P["fond"])
    s.configure("TPanedwindow", background=P["bord"])
    s.configure("TSeparator", background=P["bord"])
    return P


def styler_figure(fig, axes, P):
    """Couleurs des courbes matplotlib accordées au thème."""
    fig.set_facecolor(P["fond"])
    for a in axes:
        a.set_facecolor(P["panneau"])
        a.tick_params(colors=P["doux"], labelsize=9)
        a.xaxis.label.set_color(P["doux"])
        a.yaxis.label.set_color(P["doux"])
        a.grid(True, color=P["grille"], lw=0.8)
        for bord in a.spines.values():
            bord.set_color(P["bord"])


def couleurs_courbes(P):
    return {"pression": P["orange"], "debit": P["accent"], "cmd": P["accent2"],
            "eps": P["vert"], "cible": P["doux"], "limite": P["rouge"]}
