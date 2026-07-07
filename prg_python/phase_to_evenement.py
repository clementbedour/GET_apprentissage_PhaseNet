import os
import re
import glob
from datetime import datetime, timedelta, timezone

PATH_PHASE = "../data/phase_vt/"
PATH_EVENEMENT = "../data/phase_evenement"
PATH_DATA = "../data/2014/MQ/"
PATH_CATALOG = "../data/phase_evenement_doc/2014.CATALOG.txt"
CHANNEL_PATTERN = '*H*'
title = ""
os.makedirs(PATH_EVENEMENT, exist_ok=True)


def to_decimal(coord_str, is_longitude=False):
    neg = coord_str.startswith('-')
    coord_str = coord_str.lstrip('-')
    if '-' in coord_str:
        deg, minutes = map(float, coord_str.split('-'))
        val = deg + minutes / 60.0
    else:
        val = float(coord_str)
    if neg:
        val = -val
    if is_longitude and val > 0:
        val = -val
    return val


def event(content):
    """Renvoie (ligne_event, matched, event_id). Ligne vide si pas de correspondance."""
    event_id = next((m.group(0) for l in content if (m := re.search(r'\S+\.mq0', l))), None)
    if not event_id:
        return "", False, None

    try:
        with open(PATH_CATALOG, 'r') as f:
            catalog_parts = next((p for l in f if (p := l.split()) and p[-1] == event_id), None)
    except FileNotFoundError:
        raise FileNotFoundError(f"Catalogue introuvable : {PATH_CATALOG}")

    if not catalog_parts:
        return "", False, event_id

    raw_date, raw_time, raw_sec, raw_lat, raw_lon, raw_depth = catalog_parts[0:6]
    raw_mag = catalog_parts[7]

    date_fmt = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    try:
        time_fmt = f"{raw_time[0:2]}:{raw_time[2:4]}:{float(raw_sec):07.4f}"
    except ValueError:
        time_fmt = f"{raw_time[0:2]}:{raw_time[2:4]}:{raw_sec}"

    try:
        lat, lon = to_decimal(raw_lat), to_decimal(raw_lon, is_longitude=True)
        depth, mag = float(raw_depth), float(raw_mag)
    except Exception as e:
        raise ValueError(f"Erreur de conversion catalogue : {e}")

    eid = event_id.replace('.mq0', '')
    line = f"event: {date_fmt} {time_fmt}  0 {eid}  {lat:.4f}  {lon:.4f}  {depth:.2f}  {mag:.2f}  None  M={mag:.2f}  None\n"
    return line, True, event_id


def parse_phase_file(filepath):
    picks = []
    with open(filepath, 'r') as f:
        for line in f:
            if not line[0:3].strip():
                continue
            station = line[0:3].strip()
            raw_p = line[9:24].strip().replace(" ", "0")
            try:
                p_dt = datetime.strptime(raw_p, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
            except ValueError:
                print(f" -> Problème format P sur '{raw_p}' dans {os.path.basename(filepath)}")
                continue
            picks.append({'station': station, 'phase': 'P', 'datetime': p_dt})

            s_time = line[31:36].strip()
            if s_time:
                try:
                    s_sec, p_sec = float(s_time), float(line[19:24].strip())
                    delta = timedelta(seconds=s_sec, minutes=1 if p_sec > s_sec else 0)
                    s_dt = p_dt.replace(second=0, microsecond=0) + delta
                    picks.append({'station': station, 'phase': 'S', 'datetime': s_dt})
                except ValueError:
                    print(f" -> Problème format S sur une ligne de {os.path.basename(filepath)}")
    return picks


def pattern(picks, g):
    year, jday = picks[0]['datetime'].strftime('%Y'), picks[0]['datetime'].strftime('%j')
    stations = list(dict.fromkeys(p['station'] for p in picks))
    chosen = {}

    for station in stations:
        matches = glob.glob(os.path.join(PATH_DATA, station, f"*.{station}.*.{CHANNEL_PATTERN}.D.{year}.{jday}.mseed"))
        st_picks = [p for p in picks if p['station'] == station]

        if not matches:
            for p in st_picks:
                comp = "HHZ" if p['phase'] == 'P' else "HHE"
                chosen[(p['datetime'], station, p['phase'])] = f"MQ.{station}.00.{comp}"
            continue

        net, sta, loc, cha = os.path.basename(matches[0]).split('.')[:4]
        for p in st_picks:
            key = (p['datetime'], station, p['phase'])
            if p['phase'] == 'S':
                code = cha[:-1] + 'E' if cha.endswith('Z') else cha
            else:
                code = cha[:-1] + 'Z' if cha[-1] in 'EN' else cha
            chosen[key] = f"{net}.{sta}.{loc}.{code}"

    lines = sorted(
        ((t, f"phase:  {t.strftime('%Y-%m-%d %H:%M:%S.%f')[:-2]}  0 {code} None None None {ph} None False\n")
        for (t, _, ph), code in chosen.items()),
        key=lambda x: x[0]
    )
    for _, line in lines:
        g.write(line)


def main(filename):
    global title
    with open(filename, 'r') as f:
        content = f.readlines()
    if not content or not content[0].strip():
        raise ValueError("Première ligne vide ou absente.")

    title = "20" + content[0][9:19].replace(" ", "0") + ".txt"
    line, matched, event_id = event(content)

    with open(os.path.join(PATH_EVENEMENT, title), 'w') as g:
        g.write("# Snuffler Markers File Version 0.2\n")
        g.write(line)

    return matched, event_id


if __name__ == "__main__":
    path_NL = os.path.join(PATH_EVENEMENT, "NL.txt")

    if not os.path.exists(PATH_PHASE):
        with open(path_NL, "w") as f:
            f.write(f"Dossier source introuvable : {os.path.abspath(PATH_PHASE)}\n")
        print(f"ERREUR : '{PATH_PHASE}' introuvable.")
    else:
        for fname in os.listdir(PATH_PHASE):
            old = os.path.join(PATH_PHASE, fname)
            if os.path.isdir(old) or fname.startswith("NL"):
                continue
            if re.search(r'[\s\xa0]', fname):
                new = re.sub(r'[\s\xa0]+', '0', fname)
                os.rename(old, os.path.join(PATH_PHASE, new))
                print(f"Renommé : '{fname}' -> '{new}'")

        all_files = sorted(f for f in os.listdir(PATH_PHASE)
                            if os.path.isfile(os.path.join(PATH_PHASE, f)) and not f.startswith("NL"))
        failed, unmatched = [], []

        for fname in all_files:
            filepath = os.path.join(PATH_PHASE, fname)
            try:
                picks = parse_phase_file(filepath)
                if not picks:
                    raise ValueError("Aucun pointé valide trouvé.")

                matched, event_id = main(filepath)
                with open(os.path.join(PATH_EVENEMENT, title), 'a') as g:
                    pattern(picks, g)

                if matched:
                    print(f" -> Réussi : {title}")
                else:
                    unmatched.append((fname, title, event_id))
                    print(f" -> Sans correspondance catalogue (phases écrites) : {title}")
            except Exception as e:
                print(f" -> ÉCHEC : {e}")
                failed.append((fname, str(e)))

        with open(path_NL, "w") as f:
            if not failed and not unmatched:
                f.write("Aucun problème détecté ! Tous les fichiers ont été convertis avec succès.\n")
            else:
                if failed:
                    f.write("Fichiers en échec total :\n")
                    for fname, err in failed:
                        f.write(f"{'-'*40}\nFichier : {fname}\nErreur  : {err}\n")
                if unmatched:
                    f.write("\nFichiers créés (phases écrites) sans correspondance catalogue :\n")
                    for fname, out_title, eid in unmatched:
                        f.write(f"{'-'*40}\nSource : {fname}\nSortie : {out_title}\n")
            print(f"\nRapport : {os.path.abspath(path_NL)}")