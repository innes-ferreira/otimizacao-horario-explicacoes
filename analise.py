"""
Análise de cenários do modelo de horário.

    python analise.py

Imprime a tabela de cenários e guarda os horários em figuras/.
"""
import copy

from horario import DIAS, carregar, figura, mostrar, resolver

dados = carregar("dados_exemplo.json")

cenarios = {}
cenarios["base"] = ("Base", dados)

d2 = copy.deepcopy(dados)  # semana de testes: o Aluno B precisa de 2 aulas
d2["alunos"]["Aluno B"]["n"] = 2
cenarios["testes"] = ("Semana de testes: Aluno B com 2 aulas", d2)

d3 = copy.deepcopy(d2)  # ...mas o Aluno B só está livre à quarta
d3["alunos"]["Aluno B"]["livre"] = {d: [] for d in DIAS}
d3["alunos"]["Aluno B"]["livre"]["qua"] = [(14 * 60, 17 * 60 + 30)]
cenarios["testes_quarta"] = ("Aluno B com 2 aulas, mas só livre à quarta", d3)

d4 = copy.deepcopy(dados)  # chega um aluno novo
d4["alunos"]["Aluno H"] = {"n": 1, "livre": {d: [(16 * 60, 20 * 60)] for d in DIAS}, "combinado": set()}
cenarios["novo"] = ("Chega um aluno novo (Aluno H)", d4)

print(f"{'Cenário':46s} {'aulas':>7s} {'2 aulas no dia':>15s} {'fora do combinado':>18s}")
for chave, (nome, dd) in cenarios.items():
    r = resolver(dd)
    total = sum(a["n"] for a in dd["alunos"].values())
    print(f"{nome:46s} {len(r['aulas']):>3d}/{total:<3d} {r['aulas_duplas']:>15d} {r['fora_do_combinado']:>18d}")
    if chave in ("base", "testes_quarta"):
        figura(r, f"figuras/horario_{chave}.png", dd["aula"])
