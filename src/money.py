from unittest.mock import ANY


class Money:
    DENOM = 1000000
    CENT_DENOM = DENOM // 100

    def __init__(self, val):
        self._val = int(val)

    def dollars(self):
        return self._val // Money.DENOM

    def cents(self):
        return self.total_cents() % 100

    def total_cents(self):
        return self._val // Money.CENT_DENOM

    def has_fraction_of_cent(self):
        return (self._val % Money.CENT_DENOM) != 0

    def __int__(self):
        assert isinstance(self._val, int)
        return self._val

    def __index__(self):
        assert isinstance(self._val, int)
        return self._val

    def __float__(self):
        return self._val / Money.DENOM

    def __add__(self, other):
        return Money(self._val + other._val)

    def __iadd__(self, other):
        self._val += other._val
        return self

    def __sub__(self, other):
        return Money(self._val - other._val)

    def __mul__(self, val):
        if isinstance(val, (int, float)):
            return Money(int(self._val * val))
        else:
            raise ValueError(f'Multiplicator [{val!r}] must be int or float')

    def __floordiv__(self, val):
        if isinstance(val, int):
            return Money(self._val // val)
        else:
            raise ValueError(f'Denominator [{val!r}] must be int')

    def __lt__(self, other):
        return self._val < other._val

    def __eq__(self, other):
        if isinstance(other, Money):
            return self._val == other._val
        elif other is ANY:
            return True
        elif other is None:
            return False
        else:
            raise ValueError(f"Other must be Money, but [{other!r}] given")

    def __le__(self, other):
        return self._val <= other._val

    def __str__(self):
        return f'{float(self):.2f}'

    def __repr__(self):
        return f'Money({self._val})'

    def __neg__(self):
        return Money(-self._val)

    def __abs__(self):
        return Money(abs(self._val))

    def __bool__(self):
        return bool(self._val)

    def __format__(self, format_spec):
        if not format_spec:
            return str(self)

        return format(float(self), format_spec)


Money.ZERO = Money(0)


def dollars(val):
    return Money(val * Money.DENOM)


def cents(val):
    return Money(val * Money.CENT_DENOM)


def format(money, currency=None):
    return str(money) if currency is None else f'{money} {currency}'
