from pytest import mark, raises

import money

def test_factory_methods():
    assert money.dollars(5).dollars() == 5
    assert money.dollars(5).cents() == 0
    assert money.cents(5).dollars() == 0
    assert money.cents(5).cents() == 5


def test_construction():
    m = money.Money(12345678)
    assert m.dollars() == 12
    assert m.cents() == 34


def test_binary_arithmetic_operations():
    assert money.Money(10) + money.Money(1) == money.Money(11)
    assert money.Money(10) - money.Money(1) == money.Money(9)


def test_floordiv_operations():
    assert money.Money(11) // 5 == money.Money(2)
    with raises(ValueError):
        money.dollars(11) // 1.1


def test_multiplication():
    assert money.dollars(1) * 10 == money.dollars(10)


def test_comparison():
    assert money.Money(1) == money.Money(1)
    assert money.Money(1) != money.Money(2)
    assert money.Money(1) < money.Money(2)
    assert money.Money(2) > money.Money(1)
    assert money.Money(1) <= money.Money(2)
    assert money.Money(2) <= money.Money(2)
    assert money.Money(2) >= money.Money(1)
    assert money.Money(2) >= money.Money(2)
    assert money.Money(0) != None


def test_str():
    assert str(money.dollars(1)) == '1.00'


def test_repr():
    assert repr(money.dollars(1)) == 'Money(1000000)'


def test_as_float():
    assert float(money.cents(1)) == 0.01


@mark.parametrize('sut, expected_res', [
    (money.Money(0), False),
    (money.Money(1), True)
])
def test_to_bool(sut, expected_res):
    actual_res = bool(sut)
    assert actual_res is expected_res


def test_has_fraction_of_cent():
    three_cents = money.cents(3)
    one_and_half_cents = three_cents // 2
    assert not three_cents.has_fraction_of_cent()
    assert one_and_half_cents.has_fraction_of_cent()
