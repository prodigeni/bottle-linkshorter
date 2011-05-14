"""
Little Base36-Lib

This is a 99,99% copy of wikipedia (http://en.wikipedia.org/wiki/Base_36), so that source is CC-BY-SA (http://en.wikipedia.org/wiki/Wikipedia:Text_of_Creative_Commons_Attribution-ShareAlike_3.0_Unported_License)
"""

def base36encode(number, alphabet='0123456789abcdefghijklmnopqrstuvwxyz'):
    """Convert positive integer to a base36 string."""
    if not isinstance(number, (int, long)):
        raise TypeError('number must be an integer')
    # Special case for zero
    if number == 0:
        return alphabet[0]
    base36 = ''
    sign = ''
    if number < 0:
        sign = '-'
        number = - number
    while number != 0:
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36
    return sign + base36

def base36decode(number):
    return int(number, 36)
