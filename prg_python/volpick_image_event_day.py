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
if len(sys.argv) < 3:
    print("Usage: python image_event_day.py <1/2> <LPVT/VT>")
    sys.exit(1)

version = sys.argv[1]
type_event = sys.argv[2].upper()

if version not in ['1', '2']:
    print("Erreur : Le premier argument (version du modèle) doit être '1' ou '2'.")
    sys.exit(1)

if type_event not in ['LPVT', 'VT']:
    print("Erreur : Le deuxième argument (type d'événement) doit être 'LPVT' ou 'VT'.")
    sys.exit(1)

# Répertoire des données et de sortie des images
BASE_OUT = f"../data/volpick/{type_event}"
IMAGE_DIR = f"../images/volpick/{type_event}"
os.makedirs(IMAGE_DIR, exist_ok=True)

OUTPUT_PLOT = os.path.join(IMAGE_DIR, f"distribution_journaliere_{type_event.lower()}_v{version}.png")


# ------------ PARAMÈTRES ------------
EVENTS_CSV = os.path.join(BASE_OUT, "catalogue_vt_detectes_evenements_valides.csv")

if not os.path.exists(EVENTS_CSV):
    print(f"Erreur : Le fichier {EVENTS_CSV} est introuvable.")
    sys.exit(1)


df = pd.read_csv(EVENTS_CSV)
if df.empty:
    print("Le catalogue d'événements est vide.")
    sys.exit(0)

#conversion date et jour
df["time_dt"] = pd.to_datetime(df["time_debut"], format="ISO8601")
df.set_index("time_dt", inplace=True)
counts_daily = df.resample("D").size()

#style graph (agrandrir 10 et 4.5 si trop de donnees)
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)

#barre rouge
ax.bar(counts_daily.index, counts_daily.values, color="red", width=1.0, align="center")

ax.set_xlim(counts_daily.index.min(), counts_daily.index.max())
ax.set_ylim(0, max(counts_daily.values.max() * 1.05, 10))

#format des mois
month_initials = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
ax.xaxis.set_major_locator(mdates.MonthLocator())
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: month_initials[mdates.num2date(x).month - 1]))
ax.xaxis.set_minor_locator(mdates.DayLocator(bymonthday=[10, 20]))


#annee
for yr in counts_daily.index.year.unique():
    sub_df = counts_daily[counts_daily.index.year == yr]
    mid_date = sub_df.index[len(sub_df) // 2]
    
    ax.text(mid_date, -0.08, str(yr), 
            transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=12, fontweight="bold")

#cadre
ax.tick_params(top=True, right=True, which='both', direction='in', length=5)
ax.tick_params(which='minor', length=2.5)
ax.grid(False)

plt.tight_layout()
plt.savefig(OUTPUT_PLOT, bbox_inches='tight')
print(f"Graphique mis à jour sauvegardé : {OUTPUT_PLOT}")