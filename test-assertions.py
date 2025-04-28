def f():
    class Falsy:
        def __bool__(self):
            return False
        def __repr__(self):
            return 'Falsy()'
    x = Falsy()
    assert x

try:
    f()
except Exception as e:
    exc = e


# >       assert x
# E    assert False

# >       assert x == 2
# E    assert 1 == 2

# >       assert x == 2 == y
# E    assert 1 == 2

# >       assert x == 2 and y == 42
# E    assert (1 == 2)

# >       assert x == 2 or y == 42
# E    assert (1 == 2 or 3 == 42)

# >       assert x == 2 or ((f() or True) - 7) == 33
# E    assert (1 == 2 or ((False or True) - 7) == 33)
# E     +  where False = f()


r(const) -> v(const)
r(var) -> v(var)
f(fcall) -> v(fcall)
r(binop(lhs, rhs)) -> binop(r(lhs), r(rhs))
