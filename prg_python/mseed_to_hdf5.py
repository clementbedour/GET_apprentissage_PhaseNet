import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API")

import h5py
from obspy import read



#lecture du doc (faudra auto tout les docs)
PATH_DATA = "../data/2014/MQ/BAM/"
PATH_HDF5 = "../data/hdf5/"


#lecture du doc (faudra auto tout les docs)
PATH_FILE = "MQ.BAM.91.EHZ.D.2014.051.mseed"
NAME_FILE = PATH_FILE.strip('mseed') + "hdf5"



stream = read(PATH_DATA + PATH_FILE)

#creation d'un fichier sortie en hdf5
with h5py.File(PATH_HDF5 + NAME_FILE, "w") as f:
    for i, tr in enumerate(stream):
        # Chemin du dataset unique pour cette trace
        dataset_path = f"waveforms/{tr.id}/data"
        # Stocker les data
        f.create_dataset(dataset_path, data=tr.data)