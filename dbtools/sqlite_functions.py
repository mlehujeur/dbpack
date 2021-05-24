def substring(X, i, j):
    """
    Function for sqlite : substring selection
    :param X: sqlite will pass the column as X
    :param i: index of the first letter to keep, indexation starts at 0
    :param j: index of the first letter not to keep unless j == i,
    :return: substring
    """
    if i == j:
        return str(X)[i]
    return str(X)[i:j]


def divrest(x, y):
    """
    Function for sqlite : rest of the eucldian division
    :param x: sqlite will pass the column here
    :param y: float
    :return:
    """
    return x % y


def floor(x):
    return int(np.floor(x))