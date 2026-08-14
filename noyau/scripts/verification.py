import clingo, torch, owlready2
from ortools.sat.python import cp_model

print("torch:", torch.__version__)
print("owlready2:", owlready2.VERSION)
print("clingo:", clingo.__version__)

ctl = clingo.Control()
ctl.add("base", [], "chambre(312). chambre(407). bloquee(312). libre(X) :- chambre(X), not bloquee(X).")
ctl.ground([("base", [])])
with ctl.solve(yield_=True) as h:
    for m in h:
        print("clingo deduit:", [str(a) for a in m.symbols(shown=True) if a.name == "libre"])

m = cp_model.CpModel()
x = m.NewIntVar(0, 10, "x")
m.Add(x > 7)
m.Maximize(x)
s = cp_model.CpSolver()
s.Solve(m)
print("cp-sat trouve:", s.Value(x))

t = torch.nn.Linear(4, 2)(torch.randn(1, 4))
print("torch calcule:", tuple(t.shape))
