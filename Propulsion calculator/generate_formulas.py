import matplotlib.pyplot as plt

plt.rc('text', usetex=False)
plt.rc('mathtext', fontset='cm')

fig = plt.figure(figsize=(8, 3.5), dpi=150)
fig.patch.set_facecolor('#EBEBEB') # Match Tkinter's 'clam' background roughly

formulas = [
    r"Burn Area to Throat Area Ratio ($K_n$) = $\frac{P_1^{(1-n)}}{a \cdot \rho_p \cdot c^*} \times 10^6$",
    r"Thrust Coefficient ($C_F$) = $\sqrt{\frac{2k^2}{k-1} \left(\frac{2}{k+1}\right)^{\frac{k+1}{k-1}} \left[ 1 - \left(\frac{P_2}{P_1}\right)^{\frac{k-1}{k}} \right] }$",
    r"Throat Area ($Area_{throat}$) = $\frac{F}{C_F \cdot P_1}$",
    r"Required Core Length ($L$) = $\frac{Area_{throat} \cdot K_n}{\pi \cdot d}$",
    r"Expansion Ratio ($\epsilon$) = $\left(\frac{k+1}{2}\right)^{\frac{1}{k-1}} \left(\frac{P_2}{P_1}\right)^{\frac{1}{k}} \sqrt{\frac{k+1}{k-1} \left[ 1 - \left(\frac{P_2}{P_1}\right)^{\frac{k-1}{k}} \right] }^{-1}$"
]

for i, formula in enumerate(formulas):
    plt.text(0.02, 0.9 - i*0.2, formula, fontsize=12, va='top')

plt.axis('off')
plt.tight_layout()
plt.savefig('formulas.png', bbox_inches='tight', pad_inches=0.1, facecolor=fig.get_facecolor(), transparent=True)
plt.close()
