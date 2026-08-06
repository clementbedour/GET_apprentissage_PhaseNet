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



if len(sys.argv) > 1:
    var = sys.argv[1].lower()
    if var == 'a':
        BASE_OUT = "../data/seisbenchA/seisbench_nouv"
        os.makedirs("../images/seisbenchA", exist_ok=True)
        OUTPUT_PLOT = os.path.join("../images", "distribution_journaliere_vtA.png")
    elif var == 'b':
        BASE_OUT = "../data/seisbenchB/seisbench_nouv"
        os.makedirs("../images/seisbenchB", exist_ok=True)
        OUTPUT_PLOT = os.path.join("../images", "distribution_journaliere_vtB.png")
    else:
        BASE_OUT = "../data/seisbench/seisbench_nouv"
        os.makedirs("../images/seisbench", exist_ok=True)
        OUTPUT_PLOT = os.path.join("../images", "distribution_journaliere_vt.png")
else:
    var = 'c'
    BASE_OUT = "../data/seisbench/seisbench_nouv"

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