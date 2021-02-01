def add_no_carry(*args):
    """
    Addition without carry; addition is not carried to the next decimal up.

    Parameters
    ----------
    *args : iterable (not string)
        Iterate of ints to add without carry.

    Returns
    -------
    final_sum : int
        the result...

    Examples
    --------
    >>> add_no_carry(1, 1)
    2

    >>> add_no_carry(1, 18)
    19

    >>> add_no_carry(1, 19)
    10

    The '10'is not carried over to the next decimal.
    """
    num_digits = []
    
    for arg in args:
        num_digits.append(len(str(arg)))
    
    max_digits = max(num_digits) 
    # list comprehension way
    # max_digits = max([len(str(arg)) for arg in args])
    final_sum = 0
    
    for pwr in range(1, max_digits + 1): # iterate through ea decimal
        result_no_carry = 0
        for arg in args:
            if len(str(arg)) >= pwr:
                # modulus sets the current decimal as the most significant 
                # decimal
                # floor div selects the most significant decimal
                result_no_carry += arg % 10**pwr // 10**(pwr - 1)
                
        # list comprehension way
        # result_no_carry = sum([arg % 10**pwr // 10**(pwr - 1) for arg in args if len(str(arg)) >= pwr])
        
        # final_sum = str(result_no_carry % 10) + final_sum
        final_sum += result_no_carry % 10
        
    return int(final_sum)