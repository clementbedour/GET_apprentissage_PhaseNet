import os
import obspy
import glob


# Variables d'environnement pour snuffler (sur WSL y'a des problèmes)
os.environ['LD_LIBRARY_PATH'] = os.environ.get('CONDA_PREFIX', '') + '/lib:' + os.environ.get('LD_LIBRARY_PATH', '')
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_XCB_GL_INTEGRATION'] = 'none'
os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/home/guiga/miniconda3/envs/phasenet/plugins/platforms'


# Paramètres
DAY = 51
YEAR = 2014
STAT = "SAM" # Change ici pour tester IA2 ou LAM
DATA_DIR = f"../data/2014/MQ/{STAT}" 

# Trouver un fichier pour ce jour
files = glob.glob(os.path.join(DATA_DIR, f"*{YEAR}*{DAY:03d}*"))

if files:
    st = obspy.read(files[0])
    st.detrend("linear")
    st.filter("bandpass", freqmin=3.0, freqmax=15.0)
    
    # On affiche les 10 premières minutes de la journée
    st.trim(starttime=st[0].stats.starttime, endtime=st[0].stats.starttime + 600)
    st.plot(equal_scale=False)
else:
    print(f"Aucun fichier trouvé pour {STAT} le jour {DAY}")