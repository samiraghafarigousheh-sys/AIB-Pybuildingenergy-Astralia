from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
R=Path(__file__).resolve().parent
F=R/'figures';F.mkdir(exist_ok=True)
d=pd.read_csv(R/'revision_results/comparison.csv')
m=pd.read_csv(R/'revision_results/monthly.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
blue='#28658A';orange='#C77538'
def save(fig,name):
 for ext in ['png','pdf','svg']:fig.savefig(F/(name+'.'+ext),dpi=300,bbox_inches='tight',facecolor='white')
 plt.close(fig)
def val(c,col='iso_kWh',metric='Total'):return d[(d['case']==c)&(d.metric==metric)][col].iloc[0]
fig,ax=plt.subplots(figsize=(8,3.0));ax.set(xlim=(0,10),ylim=(0,5));ax.axis('off')
boxes=[(.2,2.5,2.6,1.9,'Stage 1\nImplementation repairs\n\nOriginal → repaired\nInfiltration ablation'),(3.7,2.5,2.6,1.9,'Stage 2\nPhysical methods\n\nAngular × convection\nNeither / each / both'),(7.2,2.5,2.6,1.9,'Stage 3\nAustralian inputs\n\nLeakage × construction\nReference / each / both')]
for x,y,w,h,t in boxes:
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08',fc='#EEF3F6',ec=blue,lw=1));ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=10)
for x1,x2 in [(2.9,3.55),(6.4,7.05)]:ax.annotate('',(x2,3.45),(x1,3.45),arrowprops={'arrowstyle':'->','color':blue,'lw':1.6})
ax.text(3.3,1.75,'Stages 1–2: common EnergyPlus reference',ha='center',fontsize=10)
ax.text(8.5,1.65,'Stage 3: matched reference\nfor each physical scenario',ha='center',fontsize=9)
ax.text(5,.5,'EnergyPlus algorithms unchanged • Compare annual demand and hourly error\nSensitivity checks: leakage magnitude and constant versus weather-dependent airflow',ha='center',fontsize=10,linespacing=1.7)
save(fig,'fig1_comparison_design')
fig,axs=plt.subplots(1,2,figsize=(8,3.35),gridspec_kw={'width_ratios':[1,1.6]})
cs=['original','repaired'];a=axs[0];a.bar([0,1],[val(c) for c in cs],color=blue,width=.55);a.axhline(val('repaired','ep_kWh'),color=orange,lw=1.6,ls='--');a.set_xticks([0,1],['Original','Repaired']);a.set_ylabel('Annual sensible demand (kWh)');a.set_ylim(0,2800);a.set_title('(a) Implementation repairs',loc='left',fontsize=11)
for i,c in enumerate(cs):a.text(i,val(c)+60,f'{val(c):.2f}',ha='center',fontsize=9)
a.text(.95,460,'EnergyPlus 157.33',ha='right',color=orange,fontsize=9)
a=axs[1];cs=['both','au_leakage_only','au_construction_only','au_combined'];x=np.arange(4)
a.bar(x-.18,[val(c) for c in cs],width=.36,color=blue,label='pyBuildingEnergy');a.bar(x+.18,[val(c,'ep_kWh') for c in cs],width=.36,color=orange,label='EnergyPlus')
a.set_xticks(x,['Reference','Leakage\nonly','Construction\nonly','Combined']);a.set_ylim(0,205);a.set_title('(b) Australian input scenarios',loc='left',fontsize=11);a.legend(frameon=False,fontsize=9,ncol=2,loc='upper center');a.set_ylabel('Annual sensible demand (kWh)')
for i,c in enumerate(cs):
 for off,col in [(-.18,'iso_kWh'),(.18,'ep_kWh')]:a.text(i+off,val(c,col)+3,f'{val(c,col):.1f}',ha='center',fontsize=8)
fig.tight_layout(w_pad=2);save(fig,'fig2_annual_demand')
fig,axs=plt.subplots(1,2,figsize=(8,3.1));cs=['repaired','angular_only','convection_only','both'];labs=['Fixed','Angular','Convection','Both']
for a,col,title,ylabel in [(axs[0],'bias_pct','(a) Annual total bias','Bias relative to EnergyPlus (%)'),(axs[1],'RMSE_W','(b) Hourly total-load error','RMSE (W)')]:
 values=[val(c,col) for c in cs];a.bar(np.arange(4),values,color=blue,width=.6);a.set_xticks(np.arange(4),labs,rotation=15);a.set_title(title,loc='left',fontsize=11);a.set_ylabel(ylabel)
 for i,v in enumerate(values):a.text(i,v+(.4 if col=='bias_pct' else .2),f'{v:.2f}',ha='center',va='bottom',fontsize=9)
 if col=='bias_pct':a.set_ylim(-20,0)
 else:a.set_ylim(0,18)
fig.tight_layout(w_pad=2);save(fig,'fig3_physical_methods')
fig,ax=plt.subplots(figsize=(8,2.8));z=m[(m['case']=='repaired')&(m.metric=='Heating')].sort_values('month');x=np.arange(12)
ax.axvspan(4.5,7.5,color='#EDF1F4',label='June–August');ax.plot(x,z.iso_kWh,'o-',color=blue,label='Repaired pyBuildingEnergy',ms=4);ax.plot(x,z.ep_kWh,'s-',color=orange,label='EnergyPlus',ms=4);ax.set_xticks(x,['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']);ax.set_ylabel('Monthly heating demand (kWh)');ax.set_ylim(0,40);ax.legend(frameon=False,ncol=3,fontsize=9,loc='upper left');fig.tight_layout();save(fig,'fig4_monthly_heating')
