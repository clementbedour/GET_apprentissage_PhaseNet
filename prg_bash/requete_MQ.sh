#!/bin/bash

# V Clouard dec. 2022 - version corrigée
#
# Téléchargement des données de la station PCM (réseau MQ, Martinique)
# pour l'année 2014, du jour 51 au jour 151 inclus.

# --- Paramètres ---
WSURL=https://ws.ipgp.fr/fdsnws
#WSURL=https://ws.resif.fr/fdsnws

racine=/mnt/c/Users/Bedour/Desktop/GET/data/
year=2014
network=MQ
station=PCM
channel=EHZ
location=91

jour_debut=51
jour_fin=151

temps_0=T00:00:00
temps_24=T23:59:59

# Détection GNU date (Linux) vs BSD date (macOS), pour ne plus dépendre
# de l'outil externe "dateadd" (dateutils) qui n'est pas installé par défaut.
if [[ "$(uname)" == "Darwin" ]]; then
    OS_TYPE="bsd"
else
    OS_TYPE="gnu"
fi

# Convertit un numéro de jour de l'année (1-366) en date calendaire YYYY-MM-DD
day_of_year_to_date() {
    local y=$1
    local doy=$2
    if [[ "$OS_TYPE" == "bsd" ]]; then
        local doy_pad
        printf -v doy_pad '%03d' "$doy"
        date -j -f "%Y-%j" "${y}-${doy_pad}" +%Y-%m-%d
    else
        date -d "${y}-01-01 +$((doy-1)) days" +%Y-%m-%d
    fi
}

outdir="$racine/$year/$network/$station"
mkdir -p "$outdir"

for (( jour=jour_debut; jour<=jour_fin; jour++ )); do
    date=$(day_of_year_to_date "$year" "$jour")
    jour_pad=$(printf '%03d' "$jour")

    debut="${date}${temps_0}"
    fin="${date}${temps_24}"

    file_name="$outdir/${network}.${station}.${location}.${channel}.D.${year}.${jour_pad}.mseed"

    echo "Jour $jour_pad ($date) -> $file_name"

    # NB: on filtre avec location=* (et non $location) dans la requête,
    # pour ne pas risquer un fichier vide si le code de localisation
    # renseigné ci-dessus n'est pas le bon. Seul le NOM de fichier utilise $location.
    curl --output "$file_name" \
        "$WSURL/dataselect/1/query?network=${network}&station=${station}&location=*&channel=${channel}&starttime=${debut}&endtime=${fin}&nodata=404"
done

echo "Terminé."