import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# pb affichage WSL
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'

#arg
args_lower = [arg.lower() for arg in sys.argv]
is_pyocto = "pyocto" in args_lower

var = 'c'
for arg in args_lower[1:]:
    if arg in ['a', 'b', 'c']:
        var = arg
        break

if var == 'a':
    DOSSIER = "seisbenchA"
elif var == 'b':
    DOSSIER = "seisbenchB"
else:
    DOSSIER = "seisbenchC"

os.makedirs(f"../images/{DOSSIER}", exist_ok=True)

#configuration selon arg "pyocto"
if is_pyocto:
    EVENTS_CSV = f"../data/{DOSSIER}/results_pyocto/catalogue_evenements.csv"
    OUTPUT_PLOT = f"../images/{DOSSIER}/distribution_journaliere_pyocto.png"
    time_col = "time"
    titre = "Distribution journalière des événements avec PyOcto"
else:
    var = 'c'
    EVENTS_CSV = f"../data/{DOSSIER}/seisbench_nouv/catalogue_vt_detectes_evenements_valides.csv"
    OUTPUT_PLOT = f"../images/{DOSSIER}/distribution_journaliere_vt.png"
    time_col = "time_debut"
    titre = "Distribution journalière des événements VT sans PyOcto"


if not os.path.exists(EVENTS_CSV):
    if is_pyocto:
        print(f"Le catalogue PyOcto n'est pas encore généré ({EVENTS_CSV})")
        sys.exit(0)
    else:
        print(f"Erreur : Le fichier {EVENTS_CSV} est introuvable.")
        sys.exit(1)


df = pd.read_csv(EVENTS_CSV)
if df.empty:
    print("Le catalogue d'événements est vide.")
    sys.exit(0)

#conversion date et jour
try:
    df["time_dt"] = pd.to_datetime(df[time_col], format="ISO8601")
except ValueError:
    df["time_dt"] = pd.to_datetime(df[time_col])
    
df.set_index("time_dt", inplace=True)
counts_daily = df.resample("D").size()

#style graph (agrandrir 10 et 4.5 si trop de donnees)
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)

#barres
ax.bar(counts_daily.index, counts_daily.values, color="indianred", edgecolor="white", linewidth=0.5, width=1.0, align="center")

if not counts_daily.empty:
    ax.set_xlim(counts_daily.index.min(), counts_daily.index.max())
    ax.set_ylim(0, max(counts_daily.values.max() * 1.05, 10))

# titres + labels
ax.set_title(titre, fontsize=14, fontweight='bold', pad=15, color='#333333')
ax.set_ylabel("Nombre d'événements", fontsize=11, color='#333333')

#format des mois
month_initials = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: month_initials[mdates.num2date(x).month - 1]))
ax.xaxis.set_minor_locator(mdates.DayLocator(bymonthday=[10, 20]))


#annee
for yr in counts_daily.index.year.unique():
    sub_df = counts_daily[counts_daily.index.year == yr]
    if not sub_df.empty:
        mid_date = sub_df.index[len(sub_df) // 2]
        #decalage texte
        ax.text(mid_date, -0.12, str(yr), 
                transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=12, fontweight="bold", color='#333333')

#cadre
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#cccccc')
ax.spines['bottom'].set_color('#333333')

#grille horizontale
ax.grid(axis='y', linestyle='--', alpha=0.5, color='#cccccc')

plt.tight_layout()
plt.savefig(OUTPUT_PLOT, bbox_inches='tight')
print(f"Graphique mis à jour sauvegardé : {OUTPUT_PLOT}")