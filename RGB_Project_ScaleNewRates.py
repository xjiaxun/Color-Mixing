import numpy as np


def scale_rates(old_rates, delta_rates):

    old_rates = np.array(old_rates)
    delta_rates = np.array(delta_rates)

    # if old rates is already non-positive, and the delta is non-positive
    # ignore the delta, cause the new rates cannot go outside the range <0
    for i in range(4):
        if old_rates[i] <= 0 and delta_rates[i] <= 0:
            delta_rates[i] = 0

    # rates plus delta with zeroing if out of range
    new_rates_before_scale = old_rates + delta_rates

    # find the index of the minimum new rates before scale
    idx_min = np.argmin(new_rates_before_scale)
    min_rate = new_rates_before_scale[idx_min]

    # if the minimum new rates before scale is negative, then scale down delta
    # such that the minimum new rates before scale does not go below limit, 0
    if min_rate < 0:
        rate_scale = delta_rates[idx_min]/old_rates[idx_min]
        for i in range(4):
            delta_rates[i] /= abs(rate_scale)

    # rates plut scaled delta
    new_rates_after_scale = old_rates + delta_rates

    # scale the final rates to the range 0, 150
    #new_rates_final = np.interp(new_rates_after_scale,(0,max(new_rates_after_scale)), (0, 150))

    # normalize the final rates then scale to sum rates = 600
    new_rates_final = 600/(sum(new_rates_after_scale))*(new_rates_after_scale)

    return new_rates_final





# ============= Test =========================
if __name__ == "__main__":
    import random


    # old rates
    rates = np.array([150,0,0,0])
    print("old rates:" + str(rates))

    # delta calcualted from gradient descent
    delta_rates = np.zeros(4)
    for i in range(4):
        delta_rates[i] = random.uniform(-500,500)
    print("delta rates: " + str(delta_rates))

    # if old rates is already non-positive, and the delta is non-positive
    # ignore the delta, cause the new rates cannot go outside the range <0
    for i in range(4):
        if rates[i] <= 0 and delta_rates[i] <= 0:
            delta_rates[i] = 0

    print(delta_rates)

    # rates plus delta with zeroing if out of range
    rates_original = rates + delta_rates
    print("original: " + str(rates_original))

    # find the index of the minimum new rates before scale
    idx_min = np.argmin(rates_original)
    min_rate = rates_original[idx_min]

    # if the minimum new rates before scale is negative, then scale down delta
    # such that the minimum new rates before scale does not go below limit, 0
    if min_rate < 0:
        rate_scale = delta_rates[idx_min]/rates[idx_min]
        for i in range(4):
             delta_rates[i] /= abs(rate_scale)

    print("scaled delta: " + str(delta_rates))

    # rates plut scaled delta
    rates_scaled_delta = rates + delta_rates
    print("rates with scaled delta: " + str(rates_scaled_delta))

    # scale the final rates to the range 0, 150
    rates_scaled_final = np.interp(rates_scaled_delta,(0,max(rates_scaled_delta)), (0, 150))
    print("final rates: " + str(rates_scaled_final))



    print("function return: " + str(scale_rates(rates, delta_rates)))