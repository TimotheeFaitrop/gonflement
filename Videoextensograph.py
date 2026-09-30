import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from glob import glob
import csv


date = '2025_04_28'
sample = 'SC_37_40_4DFIXNR'
data_folder = f'./{date}/{sample}/Essai_3/'


t,P,Vf,Mf = [],[],[],[]

t_label = '0'
P_label = '0'
Vf_label = '0'
Mf_label = '0'

with open(data_folder+'data_ali_00003.txt') as csv_file:
    line=0
    csv_reader=csv.reader(csv_file, delimiter = ',')
    for row in csv_reader:
        if line==0:
            t_label = row[0]
            P_label = row[1]
            Vf_label = row[2]
            Mf_label = row[3]
            line+=1
        else:
            t.append(row[0])
            P.append(row[1])
            Vf.append(row[2])
            Mf.append(row[3])

#plt.plot(t,P)
plt.plot(t,Mf)
plt.xlabel(t_label)
plt.ylabel(Mf_label)
plt.yscale('log')
plt.show()
