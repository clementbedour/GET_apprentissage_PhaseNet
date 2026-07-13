import os
import random
import numpy as np
import pandas as pd
from pathlib import Path
import obspy
from obspy import UTCDateTime
from obspy.signal.trigger import classic_sta_lta, trigger_onset

# --- CONFIGURATION (Identique à ton script principal) ---
CFG = {
    "mseed_dir"       : "../data/2014/MQ",
    "picks_dir"       : "../data/phase_snuffler",
    "npz_dir"         : "../data/npz_dataset",
    "window_before_s" : 10,
    "window_after_s"  : 50,
}

def load_snuffler_picks():
    # Identique à ta fonction, nécessaire pour identifier les jours "occupés"
    picks = {}
    path = Path(CFG["picks_dir"])
    files = list(path.glob("*")) if path.is_dir() else [path]
    for file_path in files:
        if not file_path.is_file(): continue
        with open(file_path, 'r') as f:
            for line in f:
                if not line.startswith("phase:"): continue
                parts = line.strip().split()
                if len(parts) < 9: continue
                nslc = parts[4].split('.')
                pick_time = UTCDateTime(f"{parts[1]} {parts[2]}")
                picks.setdefault((nslc[0], nslc[1], pick_time.date), {})[parts[8].upper()] = pick_time
    return picks

def _stream_to_3c_array(st, target_npts):
    unique = {}
    for tr in st:
        comp = tr.stats.channel[-1].upper()
        if comp not in unique or tr.stats.npts > unique[comp].stats.npts:
            unique[comp] = tr
    if not unique: return None
    data = np.zeros((3, target_npts), dtype=np.float32)
    for i, comp in enumerate(['Z', 'N', 'E']):
        if comp in unique:
            arr = unique[comp].data.astype(np.float32)
            n = min(len(arr), target_npts)
            data[i, :n] = arr[:n]
    return data

def generate_noise():
    print("[INFO] Démarrage de la génération de bruit uniquement...")
    npz_dir = Path(CFG["npz_dir"])
    mseed_dir = Path(CFG["mseed_dir"])
    (npz_dir / "noise").mkdir(parents=True, exist_ok=True)

    snuffler_picks = load_snuffler_picks()
    days_with_picks = {day for (_, _, day) in snuffler_picks}

    print("  Indexation MiniSEED...")
    files_by_day = {}
    for fp in mseed_dir.rglob("*"):
        if not fp.is_file(): continue
        try:
            for tr in obspy.read(str(fp), headonly=True):
                files_by_day.setdefault(tr.stats.starttime.date, set()).add(fp)
        except: continue

    noise_days = [d for d in files_by_day if d not in days_with_picks]
    # Génère 200 exemples de bruit ou moins selon la disponibilité
    target_noise =  15
    noise_count = 0

    for day in random.sample(noise_days, min(len(noise_days), target_noise * 2)):
        if noise_count >= target_noise: break
        
        t0 = UTCDateTime(day) + random.randint(3600, 72000)
        t_end = t0 + CFG["window_before_s"] + CFG["window_after_s"]
        
        st = obspy.Stream()
        for fp in files_by_day[day]:
            try: st += obspy.read(str(fp), starttime=t0, endtime=t_end)
            except: continue
        if not st: continue
        st.merge(method=1, fill_value=0)
        
        stations = list({(tr.stats.network, tr.stats.station) for tr in st})
        if not stations: continue
        net_n, sta_n = random.choice(stations)
        st_sta = st.select(network=net_n, station=sta_n)
        
        # Filtre STA/LTA
        try:
            tr_z = st_sta.select(component="Z")[0]
            cft = classic_sta_lta(tr_z.data, int(1.0 * tr_z.stats.sampling_rate), int(10.0 * tr_z.stats.sampling_rate))
            if len(trigger_onset(cft, 3.0, 1.5)) > 0: continue
        except: continue

        # Sauvegarde
        data = _stream_to_3c_array(st_sta, int((CFG["window_before_s"] + CFG["window_after_s"]) * st_sta[0].stats.sampling_rate))
        if data is None: continue
        
        np.savez(npz_dir / "noise" / f"{net_n}_{sta_n}_{day.strftime('%Y%m%d')}_noise_{noise_count}.npz", 
                data=data, p_idx=np.array([-1]), s_idx=np.array([-1]), sr=np.array([st_sta[0].stats.sampling_rate]))
        noise_count += 1
        print(f"  -> Bruit généré : {noise_count}/{target_noise}", end='\r')

    print(f"\n[INFO] Terminé. {noise_count} fichiers de bruit ajoutés dans {npz_dir / 'noise'}")

if __name__ == "__main__":
    generate_noise()