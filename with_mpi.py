# -*- coding: utf-8 -*-
"""with-mpi.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1qoGKBSb6sTXbZBnQ5-XPQIadcvhfXZad
"""

from mpi4py import MPI
import numpy as np
import pandas as pd
from scipy.integrate import odeint
import matplotlib.pyplot as plt
import time

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

class Life_real:
    def __init__(self, investment_fraction, interest_rate_proc=5, income=10000, spending=7000, tax_rate=0.19,
                 pension=500, starting_age=18, retirement_age=67, pay_raise=250, life_inflation=50, inflation_proc=4):
        self.investment_fraction = investment_fraction
        self.interest_rate_proc = interest_rate_proc
        self.income = income
        self.spending = spending
        self.tax_rate = tax_rate
        self.pension = pension
        self.starting_age = starting_age
        self.retirement_age = retirement_age
        self.pay_raise = pay_raise
        self.life_inflation = life_inflation
        self.inflation_proc = inflation_proc

    def earn(self, t):
        if t < self.starting_age:
            return 0
        elif self.starting_age <= t < self.retirement_age:
            return 12 * (self.income + self.pay_raise * (t - self.starting_age))
        else:
            return 12 * self.pension

    def spend(self, t):
        return 12 * (self.spending + self.life_inflation * (t - self.starting_age))

    def pay_taxes(self, t):
        return self.earn(t) * self.tax_rate

def live_with_investing(x, t, you):
    balance = you.earn(t) - you.spend(t) - you.pay_taxes(t)
    x1 = balance * (1 - you.investment_fraction) - np.log(1 + 0.01 * you.inflation_proc) * x[0]
    if t < you.retirement_age:
        x2 = np.log(1 + 0.01 * you.interest_rate_proc) * x[1] + you.investment_fraction * balance
    else:
        x2 = np.log(1 + 0.01 * you.interest_rate_proc) * x[1]
    x2 -= np.log(1 + 0.01 * you.inflation_proc) * x[1]
    return [x1, x2]

def live_without_investing(x, t, you):
    balance = you.earn(t) - you.spend(t) - you.pay_taxes(t)
    return balance - np.log(1 + 0.01 * you.inflation_proc) * x

def simulate(you):
    t0 = np.linspace(0, you.starting_age - 1, num=you.starting_age)
    t1 = np.linspace(you.starting_age, you.retirement_age - 1, num=(you.retirement_age - you.starting_age))
    t2 = np.linspace(you.retirement_age, 100, num=(100 - you.retirement_age))

    # non-investor
    x1_0 = np.zeros((t0.shape[0], 1))
    x1_1 = odeint(live_without_investing, 0, t1, args=(you,))
    x1_2 = odeint(live_without_investing, x1_1[-1], t2, args=(you,))

    # investor
    x2_0 = np.zeros((t0.shape[0], 2))
    x2_1 = odeint(live_with_investing, [0, 0], t1, args=(you,))
    x2_2 = odeint(live_with_investing, x2_1[-1], t2, args=(you,))

    df0 = pd.DataFrame({'time': t0, 'wallet (non-investor)': x1_0[:, 0], 'wallet (investor)': x2_0[:, 0], 'investment bucket (investor)': x2_0[:, 1]})
    df1 = pd.DataFrame({'time': t1, 'wallet (non-investor)': x1_1[:, 0], 'wallet (investor)': x2_1[:, 0], 'investment bucket (investor)': x2_1[:, 1]})
    df2 = pd.DataFrame({'time': t2, 'wallet (non-investor)': x1_2[:, 0], 'wallet (investor)': x2_2[:, 0], 'investment bucket (investor)': x2_2[:, 1]})
    return pd.concat([df0, df1, df2])

mu_itr = 5
sig_itr = 2
mu_inf = 4
sig_inf = 2

if rank == 0:
    start_time = time.time()

MC_times = 2000
local_MC_times = MC_times // size

dfs = {}
for _ in range(local_MC_times):
    beta = np.random.beta(2, 5)
    interest_rate_proc = sig_itr * np.random.randn() + mu_itr
    inflation_proc = sig_inf * np.random.randn() + mu_inf

    instance = Life_real(investment_fraction=beta, interest_rate_proc=interest_rate_proc, inflation_proc=inflation_proc)
    tmp = simulate(instance)
    tmp['total net asssets (investor)'] = tmp['wallet (investor)'] + tmp['investment bucket (investor)']
    tmp = tmp.drop(columns=['wallet (non-investor)', 'wallet (investor)', 'investment bucket (investor)'])
    dfs[instance.investment_fraction] = tmp

all_dfs = comm.gather(dfs, root=0)

if rank == 0:
    combined_dfs = {}
    for d in all_dfs:
        combined_dfs.update(d)
    end_time = time.time()
    print(end_time - start_time, "s")