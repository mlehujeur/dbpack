"""
"""


PROMPT_COLORS = {
    "purple": '\033[95m',
    "blue": '\033[94m',
    "green": '\033[92m',
    "yellow": '\033[93m',
    "red": '\033[91m',
    "bold": '\033[1m',
    "underline": '\033[4m'}


PROMPT_TAILER = '\033[0m'


class ColoredPrinter(object):
    def __init__(self, color):

        if not color in PROMPT_COLORS.keys():
            raise ValueError('unknown color {}'.format(color))

        self.print_fmt = PROMPT_COLORS[color] + '{string}' + PROMPT_TAILER

    def __str__(self):
        """return a colored version of the representation string"""
        return self.format(self.__repr__())

    def format(self, *strings):
        """add coloration items to a list of strings
        """
        string = " ".join([self.print_fmt.format(string=string) for string in strings])
        return string

    def __call__(self, *strings, **kwargs):
        string = self.format(*strings)
        print(string, **kwargs)


printpurple = ColoredPrinter('purple')


printblue = ColoredPrinter('blue')


printgreen = ColoredPrinter('green')


printyellow = ColoredPrinter('yellow')


printred = ColoredPrinter('red')


printbold = ColoredPrinter('bold')


printunderline = ColoredPrinter('underline')


PRINTERS = {color: eval("print{}".format(color)) for color in PROMPT_COLORS}


if __name__ == '__main__':
    for color, printer in PRINTERS.items():
        print("{:<20s} {} ======> ".format(color, printer), end=" ")
        printer('hello world')

