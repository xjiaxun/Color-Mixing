import numpy as np

def cal_cost(target_rgb, rgb):
    # mean squared error between the measured rgb and the target rgb
    cost = (np.square(np.asarray(target_rgb) - np.asarray(rgb))).mean(axis=None)
    return cost

def gradient_descent_4steps(target_rgb,rgb,flowrates,prev_cost,prev_flowrates,learning_rate=0.01):
    ''' Move 4 scout steps in each flowrate, calculate a 4 entries gradient array.
        target_rgb: target rgb
        rgb: measured rgb of the scout step
        flowrates: flowrate of the scout step
        prev_cost: cost of the previous real step
        prev_flowrates: flowrate of the previous real step
        learning rate: learning rate of gradient descent
        step_size: the difference in flowrates between the next and previous real steps
    '''

    # calculate MSE cost between the scout step measured rgb and the target rgb
    cost = cal_cost(target_rgb, rgb)

    # scout step flowrate - real step flowrate 
    denom = flowrates - prev_flowrates

    # initialize a 4-element gradient array
    gradient = np.array([0.0]*4)

    # calculate gradient for each gradient
    for i in range(len(denom)):
        # if denominator is zero, i.e. flow rate did not change, step_size should be 0
        if denom[i] == 0:
            gradient[i] = 0
        else:
            gradient[i]=(cost-prev_cost)/denom[i]
    
    step_size = - learning_rate*gradient

    return step_size


if __name__ == '__main__':
    target_rgb = np.array([ 0,0, 200])
    prev_rgb = np.array([166, 174, 176])
    prev_flowrates = np.array([21.3, 65.,         65.,         50.])
    prev_cost = cal_cost(target_rgb,prev_rgb)
    flowrates = np.array([21.3,  67,  65, 50.])
    rgb = np.array([160, 173, 176])

    step = gradient_descent_4steps(target_rgb,rgb,flowrates,prev_cost,prev_flowrates,0.01)[0]
    print(step)
    next_flowrates = flowrates + gradient_descent_4steps(target_rgb,rgb,flowrates,prev_cost,prev_flowrates,0.01)[0]
    print(next_flowrates)