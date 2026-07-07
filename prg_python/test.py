import h5py
from obspy import read

#lecture du doc (faudra auto tout les docs)
st = read("../data/mseed/BAM/MQ.BAM.91.EHE.D.2014.051.mseed");
trace = st[0]
print(trace)

#creation d'un fichier sortie
with h5py.File("../data/hdf5/test.hdf5", "w") as f:
    for i, tr in enumerate(st):
        #creation d'un fichier sortie
    
        # stocker les data
        f.create_dataset(f"waveforms/{tr.id}/data", data=tr.data);
        # stocker les méta
        f[f"waveforms/{tr.id}"].attrs["starttime"] = str(tr.stats.starttime);
        f[f"waveforms/{tr.id}"].attrs["sampling_rate"] = tr.stats.sampling_rate;
        f[f"waveforms/{tr.id}"].attrs["station"] = tr.stats.station;
        f[f"waveforms/{tr.id}"].attrs["channel"] = tr.stats.channel;
        f[f"waveforms/{tr.id}"].attrs