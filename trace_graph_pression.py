import matplotlib.pyplot as plt
import numpy as np
import glob
import time


date = time.strftime("%Y_%m_%d")  #"2025_07_21"
sample= "tests_pression"
path = f'./{date}/{sample}/'
files = glob.glob(path+'*pression*.txt')

for element, i in enumerate(files):
    print(element)
    """data = np.loadtxt(f'./{date}/{sample}/data_pression_{Kp}_{Ki}.txt', delimiter = ',', skiprows = 1)


plt.ion()
plt.figure()
plt.plot(data[:,0], data[:,1], 'k')
plt.grid()
plt.xlabel('t(s)')
plt.ylabel('Pression (Pa)')
"""
