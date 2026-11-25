"""
Horário semanal de explicações como problema de programação linear inteira.

Uso:
    python horario.py                          # usa dados_exemplo.json
    python horario.py dados.json --figura figuras/horario.png
"""
import argparse
import json

from ortools.linear_solver import pywraplp

DIAS = ["seg", "ter", "qua", "qui", "sex"]


def minutos(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def carregar(caminho):
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    conv = lambda ints: [(minutos(a), minutos(b)) for a, b in ints]
    return {
        "aula": d["aula_minutos"],
        "passo": d["passo_minutos"],
        "janela": (minutos(d["janela_dia"][0]), minutos(d["janela_dia"][1])),
        "fim_preferido": minutos(d.get("fim_preferido", d["janela_dia"][1])),
        "explicadora": {dia: conv(d["explicadora"].get(dia, [])) for dia in DIAS},
        "alunos": {
            nome: {
                "n": a["aulas_por_semana"],
                "livre": {dia: conv(a["livre"].get(dia, [])) for dia in DIAS},
                "combinado": {(dia, minutos(h)) for dia, h in a["combinado"]},
            }
            for nome, a in d["alunos"].items()
        },
    }


def cabe(intervalos, inicio, duracao):
    return any(a <= inicio and inicio + duracao <= b for a, b in intervalos)


def resolver(dados, pen_falta=100, pen_dobro=30, pen_tarde=5, pen_desvio=3, limite_tempo_s=60):
    """
    Variáveis
      x[a,d,t] = 1 se o aluno a tem aula no dia d a começar à hora t
      f[a]     = aulas do aluno a que ficam por marcar
      h[a,d]   = aulas do aluno a no dia d acima de 1 (2 horas seguidas, só em casos excecionais)
    Objetivo
      minimizar pen_falta*sum(f) + pen_dobro*sum(h)
                + pen_tarde*(meias horas de aula depois da hora preferida de fim, ex. 19:00)
                + pen_desvio*(aulas fora do horário combinado, para alunos que têm um combinado)
    """
    L, passo = dados["aula"], dados["passo"]
    s = pywraplp.Solver.CreateSolver("SCIP")
    s.SetTimeLimit(limite_tempo_s * 1000)

    x = {}
    for a, al in dados["alunos"].items():
        for d in DIAS:
            for t in range(dados["janela"][0], dados["janela"][1] - L + 1, passo):
                if cabe(dados["explicadora"][d], t, L) and cabe(al["livre"][d], t, L):
                    x[a, d, t] = s.BoolVar(f"x_{a}_{d}_{t}")

    f = {a: s.IntVar(0, al["n"], f"f_{a}") for a, al in dados["alunos"].items()}
    h = {(a, d): s.IntVar(0, 2, f"h_{a}_{d}") for a in dados["alunos"] for d in DIAS}

    for a, al in dados["alunos"].items():
        # (1) todas as aulas do aluno são marcadas, ou ficam em falta
        s.Add(sum(v for (aa, _, _), v in x.items() if aa == a) + f[a] == al["n"])
        # (2) 1 hora por dia para cada aluno; uma segunda aula no mesmo dia custa pen_dobro
        for d in DIAS:
            s.Add(sum(v for (aa, dd, _), v in x.items() if aa == a and dd == d) <= 1 + h[a, d])

    for d in DIAS:
        # (3) duas aulas não se sobrepõem (alunos diferentes no mesmo dia não são problema)
        for m in range(dados["janela"][0], dados["janela"][1], passo):
            s.Add(sum(v for (_, dd, t), v in x.items() if dd == d and t <= m < t + L) <= 1)

    fora = [v for (a, d, t), v in x.items()
            if dados["alunos"][a]["combinado"] and (d, t) not in dados["alunos"][a]["combinado"]]
    # Aulas que acabam depois da hora preferida (os alunos já estão cansados): custa por cada
    # meia hora de aula para lá dessa hora
    tarde = sum(max(0, t + L - dados["fim_preferido"]) / passo * v for (a, d, t), v in x.items())

    s.Minimize(pen_falta * sum(f.values()) + pen_dobro * sum(h.values())
               + pen_tarde * tarde + pen_desvio * sum(fora))

    estado = s.Solve()
    ok = estado in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE)
    aulas = sorted((d, t, a) for (a, d, t), v in x.items() if ok and v.solution_value() > 0.5)
    return {
        "estado": "ótimo" if estado == pywraplp.Solver.OPTIMAL else ("viável" if ok else "sem solução"),
        "objetivo": s.Objective().Value() if ok else None,
        "aulas": aulas,
        "em_falta": {a: int(v.solution_value()) for a, v in f.items() if ok and v.solution_value() > 0.5},
        "aulas_duplas": sum(round(v.solution_value()) for v in h.values()) if ok else None,
        "fora_do_combinado": sum(1 for (d, t, a) in aulas
                                 if dados["alunos"][a]["combinado"] and (d, t) not in dados["alunos"][a]["combinado"]),
        "tempo_s": s.WallTime() / 1000,
        "n_variaveis": len(x),
    }


def mostrar(res, L=60):
    print(f"Estado: {res['estado']} | objetivo: {res['objetivo']} | "
          f"dias com 2 aulas do mesmo aluno: {res['aulas_duplas']} | "
          f"aulas em falta: {res['em_falta'] or 'nenhuma'}")
    for d in DIAS:
        for dd, t, a in res["aulas"]:
            if dd == d:
                print(f"  {d} {hhmm(t)}-{hhmm(t + L)}  {a}")


def figura(res, caminho, L=60):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    azul, escuro = "#2a78d6", "#104281"
    fig, ax = plt.subplots(figsize=(9, 5))
    h0, h1 = 13 * 60, 20 * 60
    for i, d in enumerate(DIAS):
        for dd, t, a in res["aulas"]:
            if dd == d:
                ax.add_patch(Rectangle((i + 0.06, t), 0.88, L, facecolor=azul, edgecolor="white", linewidth=2))
                ax.text(i + 0.5, t + L / 2, a, ha="center", va="center", color="white", fontsize=10)
    ax.set_xlim(0, 5)
    ax.set_ylim(h1, h0)
    ax.set_xticks([i + 0.5 for i in range(5)])
    ax.set_xticklabels(["Segunda", "Terça", "Quarta", "Quinta", "Sexta"])
    ax.xaxis.tick_top()
    ax.set_yticks(range(h0, h1 + 1, 60))
    ax.set_yticklabels([hhmm(m) for m in range(h0, h1 + 1, 60)])
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.6)
    for sp in ["right", "bottom", "left", "top"]:
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)
    plt.tight_layout()
    plt.savefig(caminho, dpi=150)
    plt.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("dados", nargs="?", default="dados_exemplo.json")
    p.add_argument("--figura")
    args = p.parse_args()
    dados = carregar(args.dados)
    res = resolver(dados)
    mostrar(res, dados["aula"])
    if args.figura:
        figura(res, args.figura, dados["aula"])
