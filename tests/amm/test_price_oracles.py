import boa
import pytest
from hypothesis import given
from hypothesis import strategies as st
from ..conftest import PRICE, approx


@pytest.fixture(scope="module")
def ema_price_oracle(price_oracle, admin):
    with boa.env.prank(admin):
        signature = price_oracle.price.args_abi_type(0)[0]
        signature = b'\x00' * (32 - len(signature)) + signature
        return boa.load('contracts/price_oracles/EmaPriceOracle.vy', 10000, price_oracle.address, signature)


def test_price_oracle(price_oracle, amm):
    assert price_oracle.price() == PRICE * 10**18
    assert amm.price_oracle() == price_oracle.price()


def test_p_oracle_updown(amm):
    p_base = amm.get_base_price()
    A = amm.A()
    assert amm.p_oracle_up(0) == p_base
    assert approx(amm.p_oracle_down(0), p_base * (A - 1) // A, 1e-14)

    for i in range(-10, 10):
        mul = ((A - 1) / A) ** i
        p_up = p_base * mul
        p_down = p_up * (A - 1) / A
        assert approx(amm.p_oracle_up(i), p_up, 1e-14)
        assert approx(amm.p_oracle_down(i), p_down, 1e-14)


def test_p_current_updown(amm):
    p_base = amm.get_base_price()
    p_oracle = amm.price_oracle()
    A = amm.A()

    for i in range(-1023, 1023):
        mul = ((A - 1) / A) ** i
        p_base_up = p_base * mul
        p_base_down = p_base_up * (A - 1) / A
        p_current_up = p_oracle**3 / p_base_down**2
        p_current_down = p_oracle**3 / p_base_up**2
        assert approx(amm.p_current_up(i), p_current_up, 1e-10)
        assert approx(amm.p_current_down(i), p_current_down, 1e-10)


def test_ema_wrapping(ema_price_oracle, price_oracle):
    with boa.env.anchor():
        assert price_oracle.price() == ema_price_oracle.last_price()
        assert price_oracle.price() == ema_price_oracle.price()
        ema_price_oracle.price_w()
        boa.env.time_travel(20000)
        assert price_oracle.price() == ema_price_oracle.price()
        ema_price_oracle.price_w()
        boa.env.time_travel(20000)
        assert price_oracle.price() == ema_price_oracle.price()


@given(
    t1=st.integers(min_value=0, max_value=10**6),
    p_mul=st.floats(min_value=0.1, max_value=10),
)
def test_ema_sleep(ema_price_oracle, price_oracle, admin, t1, p_mul):
    p = price_oracle.price()
    p_target = int(p_mul * p)
    boa.env.time_travel(t1)
    with boa.env.prank(admin):
        price_oracle.set_price(p_target)
    ema_price_oracle.price_w()
    assert (ema_price_oracle.price() - p) < 0.001 * p
    boa.env.time_travel(100_000_000)
    assert (ema_price_oracle.price() - p_target) < 0.001 * p_target
