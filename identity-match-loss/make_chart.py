"""Draw the funnel and scenario comparison from the simulator (synthetic)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from identity_match_loss import default_steps, run_funnel, fewer_handoffs, final_reach, layered_retention, Step

N = 1000
scen = {
    "Baseline (deterministic)": default_steps("deterministic"),
    "Probabilistic": default_steps("probabilistic"),
    "Layered": [Step("ID vendor match", layered_retention())] + default_steps()[1:],
    "One fewer handoff": fewer_handoffs(default_steps(), "Onboarding"),
}
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
f = run_funnel(N, scen["Baseline (deterministic)"])
ax[0].barh([n for n, _ in f][::-1], [v for _, v in f][::-1], color="#0F766E")
ax[0].set_title("Funnel: 1,000 seed records (illustrative)")
vals = {k: final_reach(N, v) for k, v in scen.items()}
ax[1].barh(list(vals)[::-1], list(vals.values())[::-1], color="#C2410C")
ax[1].set_title("Final reached by scenario")
for a in ax: a.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Synthetic data. Rates are illustrative, not vendor performance.", fontsize=8)
fig.tight_layout(rect=[0, 0.04, 1, 1])
fig.savefig(pathlib.Path(__file__).parent / "docs" / "funnel.png", dpi=150)
print(vals)
