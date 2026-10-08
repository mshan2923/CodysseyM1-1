"""세피리아 패치 전후 플레이어 수 분석. 실행: python sephiria_analysis.py
각 단계는 독립 함수라서 이후 AI 비서에서 그대로 import 해 쓸 수 있다."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DATA = DATA_DIR / "steamdb_chart_Sephira_Max.csv"
PATCHES = DATA_DIR / "sephiria_patchnotes.csv"
PLOTS = BASE / "images"
SUSTAIN_THRESHOLD = 0.10   # 지속일 판정: 패치 전 7일 평균 대비 +10% 이상
SUSTAIN_CAP = 30

def setup_font():
    """한글 폰트를 파일 경로로 직접 등록 (시스템 폰트 캐시에 없어도 동작)."""
    from matplotlib import font_manager as fm
    cands = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "C:/Windows/Fonts/malgun.ttf",
             "/System/Library/Fonts/AppleSDGothicNeo.ttc"]
    for c in cands:
        if Path(c).exists():
            fm.fontManager.addfont(c)
            name = fm.FontProperties(fname=c).get_name()
            plt.rcParams["font.family"] = [name, "DejaVu Sans"]
            break
    plt.rcParams.update({"axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False})


setup_font()


# ---------- 1. 데이터 ----------
def load_daily(path=DATA):
    """일별 평균 플레이어 수(자정 행의 Average Players). 마지막 미완료 일자는 제외."""
    raw = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["DateTime"])
    d = raw[(raw.DateTime.dt.hour == 0) & (raw.DateTime.dt.minute == 0)].dropna(subset=["Average Players"])
    d = d.drop_duplicates("DateTime").sort_values("DateTime")
    s = d.set_index(d.DateTime.dt.normalize())["Average Players"].rename("avg_players")
    s = s.iloc[:-1] if s.index[-1] == raw.DateTime.max().normalize() else s  # 진행 중인 날 제외
    return s


def check_data(s):
    full = pd.date_range(s.index.min(), s.index.max())
    return {"기간": f"{s.index.min().date()} ~ {s.index.max().date()}", "일수": len(s),
            "누락일": len(full.difference(s.index)), "중복일": int(s.index.duplicated().sum()),
            "결측": int(s.isna().sum()), "0이하": int((s <= 0).sum())}


def load_patches(path=PATCHES):
    """같은 날짜의 패치는 하루 단위로 묶는다."""
    p = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["date"])
    p["titled"] = p.title.ne("No title")
    g = p.groupby("date").agg(n_patches=("title", "size"), major=("major", lambda x: (x == "Y").any()),
                              title=("title", lambda x: " / ".join(t for t in x[::-1] if t != "No title") or "No title"))
    return g.reset_index()


# ---------- 2. 통계 ----------
def overall_stats(s):
    return {"평균": s.mean(), "중앙값": s.median(), "최댓값": s.max(), "최댓값일": s.idxmax().date(),
            "최솟값": s.min(), "최솟값일": s.idxmin().date()}


def moving_average(s, w=7):
    return s.rolling(w, min_periods=w).mean()


def _win(s, d, a, b):
    """패치일 d 기준 [d+a, d+b] 일 구간. 전 구간이 데이터 안에 있어야 반환."""
    idx = pd.date_range(d + pd.Timedelta(days=a), d + pd.Timedelta(days=b))
    return s.reindex(idx) if idx.isin(s.index).all() else None


def sustained_days(s, d, base):
    n = 0
    for k in range(1, SUSTAIN_CAP + 1):
        t = d + pd.Timedelta(days=k)
        if t not in s.index or s[t] < base * (1 + SUSTAIN_THRESHOLD):
            break
        n += 1
    return n


def analyze_patches(s, patches):
    dates = patches.date.tolist()
    rows = []
    for _, p in patches.iterrows():
        d = p.date
        others = [x for x in dates if x != d]
        ov7 = [x for x in others if d - pd.Timedelta(days=7) <= x <= d + pd.Timedelta(days=7)]
        ov14 = [x for x in others if d - pd.Timedelta(days=14) <= x <= d + pd.Timedelta(days=14)]
        pre7, post7, pre14, post14 = _win(s, d, -7, -1), _win(s, d, 1, 7), _win(s, d, -14, -1), _win(s, d, 1, 14)
        r = {"date": d.date(), "title": p.title, "major": p.major, "n_patches_that_day": p.n_patches,
             "status_7d": "overlap" if ov7 else "clean", "other_patches_7d": len(ov7),
             "status_14d": "overlap" if ov14 else "clean", "other_patches_14d": len(ov14)}
        if pre7 is not None and post7 is not None:
            b = pre7.mean()
            r.update(pre7_mean=b, pre7_median=pre7.median(), post7_mean=post7.mean(), post7_median=post7.median(),
                     change_7d=post7.mean() - b, change_pct_7d=(post7.mean() - b) / b * 100)
            for name, (a, z) in {"d1_3": (1, 3), "d4_7": (4, 7), "d8_14": (8, 14)}.items():
                w = _win(s, d, a, z)
                r[f"{name}_mean"] = w.mean() if w is not None else np.nan
                r[f"{name}_pct"] = (w.mean() - b) / b * 100 if w is not None else np.nan
            r["sustained_days"] = sustained_days(s, d, b)
        if pre14 is not None and post14 is not None:
            r.update(pre14_mean=pre14.mean(), post14_mean=post14.mean(),
                     change_pct_14d=(post14.mean() - pre14.mean()) / pre14.mean() * 100)
        rows.append(r)
    return pd.DataFrame(rows)


def weekday_weekend(s, d, a, b):
    w = _win(s, d, a, b)
    if w is None: return None
    return {"weekday": w[w.index.dayofweek < 5].mean(), "weekend": w[w.index.dayofweek >= 5].mean()}


def find_outliers(s, window=28, z=3.5):
    """롤링 중앙값 대비 MAD 기반 z-score. 제거하지 않고 목록만 반환."""
    med = s.rolling(window, center=True, min_periods=window // 2).median()
    mad = (s - med).abs().rolling(window, center=True, min_periods=window // 2).median()
    score = 0.6745 * (s - med) / mad.replace(0, np.nan)
    return pd.DataFrame({"avg_players": s, "rolling_median": med, "robust_z": score})[score.abs() > z]



# ---------- 2-B. 보강: 팔로워, 이벤트 묶기, 플라시보 ----------
FOLLOWERS = DATA_DIR / "steamdb_chart_HubFollowers.csv"
EVENT_GAP = 7  # 이 일수 이내로 이어진 패치는 하나의 이벤트로 묶는다


def load_followers(path=FOLLOWERS):
    """허브 팔로워 누적 수와 일별 순증가(전일 대비)."""
    f = pd.read_csv(path, encoding="utf-8-sig", parse_dates=["DateTime"]).set_index("DateTime")["Followers"]
    f.index = f.index.normalize()
    return f, f.diff().rename("gain")


def group_events(patches, gap=EVENT_GAP):
    """패치일 간격이 gap일 이내면 같은 이벤트. 체인 방식이라 연속 패치는 하나로 묶인다."""
    groups = []
    for _, p in patches.sort_values("date").iterrows():
        if groups and (p.date - groups[-1][-1].date).days <= gap:
            groups[-1].append(p)
        else:
            groups.append([p])
    rows = []
    for g in groups:
        majors = [p for p in g if p.major]
        titled = [p for p in g if p.title != "No title"]
        head = (majors or titled or g)[0]
        rows.append({"start": g[0].date, "end": g[-1].date, "n_patch_days": len(g), "major": bool(majors),
                     "title": head.title})
    return pd.DataFrame(rows)


def window_change(s, d, kind="pct"):
    """패치일 d 기준 이후 7일 평균 vs 이전 7일 평균. kind: pct(%) 또는 diff(차이)."""
    pre, post = _win(s, d, -7, -1), _win(s, d, 1, 7)
    if pre is None or post is None:
        return np.nan
    return (post.mean() - pre.mean()) / pre.mean() * 100 if kind == "pct" else post.mean() - pre.mean()


def placebo_distribution(s, patch_dates, kind="pct", margin=7):
    """패치가 ±margin일 안에 없는 날을 가짜 패치일로 보고 같은 변화량을 계산한 분포."""
    pd_ = list(patch_dates)
    free = [d for d in s.index if all(abs((d - x).days) > margin for x in pd_)]
    return pd.Series({d: window_change(s, d, kind) for d in free}).dropna()


def percentile_of(value, dist):
    return float((dist < value).mean() * 100) if pd.notna(value) else np.nan


def analyze_events(players, gain, events, patch_dates):
    dp, dg = placebo_distribution(players, patch_dates, "pct"), placebo_distribution(gain, patch_dates, "diff")
    rows = []
    for i, e in events.iterrows():
        others = events.drop(i)
        clean = not ((others.start <= e.start + pd.Timedelta(days=14)) & (others.end >= e.start - pd.Timedelta(days=7))).any()
        pct, gd = window_change(players, e.start, "pct"), window_change(gain, e.start, "diff")
        pre_g, post_g = _win(gain, e.start, -7, -1), _win(gain, e.start, 1, 7)
        base = _win(players, e.start, -7, -1)
        rows.append({**e.to_dict(), "event_status": "clean" if clean else "overlap",
                     "players_pre7": base.mean() if base is not None else np.nan,
                     "players_change_pct": pct, "players_pctile_vs_placebo": percentile_of(pct, dp),
                     "gain_pre7": pre_g.mean() if pre_g is not None else np.nan,
                     "gain_post7": post_g.mean() if post_g is not None else np.nan,
                     "gain_change": gd, "gain_pctile_vs_placebo": percentile_of(gd, dg)})
    return pd.DataFrame(rows), dp, dg


# ---------- 3. 그래프 ----------
def plot_overall(s, patches, out):
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(s.index, s.values, color="#9ecae1", lw=1, label="일별 평균")
    ax.plot(s.index, moving_average(s), color="#08519c", lw=2, label="7일 이동평균")
    for d in patches.date[~patches.major]:
        ax.axvline(d, color="#999", lw=0.4, alpha=0.5)
    for _, p in patches[patches.major].iterrows():
        ax.axvline(p.date, color="#d62728", lw=1.6)
        ax.annotate(p.title.split(" Update")[0].replace("MAJOR ", ""), (p.date, s.max() * 0.97), rotation=90,
                    ha="right", va="top", color="#d62728", fontsize=10)
    ax.plot([], [], color="#999", lw=0.8, label="패치 (회색 선)")
    ax.plot([], [], color="#d62728", lw=1.6, label="메이저 패치")
    ax.set(title="세피리아 일별 평균 플레이어 수와 패치 날짜", ylabel="평균 플레이어 수")
    ax.legend(loc="upper left"); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def _lab(r):
    return f"{r.title.split(' Update')[0]}\n({str(r.date)})"


def plot_comparison(res, out):
    m = res[res.major & res.pre7_mean.notna()].reset_index(drop=True)
    x = np.arange(len(m)); w = 0.27
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, (col, lab, c) in enumerate([("pre7_mean", "이전 7일", "#bdbdbd"), ("post7_mean", "이후 7일", "#3182bd"),
                                       ("post14_mean", "이후 14일", "#08519c")]):
        bars = ax.bar(x + (i - 1) * w, m[col], w, label=lab, color=c)
        ax.bar_label(bars, fmt="{:,.0f}", fontsize=8, padding=2)
    ax.set_xticks(x, [_lab(r) + ("\n[겹침]" if r.status_7d == "overlap" else "\n[단독]") for r in m.itertuples()])
    ax.set(title="메이저 패치 전후 평균 플레이어 수 (겹침: 비교 구간 ±7일에 다른 패치 존재)", ylabel="평균 플레이어 수")
    ax.legend(); ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def plot_persistence(res, out):
    m = res[res.major & res.pre7_mean.notna()].reset_index(drop=True)
    fig, axes = plt.subplots(1, len(m), figsize=(3.6 * len(m), 5.5))
    axes = np.atleast_1d(axes)
    cols = [("pre7_mean", "이전\n7일", "#bdbdbd"), ("d1_3_mean", "+1~3일", "#9ecae1"),
            ("d4_7_mean", "+4~7일", "#4292c6"), ("d8_14_mean", "+8~14일", "#08519c")]
    for ax, r in zip(axes, m.itertuples()):
        vals = [getattr(r, c) for c, _, _ in cols]
        bars = ax.bar([l for _, l, _ in cols], vals, color=[c for _, _, c in cols])
        ax.bar_label(bars, fmt="{:,.0f}", fontsize=8, padding=2)
        sd = int(r.sustained_days)
        ax.set_title(f"{_lab(r)}\n지속 {sd}일{'+' if sd >= SUSTAIN_CAP else ''} | {r.status_7d}", fontsize=10)
        ax.tick_params(axis="x", labelsize=8); ax.grid(axis="y", alpha=0.2)
    fig.suptitle("패치 이후 기간별 평균 플레이어 수 (지속: 이전 7일 평균 +10% 이상이 연속된 일수, 최대 30일까지 집계)", y=1.0)
    fig.tight_layout(); fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)


def plot_change_rate(res, out):
    m = res[res.change_pct_7d.notna()].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(17, 6))
    colors = ["#3182bd" if s == "clean" else "#bdbdbd" for s in m.status_7d]
    ax.bar(range(len(m)), m.change_pct_7d, color=colors, edgecolor=["#d62728" if v else "none" for v in m.major],
           linewidth=2)
    for i, r in m[m.major].iterrows():
        ax.annotate(f"{r.title.split(' Update')[0]}\n{r.change_pct_7d:+.0f}%", (i, r.change_pct_7d),
                    ha="center", va="bottom", fontsize=9, color="#d62728", xytext=(0, 3), textcoords="offset points")
    step = max(1, len(m) // 20)
    ax.set_xticks(range(0, len(m), step), [str(m.date[i]) for i in range(0, len(m), step)], rotation=60, fontsize=8)
    ax.axhline(0, color="k", lw=0.8)
    from matplotlib.patches import Patch
    handles = [Patch(color="#3182bd", label="clean (±7일 내 다른 패치 없음)"), Patch(color="#bdbdbd", label="overlap (다른 패치 존재)"),
               Patch(facecolor="white", edgecolor="#d62728", linewidth=2, label="메이저 패치")]
    ax.set(title="패치별 7일 평균 변화율 (이후 7일 vs 이전 7일)", ylabel="변화율 (%)"); ax.legend(handles=handles); ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def plot_placebo(ev, dp, out):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.hist(dp.clip(-50, 260), bins=np.arange(-50, 265, 10), color="#bdbdbd", edgecolor="white", label=f"패치 없는 날 {len(dp)}개의 7일 변화율")
    p95 = dp.quantile(0.95)
    ax.axvline(p95, color="#555", ls="--", label=f"95번째 백분위 {p95:+.0f}%")
    for _, r in ev[ev.major & ev.players_change_pct.notna()].iterrows():
        x = min(r.players_change_pct, 255)
        ax.axvline(x, color="#d62728", lw=2)
        ax.text(x, ax.get_ylim()[1] * 0.97, f"{r.title.split(' Update')[0]}\n{r.players_change_pct:+.0f}%" + (" (축 밖)" if r.players_change_pct > 255 else ""),
                rotation=90, ha="right", va="top", color="#d62728", fontsize=9)
    ax.set(title="메이저 이벤트의 7일 변화율 vs 패치 없는 날의 변화율 분포", xlabel="이후 7일 평균 vs 이전 7일 평균 변화율 (%)", ylabel="날짜 수")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False); ax.grid(axis="y", alpha=0.2)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def plot_followers(f, gain, patches, out):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    a1.plot(f.index, f.values, color="#08519c", lw=2); a1.set(title="허브 팔로워 수 (누적)", ylabel="팔로워")
    a2.bar(gain.index, gain.values, color="#9ecae1", width=1.0, label="일별 순증가")
    a2.plot(gain.index, gain.rolling(7).mean(), color="#08519c", lw=2, label="7일 이동평균")
    a2.set(title="팔로워 일별 순증가", ylabel="명/일"); a2.legend(loc="upper left")
    for ax in (a1, a2):
        ax.grid(alpha=0.2)
        for d in patches.date[~patches.major]: ax.axvline(d, color="#999", lw=0.4, alpha=0.5)
        for d in patches.date[patches.major]: ax.axvline(d, color="#d62728", lw=1.6)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


# ---------- 4. 실행 ----------
def main():
    PLOTS.mkdir(exist_ok=True)
    s = load_daily(); patches = load_patches()
    print("데이터 점검:", check_data(s)); print("전체 통계:", overall_stats(s))
    s.rename_axis("date").to_csv(DATA_DIR / "cleaned_data.csv", encoding="utf-8-sig")
    res = analyze_patches(s, patches)
    res.to_csv(DATA_DIR / "patch_analysis.csv", index=False, encoding="utf-8-sig")
    find_outliers(s).to_csv(DATA_DIR / "outliers.csv", encoding="utf-8-sig")
    plot_overall(s, patches, PLOTS / "01_overall_trend.png")
    plot_comparison(res, PLOTS / "02_patch_comparison.png")
    plot_persistence(res, PLOTS / "03_persistence.png")
    plot_change_rate(res, PLOTS / "04_patch_change_rate.png")
    # 보강: 이벤트 묶기 + 플라시보 + 팔로워
    f, gain = load_followers()
    ev, dp, dg = analyze_events(s, gain, group_events(patches), patches.date)
    ev.to_csv(DATA_DIR / "event_analysis.csv", index=False, encoding="utf-8-sig")
    plot_placebo(ev, dp, PLOTS / "05_placebo.png")
    plot_followers(f, gain, patches, PLOTS / "06_followers.png")
    print("플라시보(패치 없는 날) 7일 변화율:", dp.describe().round(1).to_dict(), "95%:", round(dp.quantile(.95), 1))
    return s, res


if __name__ == "__main__":
    main()
