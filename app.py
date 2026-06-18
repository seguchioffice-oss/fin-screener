"""
Quality Stock Screener — US & Japan
Real-time data via yfinance + Finnhub
"""

import streamlit as st
import streamlit.components.v1 as st_html
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import math
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from candidates import US_CANDIDATES, JP_CANDIDATES
from scorer import fetch_ticker_data, score_stock

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Quality Compounder Screener",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── パスワード認証 ────────────────────────────────────────────────────────────
def check_password() -> bool:
    correct = st.secrets.get("APP_PASSWORD", "")
    if not correct:
        return True  # secrets未設定のローカル実行時はスキップ

    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <div style="max-width:360px;margin:80px auto;padding:32px;
                background:#fff;border-radius:12px;
                box-shadow:0 2px 16px rgba(0,0,0,0.10)">
      <div style="text-align:center;font-size:2rem;margin-bottom:8px">📊</div>
      <div style="text-align:center;font-weight:700;font-size:1.2rem;
                  color:#1a1a2e;margin-bottom:24px">Quality Compounder Screener</div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        pwd = st.text_input("パスワード", type="password", key="pwd_input",
                            placeholder="パスワードを入力")
        if st.button("ログイン", use_container_width=True):
            if pwd == correct:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── global ── */
    .stApp { background-color: #f8f9fc; }
    .stApp, .stApp p, .stApp li, .stApp label { color: #1a1a2e; }

    /* ── sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e4e8f0;
    }
    [data-testid="stSidebar"] * { color: #1a1a2e !important; }

    /* ── tabs: スクロール可能・折り返さない ── */
    [data-testid="stTabs"] {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        flex-wrap: nowrap !important;
    }
    [data-testid="stTabs"] button {
        color: #555 !important;
        font-weight: 500;
        white-space: nowrap;
        min-width: fit-content;
        font-size: 0.85rem;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #1a56db !important;
        border-bottom: 2px solid #1a56db;
    }

    /* ── dataframe: 横スクロール ── */
    [data-testid="stDataFrame"] {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    [data-testid="stDataFrame"] th {
        background: #eef1f8 !important;
        color: #1a1a2e !important;
    }

    /* ── metric cards ── */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e4e8f0;
        border-radius: 8px;
        padding: 10px 14px;
    }
    [data-testid="stMetricValue"] { color: #1a1a2e !important; }
    [data-testid="stMetricDelta"] svg { display: none; }

    /* ── buttons ── */
    .stButton > button {
        background: #1a56db;
        color: #fff;
        border: none;
        border-radius: 6px;
        min-height: 44px;  /* iOS タップ最小サイズ */
    }
    .stButton > button:hover { background: #1648c0; }

    /* ── select / input: iOS フォント固定 ── */
    input, select, textarea {
        font-size: 16px !important;  /* iOS 自動ズーム防止 */
    }

    /* ── divider ── */
    hr { border-color: #e4e8f0; }

    /* ═══════════════════════════════════════════
       📱 モバイル (〜768px) レスポンシブ
    ═══════════════════════════════════════════ */
    @media (max-width: 768px) {

        /* メインコンテンツの余白を詰める */
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 0.5rem !important;
            max-width: 100% !important;
        }

        /* h1/h2 を小さく */
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.1rem !important; }
        h3 { font-size: 1rem !important; }

        /* Streamlit columns → 縦積み */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        /* メトリクス: 2列グリッド */
        [data-testid="stMetric"] {
            padding: 8px 10px;
            font-size: 0.85rem;
        }
        [data-testid="stMetricValue"] { font-size: 1.1rem !important; }

        /* タブラベルを小さく */
        [data-testid="stTabs"] button {
            font-size: 0.75rem !important;
            padding: 6px 8px !important;
        }

        /* selectbox・input を大きめに */
        [data-testid="stSelectbox"] select,
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input {
            font-size: 16px !important;
            min-height: 44px;
        }

        /* サイドバートグルボタンを見やすく */
        [data-testid="collapsedControl"] {
            display: flex !important;
        }

        /* dataframe: 全幅スクロール */
        [data-testid="stDataFrame"] > div {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
        }

        /* plotly チャート: タッチ操作用マージン */
        .js-plotly-plot {
            touch-action: pan-x pan-y !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 設定")
    finnhub_key = st.text_input(
        "Finnhub API Key",
        value=st.secrets.get("FINNHUB_API_KEY", os.environ.get("FINNHUB_API_KEY", "")),
        type="password",
        help="finnhub.io で無料取得できます",
    )

    st.markdown("---")
    st.markdown("### スクリーニング基準")
    min_score = st.slider("最低スコア (0–100)", 0, 80, 40)
    market_filter = st.selectbox("市場", ["全て", "US", "Japan"])

    st.markdown("---")
    st.markdown("### テクニカル設定")
    show_sma = st.checkbox("SMA 50/200 を表示", value=True)
    show_volume = st.checkbox("出来高を表示", value=True)

    st.markdown("---")
    refresh = st.button("🔄 データ再取得", use_container_width=True)
    if "_stocks_at" in st.session_state:
        st.caption(f"最終取得: {st.session_state['_stocks_at']}")

    st.markdown("---")
    st.markdown("""
    **スコアリング基準 (100点)**
    | 項目 | 配点 |
    |------|------|
    | EPS多年成長 | 25 |
    | ROIC | 20 |
    | FCF/純利益比 | 15 |
    | 希薄化抑制 | 15 |
    | テクニカル: モメンタム | 15 |
    | テクニカル: RSI/MA | 10 |
    """)


# ── finnhub real-time quote ────────────────────────────────────────────────────
@st.cache_data(ttl=30)  # refresh every 30 seconds
def get_finnhub_quote(ticker: str, api_key: str) -> dict | None:
    if not api_key:
        return None
    try:
        import finnhub
        fc = finnhub.Client(api_key=api_key)
        # Finnhub uses different symbol format for Japan stocks
        fh_ticker = ticker.replace(".T", "") if ".T" in ticker else ticker
        q = fc.quote(fh_ticker)
        return q
    except Exception:
        return None


# ── data loading with caching ─────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_all_stocks(market: str) -> list[dict]:
    candidates = []
    if market in ("全て", "US"):
        candidates += [{"market": "US", **c} for c in US_CANDIDATES]
    if market in ("全て", "Japan"):
        candidates += [{"market": "Japan", **c} for c in JP_CANDIDATES]

    total = len(candidates)
    slot = [0]  # 完了カウンター（スレッド共有）
    prog = st.progress(0, text=f"データ取得中 (0/{total})...")

    def _fetch(idx: int, c: dict):
        data = fetch_ticker_data(c["ticker"])
        data["market"] = c["market"]
        if not data.get("name") or data.get("name") == c["ticker"]:
            data["name"] = c["name"]
        if not data.get("sector") or data.get("sector") == "N/A":
            data["sector"] = c.get("sector", "N/A")
        scores = score_stock(data)
        data["scores"] = scores
        data["total_score"] = scores["total"]
        return idx, data

    ordered = [None] * total
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_fetch, i, c): i for i, c in enumerate(candidates)}
        for fut in as_completed(futs):
            try:
                idx, data = fut.result()
                ordered[idx] = data
            except Exception:
                pass
            slot[0] += 1
            prog.progress(slot[0] / total, text=f"データ取得中 ({slot[0]}/{total})...")

    prog.empty()
    results = [r for r in ordered if r is not None]

    # エントリー判定を付与してソート
    # entry_rankは後で entry_suggestion() を呼ぶが、循環参照を避けるため
    # テクニカル指標から直接簡易判定する
    def _entry_rank(d: dict) -> int:
        price  = d.get("price") or 0
        sma50  = d.get("sma50")
        sma200 = d.get("sma200")
        rsi    = d.get("rsi")
        mom    = d.get("momentum_3m") or 0
        if not price:
            return 3
        above200 = sma200 and price > sma200
        above50  = sma50  and price > sma50
        rsi_ok   = rsi is not None and 40 <= rsi <= 70
        if above200 and above50 and rsi_ok and mom > 0:
            return 0   # 🟢 買い検討圏
        elif above200 and rsi_ok:
            return 1   # 🟡 条件付き
        elif above200:
            return 2   # 🟡 長期OK・短期注意
        else:
            return 3   # 🔴 様子見

    for d in results:
        d["entry_rank"] = _entry_rank(d)

    # エントリー圏 → スコア順 の2段ソート
    return sorted(results, key=lambda x: (x["entry_rank"], -x["total_score"]))


def fmt_pct(v, digits=1):
    if v is None:
        return "N/A"
    return f"{v*100:.{digits}f}%"

def fmt_num(v, digits=1):
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}"

def fmt_large(v):
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"${v/1e12:.1f}T"
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    return f"${v:.0f}"

def score_color(score: int) -> str:
    if score >= 75:
        return "#0a7c42"
    elif score >= 60:
        return "#1a7f5a"
    elif score >= 45:
        return "#b07c00"
    else:
        return "#c0392b"

def score_bg(score: int) -> str:
    if score >= 75:
        return "#e8f8f0"
    elif score >= 60:
        return "#edf7f2"
    elif score >= 45:
        return "#fef9ec"
    else:
        return "#fdf0ef"

def score_bar(label: str, score: int, max_score: int) -> str:
    pct = min(score / max_score * 100, 100)
    norm = int(score / max_score * 100)
    color = score_color(norm)
    bg    = score_bg(norm)
    return f"""
    <div style="background:{bg};border-radius:6px;padding:8px 12px;margin-bottom:6px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
        <span style="font-size:0.85rem;font-weight:600;color:#1a1a2e">{label}</span>
        <span style="font-size:0.9rem;font-weight:700;color:{color}">{score}<span style="font-size:0.72rem;color:#999;font-weight:400">/{max_score}</span></span>
      </div>
      <div style="background:#e0e4ee;border-radius:6px;height:10px">
        <div style="width:{pct:.0f}%;height:10px;background:{color};border-radius:6px;
                    transition:width 0.4s ease"></div>
      </div>
    </div>
    """


# ── main UI ───────────────────────────────────────────────────────────────────
st.title("📊 Quality Compounder Screener")
st.markdown(f"*EPS成長 × ROIC × FCF × 希薄化 × テクニカル — {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

tab_screen, tab_detail, tab_compare, tab_smt = st.tabs([
    "🏆 スクリーニング結果", "🔍 銘柄詳細", "📈 比較チャート", "🔄 SMTモメンタム"
])

# session_state でデータ保持 — 明示的リフレッシュ or 市場切替時のみ再取得
_market_changed = st.session_state.get("_stocks_market") != market_filter
if refresh or "all_stocks" not in st.session_state or _market_changed:
    if refresh:
        st.cache_data.clear()
    with st.spinner("データ取得中... (初回のみ時間がかかります)"):
        st.session_state["all_stocks"] = load_all_stocks(market_filter)
        st.session_state["_stocks_market"] = market_filter
        st.session_state["_stocks_at"] = datetime.now().strftime("%m/%d %H:%M")

all_stocks = st.session_state.get("all_stocks", [])

filtered = [s for s in all_stocks if s["total_score"] >= min_score]
us_top = [s for s in filtered if s.get("market") == "US"][:10]
jp_top = [s for s in filtered if s.get("market") == "Japan"][:10]


# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: SCREENING RESULTS
# ──────────────────────────────────────────────────────────────────────────────
with tab_screen:

    def render_market_table(stocks: list[dict], market_label: str):
        st.subheader(f"{'🇺🇸' if market_label=='US' else '🇯🇵'} {market_label} Top {len(stocks)}")

        if not stocks:
            st.info("条件に合う銘柄が見つかりませんでした。最低スコアを下げてください。")
            return

        ENTRY_LABEL = {0: "🟢 買い圏", 1: "🟡 条件付き", 2: "🟡 長期OK", 3: "🔴 様子見"}

        rows = []
        for rank, s in enumerate(stocks, 1):
            sc = s["scores"]
            fh = get_finnhub_quote(s["ticker"], finnhub_key)
            rt_price  = fh.get("c") if fh and fh.get("c") else s.get("price")
            rt_change = fh.get("dp") if fh else None

            rows.append({
                "エントリー":  ENTRY_LABEL.get(s.get("entry_rank", 3), "⚪"),
                "順位":        rank,
                "ティッカー":  s["ticker"],
                "企業名":      s.get("name", s["ticker"]),
                "セクター":    s.get("sector", "N/A"),
                "株価":        f"{rt_price:.2f}" if rt_price else "N/A",
                "前日比%":     f"{rt_change:+.2f}%" if rt_change else "N/A",
                "時価総額":    fmt_large(s.get("market_cap")),
                "EPS CAGR":   fmt_pct(s.get("eps_cagr")),
                "ROIC":        fmt_pct(s.get("roic")),
                "FCF/利益":   fmt_num(s.get("fcf_to_netinc")),
                "希薄化/年":  fmt_pct(s.get("dilution_annual")),
                "RSI":         fmt_num(s.get("rsi")),
                "3M騰落":     fmt_pct(s.get("momentum_3m")),
                "総合スコア":  s["total_score"],
            })

        df = pd.DataFrame(rows)
        display_cols = ["エントリー","順位","ティッカー","企業名","セクター","株価","前日比%",
                        "時価総額","EPS CAGR","ROIC","FCF/利益","希薄化/年",
                        "RSI","3M騰落","総合スコア"]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "総合スコア": st.column_config.ProgressColumn(
                    "総合スコア", min_value=0, max_value=100, format="%d点"
                ),
                "株価":   st.column_config.TextColumn("株価"),
                "前日比%": st.column_config.TextColumn("前日比%"),
                "EPS CAGR": st.column_config.TextColumn("EPS CAGR"),
                "ROIC":     st.column_config.TextColumn("ROIC"),
            }
        )

        # Score breakdown cards — 5-per-row grid (mobile: 2-per-row)
        st.markdown("##### スコア内訳")
        card_html = """<style>
        .score-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:4px}
        @media(max-width:520px){.score-grid{grid-template-columns:repeat(2,1fr)}}
        </style><div class="score-grid">"""
        for s_card in stocks:
            sc_card = s_card["scores"]
            total   = s_card["total_score"]
            color   = score_color(total)
            bg      = score_bg(total)
            pct     = total  # out of 100
            # mini sub-bars (2px each)
            def mini(v, mx):
                p = min(v / mx * 100, 100)
                c = score_color(int(v / mx * 100))
                return (f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">'
                        f'<div style="background:#e0e4ee;border-radius:3px;height:5px;flex:1">'
                        f'<div style="width:{p:.0f}%;height:5px;background:{c};border-radius:3px"></div></div>'
                        f'<span style="font-size:0.65rem;color:#666;width:14px;text-align:right">{v}</span>'
                        f'</div>')
            subs = (
                f'<div style="font-size:0.65rem;color:#999;margin:6px 0 2px">EPS</div>' + mini(sc_card.get("eps",0), 25) +
                f'<div style="font-size:0.65rem;color:#999;margin:2px 0">ROIC</div>'   + mini(sc_card.get("roic",0), 20) +
                f'<div style="font-size:0.65rem;color:#999;margin:2px 0">FCF</div>'    + mini(sc_card.get("fcf",0), 15) +
                f'<div style="font-size:0.65rem;color:#999;margin:2px 0">希薄化</div>' + mini(sc_card.get("dilution",0), 15) +
                f'<div style="font-size:0.65rem;color:#999;margin:2px 0">MOM</div>'    + mini(sc_card.get("momentum",0), 15) +
                f'<div style="font-size:0.65rem;color:#999;margin:2px 0">RSI</div>'    + mini(sc_card.get("rsi",0), 10)
            )
            er = s_card.get("entry_rank", 3)
            entry_badge_color = {0:"#0a7c42", 1:"#b07c00", 2:"#b07c00", 3:"#c0392b"}.get(er, "#999")
            entry_badge_bg    = {0:"#e8f8f0", 1:"#fef9ec", 2:"#fef9ec", 3:"#fdf0ef"}.get(er, "#f4f4f4")
            entry_badge_text  = {0:"🟢 買い圏", 1:"🟡 条件付き", 2:"🟡 長期OK", 3:"🔴 様子見"}.get(er, "⚪")
            card_html += f"""
            <div style="background:#ffffff;border-radius:10px;padding:12px;
                        border:1px solid #e4e8f0;border-top:4px solid {color}">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px">
                <div style="font-size:0.78rem;font-weight:700;color:#333">{s_card['ticker']}</div>
                <div style="background:{entry_badge_bg};color:{entry_badge_color};border-radius:4px;
                            padding:1px 5px;font-size:0.62rem;font-weight:700;white-space:nowrap">{entry_badge_text}</div>
              </div>
              <div style="font-size:0.68rem;color:#999;margin-bottom:6px;white-space:nowrap;
                          overflow:hidden;text-overflow:ellipsis">{s_card.get('name','')}</div>
              <div style="background:#e0e4ee;border-radius:6px;height:8px;margin-bottom:4px">
                <div style="width:{pct}%;height:8px;background:{color};border-radius:6px"></div>
              </div>
              <div style="font-size:1.4rem;font-weight:800;color:{color};text-align:center;
                          margin:4px 0">{total}</div>
              {subs}
            </div>"""
        card_html += '</div>'
        n_cards = len(stocks)
        # desktop: ceil(n/5)行×220px / mobile: ceil(n/2)行×220px → scrolling で吸収
        _h = min(max(math.ceil(n_cards / 5) * 230, 230), 500)
        st_html.html(
            f'<div style="font-family:sans-serif">{card_html}</div>',
            height=_h,
            scrolling=True,
        )

    col_us, col_jp = st.columns(2)
    with col_us:
        render_market_table(us_top, "US")
    with col_jp:
        render_market_table(jp_top, "Japan")

    # ── Overall score radar comparison ──────────────────────────────
    st.markdown("---")
    st.subheader("📡 スコアレーダー (Top 5 × 市場)")

    def radar_chart(stocks: list[dict], title: str):
        categories = ["EPS成長", "ROIC", "FCF", "希薄化", "モメンタム", "RSI/MA"]
        max_vals   = [25, 20, 15, 15, 15, 10]
        fig = go.Figure()
        colors = ["#00d26a","#7eca9c","#f0c040","#60b0f0","#e080e0"]
        for s, color in zip(stocks[:5], colors):
            sc = s["scores"]
            vals = [
                sc.get("eps",0)/25*100,
                sc.get("roic",0)/20*100,
                sc.get("fcf",0)/15*100,
                sc.get("dilution",0)/15*100,
                sc.get("momentum",0)/15*100,
                sc.get("rsi",0)/10*100,
            ]
            vals += [vals[0]]  # close the polygon
            fig.add_trace(go.Scatterpolar(
                r=vals,
                theta=categories + [categories[0]],
                fill="toself",
                name=s["ticker"],
                line_color=color,
                fillcolor=color,
                opacity=0.25,
            ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100], gridcolor="#dde1eb", tickfont=dict(color="#555")),
                angularaxis=dict(gridcolor="#dde1eb", tickfont=dict(color="#333")),
                bgcolor="#f8f9fc",
            ),
            title=dict(text=title, font=dict(color="#1a1a2e")),
            height=420,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            font_color="#1a1a2e",
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, font=dict(color="#333")),
        )
        return fig

    r1, r2 = st.columns(2)
    with r1:
        if us_top:
            st.plotly_chart(radar_chart(us_top, "🇺🇸 US Top 5"), use_container_width=True)
    with r2:
        if jp_top:
            st.plotly_chart(radar_chart(jp_top, "🇯🇵 Japan Top 5"), use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: STOCK DETAIL
# ──────────────────────────────────────────────────────────────────────────────
with tab_detail:
    all_tickers = {f"{s['ticker']} — {s.get('name','')}": s for s in all_stocks}
    selected = st.selectbox("銘柄を選択", list(all_tickers.keys()))
    s = all_tickers[selected]
    sc = s["scores"]

    # Real-time quote from Finnhub
    fh = get_finnhub_quote(s["ticker"], finnhub_key)
    rt_price  = (fh.get("c") if fh and fh.get("c") else s.get("price")) or 0
    rt_open   = fh.get("o") if fh else None
    rt_high   = fh.get("h") if fh else None
    rt_low    = fh.get("l") if fh else None
    rt_prev   = fh.get("pc") if fh else None
    rt_change = fh.get("d") if fh else None
    rt_pct    = fh.get("dp") if fh else None

    color = score_color(s["total_score"])

    st.markdown(f"## {s.get('name', s['ticker'])} `{s['ticker']}`")
    st.markdown(f"*{s.get('sector','N/A')} | {s.get('industry','N/A')} | {s.get('market','N/A')}*")

    # top metrics row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("現在値", f"{rt_price:.2f}" if rt_price else "N/A",
              f"{rt_change:+.2f}" if rt_change else None)
    m2.metric("変化率", f"{rt_pct:+.2f}%" if rt_pct else "N/A")
    m3.metric("時価総額", fmt_large(s.get("market_cap")))
    m4.metric("PER (実績)", fmt_num(s.get("pe_trailing")))
    m5.metric("PER (予想)", fmt_num(s.get("pe_forward")))
    m6.metric(f"総合スコア /100",
              s["total_score"],
              delta=None)

    # ── Fundamental reasoning ─────────────────────────────────────────────────
    def fund_reasons(d: dict) -> list[tuple[str, str, str]]:
        """Return list of (criterion, verdict_emoji, explanation) for each criterion."""
        items = []

        # EPS
        eps = d.get("eps_cagr")
        if eps is None:
            items.append(("EPS 多年成長", "⚪", "データ取得不可。直近の決算資料を確認してください。"))
        elif eps >= 0.20:
            items.append(("EPS 多年成長", "🟢", f"年率 {eps*100:.1f}% の力強い複利成長。プライシングパワーまたはボリューム拡大が持続していることを示します。"))
        elif eps >= 0.10:
            items.append(("EPS 多年成長", "🟡", f"年率 {eps*100:.1f}% と安定した成長。モート維持を示しますが、加速余地を確認してください。"))
        else:
            items.append(("EPS 多年成長", "🔴", f"年率 {eps*100:.1f}% と低成長。コスト圧力または競争激化の可能性があります。"))

        # ROIC
        roic = d.get("roic")
        if roic is None:
            items.append(("ROIC", "⚪", "データ取得不可。投下資本利益率は競争優位の最重要指標です。"))
        elif roic >= 0.25:
            items.append(("ROIC", "🟢", f"ROIC {roic*100:.1f}%。資本コスト（WACC 8–10%）を大幅に超過しており、持続的な経済的付加価値（EVA）を創出しています。"))
        elif roic >= 0.15:
            items.append(("ROIC", "🟡", f"ROIC {roic*100:.1f}%。資本コストを上回っているが、業界トップとの差が競争優位の持続性を左右します。"))
        else:
            items.append(("ROIC", "🔴", f"ROIC {roic*100:.1f}%。資本コストに近く、実質的な価値創造が限定的です。"))

        # FCF quality
        fcf_r = d.get("fcf_to_netinc")
        if fcf_r is None:
            items.append(("FCF 品質", "⚪", "データ取得不可。FCF/純利益比は利益の現金化率を示す重要指標です。"))
        elif fcf_r >= 0.85:
            items.append(("FCF 品質", "🟢", f"FCF/純利益 = {fcf_r:.2f}。利益のほぼ全額が現金として回収されており、会計利益への依存度が低い優良な利益品質です。"))
        elif fcf_r >= 0.60:
            items.append(("FCF 品質", "🟡", f"FCF/純利益 = {fcf_r:.2f}。利益の現金化率はまずまずですが、運転資本動向や設備投資サイクルを継続監視してください。"))
        else:
            items.append(("FCF 品質", "🔴", f"FCF/純利益 = {fcf_r:.2f}。利益に対してFCFが乖離しています。減価償却の過少計上や売掛金増加がないか要確認です。"))

        # Dilution
        dil = d.get("dilution_annual")
        if dil is None:
            items.append(("希薄化", "⚪", "データ取得不可。発行済み株式数の推移を有価証券報告書で確認してください。"))
        elif dil <= -0.005:
            items.append(("希薄化", "🟢", f"年率 {dil*100:.2f}% の自社株買い（株数減少）。株主価値への還元姿勢が明確で、1株当たり価値が自動的に向上します。"))
        elif dil <= 0.01:
            items.append(("希薄化", "🟡", f"年率 {dil*100:.2f}% とほぼ横ばい。ストックオプション費用は発生しているが許容範囲内です。"))
        else:
            items.append(("希薄化", "🔴", f"年率 {dil*100:.2f}% の株式希薄化。成長投資のための増資か、SBC（株式報酬）の水準を確認してください。"))

        # Revenue growth + margins (TAM / moat proxy)
        rev_g = d.get("revenue_growth")
        op_m  = d.get("op_margin")
        gm    = d.get("gross_margin")
        if rev_g is not None and op_m is not None:
            if rev_g >= 0.15 and op_m >= 0.20:
                items.append(("TAM・競争優位", "🟢", f"売上成長率 {rev_g*100:.1f}%、営業利益率 {op_m*100:.1f}%。高成長×高マージンはまだTAMが広く、価格支配力（moat）が維持されているサインです。"))
            elif rev_g >= 0.08:
                items.append(("TAM・競争優位", "🟡", f"売上成長率 {rev_g*100:.1f}%。成熟フェーズに近づいている可能性があります。隣接市場への展開戦略（新製品・地理拡大）を確認してください。"))
            else:
                items.append(("TAM・競争優位", "🔴", f"売上成長率 {rev_g*100:.1f}%。市場飽和またはシェア喪失の可能性。差別化要因の再評価が必要です。"))
        elif gm is not None:
            g_lbl = "🟢" if gm >= 0.50 else ("🟡" if gm >= 0.30 else "🔴")
            items.append(("TAM・競争優位", g_lbl, f"粗利益率 {gm*100:.1f}%。{'高粗利益率はソフトウェア・プラットフォーム型のスケーラブルなビジネスモデルを示唆します。' if gm>=0.50 else '製造業・流通業として標準的な水準です。'}"))

        return items

    # ── Entry point suggestion ────────────────────────────────────────────────
    def entry_suggestion(d: dict) -> dict:
        """Calculate entry zones from technicals. Returns dict with zones and verdict."""
        price   = d.get("price") or 0
        sma50   = d.get("sma50")
        sma200  = d.get("sma200")
        rsi     = d.get("rsi")
        hi52    = d.get("52w_high")
        lo52    = d.get("52w_low")
        mom     = d.get("momentum_3m")
        hist_ph = d.get("price_history")  # pandas Series

        result = {
            "zones": [],       # list of {"label", "price_low", "price_high", "reason", "priority"}
            "verdict": "",
            "risk_note": "",
            "stop_loss": None,
        }

        if not price:
            result["verdict"] = "⚪ 価格データなし"
            return result

        # ── Zone 1: SMA50 pullback ──────────────────────────────────────
        if sma50:
            z_low  = sma50 * 0.98
            z_high = sma50 * 1.02
            if price > sma50 * 1.05:
                result["zones"].append({
                    "label": "SMA50 押し目",
                    "price_low": z_low, "price_high": z_high,
                    "reason": "上昇トレンド中の一時的な調整でSMA50付近に戻った場面は定番の押し目買いゾーン。",
                    "priority": "A",
                })

        # ── Zone 2: SMA200 support ──────────────────────────────────────
        if sma200:
            z_low  = sma200 * 0.97
            z_high = sma200 * 1.03
            if price > sma200:
                result["zones"].append({
                    "label": "SMA200 サポート",
                    "price_low": z_low, "price_high": z_high,
                    "reason": "長期上昇トレンドの根幹ライン。機関投資家が重視するサポートで、大きく押した際の買い場。",
                    "priority": "B",
                })

        # ── Zone 3: 52-week low rebound zone ───────────────────────────
        if hi52 and lo52 and hi52 > lo52:
            fib382 = hi52 - (hi52 - lo52) * 0.382
            fib500 = hi52 - (hi52 - lo52) * 0.500
            result["zones"].append({
                "label": "フィボナッチ 38.2–50%",
                "price_low": round(fib500, 2), "price_high": round(fib382, 2),
                "reason": f"52週レンジ ({lo52:.2f}–{hi52:.2f}) に対してフィボナッチ38.2%–50%押しのゾーン。中長期トレンド継続時の押し目として機能しやすい。",
                "priority": "B",
            })

        # ── Zone 4: RSI oversold bounce ─────────────────────────────────
        if rsi is not None and rsi < 40 and price:
            # estimate price if RSI were at 50 (rough linear approx)
            result["zones"].append({
                "label": "RSI 回復待ち (現在の水準)",
                "price_low": price * 0.97, "price_high": price * 1.01,
                "reason": f"現在RSI={rsi:.1f}と売られすぎ圏。ファンダが良好な銘柄のRSI低水準は短期的なエントリー好機になりやすい。RSI 45超えを確認後にエントリーするのが安全。",
                "priority": "A",
            })

        # ── ATR-based stop loss ──────────────────────────────────────────
        if hist_ph is not None and len(hist_ph) > 20:
            atr_approx = hist_ph.diff().abs().rolling(14).mean().iloc[-1]
            result["stop_loss"] = round(price - atr_approx * 2, 2)
        elif lo52:
            result["stop_loss"] = round(lo52 * 0.97, 2)

        # ── Overall verdict ──────────────────────────────────────────────
        if rsi is not None and sma50 and sma200:
            above50  = price > sma50
            above200 = price > sma200
            rsi_ok   = 40 <= rsi <= 70

            if above200 and above50 and rsi_ok and (mom or 0) > 0:
                result["verdict"] = "🟢 買い検討圏 — トレンド・モメンタム・RSI すべて良好"
            elif above200 and rsi_ok:
                result["verdict"] = "🟡 条件付き検討 — 長期トレンドは維持、短期調整中"
            elif not above200:
                result["verdict"] = "🔴 様子見推奨 — SMA200 を下回っており長期トレンドが崩れている"
            elif rsi > 75:
                result["verdict"] = "🟡 過熱圏 — ファンダは良好だが短期的に買われすぎ。押し目を待ちたい"
            else:
                result["verdict"] = "⚪ 中立 — 追加シグナルを待ってください"
        else:
            result["verdict"] = "⚪ テクニカルデータ不足 — 手動で確認してください"

        if d.get("beta") and d["beta"] > 1.3:
            result["risk_note"] = f"⚠️ Beta={d['beta']:.2f} と高め。市場全体の下落局面では株価変動が増幅しやすいため、ポジションサイズに注意してください。"

        return result

    # ── render fund + tech ────────────────────────────────────────────────────
    st.markdown("---")
    col_fund, col_tech = st.columns([1, 1])

    with col_fund:
        st.markdown("### 📋 ファンダメンタル")
        fd_data = {
            "EPS CAGR (多年)":  fmt_pct(s.get("eps_cagr")),
            "ROIC":              fmt_pct(s.get("roic")),
            "FCF / 純利益":      fmt_num(s.get("fcf_to_netinc")),
            "希薄化率 / 年":     fmt_pct(s.get("dilution_annual")),
            "売上成長率":        fmt_pct(s.get("revenue_growth")),
            "粗利益率":          fmt_pct(s.get("gross_margin")),
            "営業利益率":        fmt_pct(s.get("op_margin")),
            "フリーCF":          fmt_large(s.get("fcf")),
            "52週高値":          fmt_num(s.get("52w_high"), 2),
            "52週安値":          fmt_num(s.get("52w_low"), 2),
            "Beta":              fmt_num(s.get("beta"), 2),
        }
        for k, v in fd_data.items():
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{k}**")
            c2.markdown(v)

    with col_tech:
        st.markdown("### 📐 テクニカル")
        td_data = {
            "RSI (14)":       fmt_num(s.get("rsi")),
            "SMA 50":         fmt_num(s.get("sma50"), 2),
            "SMA 200":        fmt_num(s.get("sma200"), 2),
            "3ヶ月騰落率":    fmt_pct(s.get("momentum_3m")),
            "52週レンジ位置": fmt_pct(s.get("range_pct")),
        }
        for k, v in td_data.items():
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{k}**")
            c2.markdown(v)

        st.markdown("##### スコア内訳")
        score_items = [
            ("EPS 多年成長", sc.get("eps",0), 25),
            ("ROIC",         sc.get("roic",0), 20),
            ("FCF 品質",     sc.get("fcf",0), 15),
            ("希薄化抑制",   sc.get("dilution",0), 15),
            ("モメンタム",   sc.get("momentum",0), 15),
            ("RSI / MA",     sc.get("rsi",0), 10),
        ]
        total_sc = sc.get("total", 0)
        tc = score_color(total_sc)
        tb = score_bg(total_sc)
        bars_html = "".join(score_bar(lbl, sv, mx) for lbl, sv, mx in score_items)
        bars_html += (
            f'<div style="background:{tb};border:2px solid {tc};border-radius:8px;'
            f'padding:10px 14px;margin-top:10px;display:flex;'
            f'justify-content:space-between;align-items:center">'
            f'<span style="font-weight:700;color:#1a1a2e;font-size:0.9rem">総合スコア</span>'
            f'<span style="font-size:1.6rem;font-weight:800;color:{tc}">{total_sc}'
            f'<span style="font-size:0.8rem;color:#999;font-weight:400">/100</span>'
            f'</span></div>'
        )
        st_html.html(
            f'<div style="font-family:sans-serif">{bars_html}</div>',
            height=len(score_items) * 62 + 80,
            scrolling=False,
        )

    # ── Fundamental reasons ───────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("💡 ファンダメンタル 評価理由")
    reasons = fund_reasons(s)
    for criterion, emoji, explanation in reasons:
        bg = {"🟢": "#f0faf5", "🟡": "#fffbeb", "🔴": "#fff5f5", "⚪": "#f8f9fc"}[emoji]
        border = {"🟢": "#0a7c42", "🟡": "#b07c00", "🔴": "#c0392b", "⚪": "#aaa"}[emoji]
        st.markdown(
            f"""<div style="background:{bg};border-left:4px solid {border};border-radius:4px;
                           padding:10px 14px;margin-bottom:8px">
              <div style="font-weight:600;color:#1a1a2e;margin-bottom:2px">{emoji} {criterion}</div>
              <div style="font-size:0.88rem;color:#333;line-height:1.5">{explanation}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # ── Entry point suggestion ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🎯 エントリーポイント サジェスト")

    entry = entry_suggestion(s)
    price_now = s.get("price") or 0

    # verdict banner
    verdict_bg = "#f0faf5" if "🟢" in entry["verdict"] else \
                 "#fffbeb" if "🟡" in entry["verdict"] else \
                 "#fff5f5" if "🔴" in entry["verdict"] else "#f8f9fc"
    st.markdown(
        f"""<div style="background:{verdict_bg};border-radius:8px;padding:14px 18px;
                       margin-bottom:16px;font-size:1.05rem;font-weight:600;color:#1a1a2e">
          {entry['verdict']}
        </div>""",
        unsafe_allow_html=True,
    )

    if entry["zones"]:
        zone_cols = st.columns(len(entry["zones"]))
        for col, zone in zip(zone_cols, entry["zones"]):
            dist_pct = (zone["price_low"] / price_now - 1) * 100 if price_now else 0
            priority_color = "#0a7c42" if zone["priority"] == "A" else "#1a56db"
            with col:
                st.markdown(
                    f"""<div style="background:#ffffff;border:1px solid #e4e8f0;border-radius:8px;
                                   padding:14px;height:100%">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <span style="font-weight:700;color:#1a1a2e;font-size:0.9rem">{zone['label']}</span>
                        <span style="background:{priority_color};color:#fff;border-radius:4px;
                                     padding:1px 7px;font-size:0.75rem;font-weight:700">優先度{zone['priority']}</span>
                      </div>
                      <div style="font-size:1.1rem;font-weight:700;color:#1a56db;margin-bottom:4px">
                        {zone['price_low']:.2f} – {zone['price_high']:.2f}
                      </div>
                      <div style="font-size:0.78rem;color:#888;margin-bottom:6px">
                        現在値比 {dist_pct:+.1f}%
                      </div>
                      <div style="font-size:0.82rem;color:#555;line-height:1.45">{zone['reason']}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
    else:
        st.info("テクニカルデータが不足しているため、エントリーゾーンを算出できませんでした。")

    # stop loss + risk note
    sl_col, rn_col = st.columns([1, 2])
    with sl_col:
        if entry["stop_loss"]:
            sl_pct = (entry["stop_loss"] / price_now - 1) * 100 if price_now else 0
            st.markdown(
                f"""<div style="background:#fff5f5;border:1px solid #f5c6c6;border-radius:8px;
                               padding:12px 16px;margin-top:12px">
                  <div style="font-weight:700;color:#c0392b;margin-bottom:2px">🛑 ストップロス目安</div>
                  <div style="font-size:1.3rem;font-weight:700;color:#c0392b">{entry['stop_loss']:.2f}</div>
                  <div style="font-size:0.8rem;color:#999">現在値比 {sl_pct:.1f}% (ATR×2 基準)</div>
                </div>""",
                unsafe_allow_html=True,
            )
    with rn_col:
        if entry["risk_note"]:
            st.markdown(
                f"""<div style="background:#fffbeb;border:1px solid #f5e0a0;border-radius:8px;
                               padding:12px 16px;margin-top:12px;font-size:0.88rem;color:#555">
                  {entry['risk_note']}
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div style='font-size:0.75rem;color:#aaa;margin-top:8px'>"
        "※ 上記はアルゴリズムによる参考情報です。投資判断は自己責任でお願いします。"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Price Chart ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📈 チャート")
    period_sel = st.select_slider("期間", options=["3mo","6mo","1y","2y","5y"], value="1y")

    @st.cache_data(ttl=300)
    def get_history(ticker, period):
        return yf.Ticker(ticker).history(period=period)

    hist = get_history(s["ticker"], period_sel)
    if hist is not None and not hist.empty:
        rows_sub = 2 if show_volume else 1
        row_heights = [0.75, 0.25] if show_volume else [1.0]
        fig = make_subplots(rows=rows_sub, cols=1, shared_xaxes=True,
                            row_heights=row_heights, vertical_spacing=0.04)

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"],
            name="価格", increasing_line_color="#2ecc71",
            decreasing_line_color="#e74c3c",
        ), row=1, col=1)

        if show_sma:
            for period_sma, color_sma, name_sma in [(50,"#1a56db","SMA50"),(200,"#e67e22","SMA200")]:
                if len(hist) >= period_sma:
                    sma = hist["Close"].rolling(period_sma).mean()
                    fig.add_trace(go.Scatter(x=hist.index, y=sma, name=name_sma,
                                             line=dict(color=color_sma, width=1.5),
                                             opacity=0.9), row=1, col=1)

        # Entry zones as horizontal bands
        entry_for_chart = entry_suggestion(s)
        for zone in entry_for_chart["zones"][:2]:  # top 2 zones only
            fig.add_hrect(
                y0=zone["price_low"], y1=zone["price_high"],
                fillcolor="#1a56db", opacity=0.08,
                line_width=0, row=1, col=1,
                annotation_text=zone["label"],
                annotation_position="right",
                annotation_font_size=10,
                annotation_font_color="#1a56db",
            )

        if entry_for_chart["stop_loss"]:
            fig.add_hline(
                y=entry_for_chart["stop_loss"],
                line_dash="dot", line_color="#e74c3c", line_width=1.2,
                annotation_text="SL", annotation_font_color="#e74c3c",
                row=1, col=1,
            )

        if show_volume and "Volume" in hist.columns:
            fig.add_trace(go.Bar(
                x=hist.index, y=hist["Volume"], name="出来高",
                marker_color="#1a56db", opacity=0.3,
            ), row=2, col=1)

        fig.update_layout(
            height=520,
            xaxis_rangeslider_visible=False,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8f9fc",
            font_color="#1a1a2e",
            legend=dict(orientation="h"),
        )
        fig.update_xaxes(gridcolor="#dde1eb", linecolor="#ccc")
        fig.update_yaxes(gridcolor="#dde1eb", linecolor="#ccc")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("チャートデータを取得できませんでした。")

    if s.get("description"):
        with st.expander("企業概要"):
            st.write(s["description"] + "...")


# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: COMPARISON CHART
# ──────────────────────────────────────────────────────────────────────────────
with tab_compare:
    st.subheader("📊 パフォーマンス比較")

    all_ticker_opts = [f"{s['ticker']} ({s.get('name','')})" for s in all_stocks]
    default_sel = all_ticker_opts[:5]
    compare_sel = st.multiselect("比較銘柄 (最大10)", all_ticker_opts, default=default_sel, max_selections=10)
    compare_period = st.select_slider("期間 ", options=["3mo","6mo","1y","2y"], value="1y", key="cmp_period")

    if compare_sel:
        tickers_cmp = [x.split(" ")[0] for x in compare_sel]

        @st.cache_data(ttl=300)
        def get_normalized_prices(tickers, period):
            dfs = {}
            for tk in tickers:
                h = yf.Ticker(tk).history(period=period)
                if h is not None and not h.empty:
                    dfs[tk] = h["Close"] / h["Close"].iloc[0] * 100
            return dfs

        norm_prices = get_normalized_prices(tuple(tickers_cmp), compare_period)

        fig2 = go.Figure()
        palette = ["#00d26a","#60b0f0","#f0c040","#e080e0","#ff8c42",
                   "#7eca9c","#80c0ff","#ffd060","#e0a0e0","#ffb080"]
        for i, (tk, series) in enumerate(norm_prices.items()):
            name_label = next((s.get("name", tk) for s in all_stocks if s["ticker"]==tk), tk)
            fig2.add_trace(go.Scatter(
                x=series.index, y=series.values,
                name=f"{tk} ({name_label})",
                line=dict(color=palette[i % len(palette)], width=2),
            ))

        fig2.add_hline(y=100, line_dash="dash", line_color="#aaa", annotation_text="基準 (100)")
        fig2.update_layout(
            title=dict(text="正規化株価推移 (初期値=100)", font=dict(color="#1a1a2e")),
            height=480,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8f9fc",
            font_color="#1a1a2e",
            xaxis=dict(gridcolor="#dde1eb", linecolor="#ccc"),
            yaxis=dict(gridcolor="#dde1eb", linecolor="#ccc", title="正規化価格"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, font=dict(color="#333")),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Metrics comparison table
        st.markdown("##### 指標比較")
        cmp_rows = []
        for tk in tickers_cmp:
            s_data = next((s for s in all_stocks if s["ticker"]==tk), None)
            if s_data:
                cmp_rows.append({
                    "ティッカー": tk,
                    "企業名": s_data.get("name", tk),
                    "スコア": s_data["total_score"],
                    "EPS CAGR": fmt_pct(s_data.get("eps_cagr")),
                    "ROIC": fmt_pct(s_data.get("roic")),
                    "FCF/利益": fmt_num(s_data.get("fcf_to_netinc")),
                    "希薄化/年": fmt_pct(s_data.get("dilution_annual")),
                    "RSI": fmt_num(s_data.get("rsi")),
                    "3M騰落": fmt_pct(s_data.get("momentum_3m")),
                    "PER予想": fmt_num(s_data.get("pe_forward")),
                })

        if cmp_rows:
            st.dataframe(pd.DataFrame(cmp_rows), use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 4: SMT 米国モメンタムファンド トラッカー
# ──────────────────────────────────────────────────────────────────────────────
with tab_smt:
    st.subheader("🔄 SMT 米国モメンタムファンド — 構成銘柄トラッカー")
    st.markdown(
        "構成21銘柄の6ヶ月パフォーマンスで上位6銘柄を選出。"
        "3ヶ月ごとの入れ替え判断を補助するため、3M・6Mパフォーマンスとエントリー圏を表示します。"
    )

    # ── 構成21銘柄（2025年度モメンタムファンド典型構成） ──────────────────────
    # 出典: SMT米国株式モメンタムファンド 月次レポート 2026年6月
    # 短期(6M)上位7 / 中期(12M)上位7 / 長期(36M)上位7 = 計21銘柄
    SMT_CONSTITUENTS = [
        # ── 短期モメンタム (6ヶ月) ──────────────────────────────────────────
        {"ticker": "MU",    "name": "マイクロン・テクノロジー",        "period": "6M"},
        {"ticker": "RKLB",  "name": "ロケット・ラボ",                 "period": "6M"},
        {"ticker": "WDC",   "name": "ウエスタンデジタル",             "period": "6M"},
        {"ticker": "STX",   "name": "シーゲイト・テクノロジー",       "period": "6M"},
        {"ticker": "DELL",  "name": "デル・テクノロジーズ",           "period": "6M"},
        {"ticker": "CIEN",  "name": "シエナ",                        "period": "6M"},
        {"ticker": "INTC",  "name": "インテル",                      "period": "6M"},
        # ── 中期モメンタム (12ヶ月) ─────────────────────────────────────────
        {"ticker": "BE",    "name": "ブルーム・エナジー",             "period": "12M"},
        {"ticker": "LITE",  "name": "ルメンタム・ホールディングス",   "period": "12M"},
        {"ticker": "IREN",  "name": "IREN",                          "period": "12M"},
        {"ticker": "SATS",  "name": "エコスター",                    "period": "12M"},
        {"ticker": "ASTS",  "name": "ASTスペースモバイル",           "period": "12M"},
        {"ticker": "COHR",  "name": "コヒレント",                    "period": "12M"},
        {"ticker": "TER",   "name": "テラダイン",                    "period": "12M"},
        # ── 長期モメンタム (36ヶ月) ─────────────────────────────────────────
        {"ticker": "CVNA",  "name": "カーバナ",                      "period": "36M"},
        {"ticker": "APP",   "name": "アップラビン",                  "period": "36M"},
        {"ticker": "CRDO",  "name": "クレド・テクノロジー",          "period": "36M"},
        {"ticker": "VRT",   "name": "バーティブ・ホールディングス",  "period": "36M"},
        {"ticker": "FIX",   "name": "コンフォート・システムズUSA",   "period": "36M"},
        {"ticker": "PLTR",  "name": "バランティア・テクノロジーズ",  "period": "36M"},
        {"ticker": "HOOD",  "name": "ロビンフッド・マーケッツ",      "period": "36M"},
    ]

    @st.cache_data(ttl=300, show_spinner=False)
    def load_smt_data() -> list[dict]:
        tickers = [c["ticker"] for c in SMT_CONSTITUENTS]
        prog = st.progress(0, text="SMT価格データを一括取得中...")

        # 21銘柄を1回のHTTPリクエストでまとめて取得
        try:
            raw = yf.download(
                tickers, period="1y", interval="1d",
                group_by="ticker", auto_adjust=True,
                progress=False, threads=True,
            )
        except Exception:
            raw = None

        prog.progress(0.8, text="テクニカル指標を計算中...")

        def _get_closes(ticker):
            if raw is None:
                return pd.Series(dtype=float)
            try:
                if len(tickers) == 1:
                    return raw["Close"].dropna()
                # MultiIndex: (ticker, metric)
                if ticker in raw.columns.get_level_values(0):
                    return raw[ticker]["Close"].dropna()
            except Exception:
                pass
            return pd.Series(dtype=float)

        def _perf(closes, n):
            return (closes.iloc[-1] / closes.iloc[-n] - 1) if len(closes) > n else None

        results = []
        for c in SMT_CONSTITUENTS:
            closes = _get_closes(c["ticker"])
            if closes.empty:
                results.append({**c, "perf_6m": None, "perf_3m": None,
                                "perf_1m": None, "price": None,
                                "rsi": None, "sma50": None, "sma200": None,
                                "entry_rank": 3, "history": None})
                continue
            try:
                price  = float(closes.iloc[-1])
                p6     = _perf(closes, 126)
                p3     = _perf(closes, 63)
                p1     = _perf(closes, 21)

                delta  = closes.diff()
                gain   = delta.clip(lower=0).rolling(14).mean()
                loss   = (-delta.clip(upper=0)).rolling(14).mean()
                rsi    = float((100 - 100 / (1 + gain / loss.replace(0, np.nan))).iloc[-1])
                sma50  = float(closes.rolling(50).mean().iloc[-1])
                sma200 = float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None

                above200 = sma200 and price > sma200
                rsi_ok   = 40 <= rsi <= 70
                if above200 and price > sma50 and rsi_ok and (p3 or 0) > 0:
                    er = 0
                elif above200 and rsi_ok:
                    er = 1
                elif above200:
                    er = 2
                else:
                    er = 3

                results.append({**c, "perf_6m": p6, "perf_3m": p3, "perf_1m": p1,
                                "price": price, "rsi": rsi, "sma50": sma50,
                                "sma200": sma200, "entry_rank": er, "history": closes})
            except Exception:
                results.append({**c, "perf_6m": None, "perf_3m": None,
                                "perf_1m": None, "price": None,
                                "rsi": None, "sma50": None, "sma200": None,
                                "entry_rank": 3, "history": None})

        prog.empty()
        return sorted(results, key=lambda x: x["perf_6m"] if x["perf_6m"] is not None else -99, reverse=True)

    # session_state でデータ保持 — ボタンまたはサイドバーリフレッシュ時のみ再取得
    smt_hdr_col, smt_btn_col = st.columns([5, 1])
    with smt_btn_col:
        smt_refresh = st.button("🔄 更新", key="smt_fetch", use_container_width=True)
    with smt_hdr_col:
        if "_smt_at" in st.session_state:
            st.caption(f"最終取得: {st.session_state['_smt_at']}")

    if smt_refresh or refresh:
        st.session_state.pop("smt_data", None)
        load_smt_data.clear()

    if "smt_data" not in st.session_state:
        with st.spinner("SMT構成銘柄データ取得中... (約30秒)"):
            st.session_state["smt_data"] = load_smt_data()
            st.session_state["_smt_at"] = datetime.now().strftime("%m/%d %H:%M")

    smt_data = st.session_state["smt_data"]

    # ── 上位6銘柄 ─────────────────────────────────────────────────────────────
    top6         = [d for d in smt_data if d["perf_6m"] is not None][:6]
    top6_tickers = {d["ticker"] for d in top6}

    ENTRY_COLORS = {0: "#0a7c42", 1: "#b07c00", 2: "#b07c00", 3: "#c0392b"}
    ENTRY_BGS    = {0: "#e8f8f0", 1: "#fef9ec", 2: "#fef9ec", 3: "#fdf0ef"}
    ENTRY_LABELS = {0: "🟢 買い圏", 1: "🟡 条件付き", 2: "🟡 長期OK", 3: "🔴 様子見"}

    # ── リバランス日トラッカー ────────────────────────────────────────────────
    from datetime import date, timedelta
    import math

    today = date.today()
    # 四半期基準日（3/末・6/末・9/末・12/末の翌営業日を簡易計算）
    quarter_ends = [date(today.year, m, 1) for m in [3, 6, 9, 12]]
    quarter_ends += [date(today.year + 1, 3, 1)]
    next_rebal = min((d for d in quarter_ends if d > today), default=None)
    days_to_rebal = (next_rebal - today).days if next_rebal else None

    rb_col1, rb_col2, rb_col3 = st.columns(3)
    with rb_col1:
        st.metric("次回リバランス目安", str(next_rebal) if next_rebal else "N/A",
                  f"あと {days_to_rebal} 日" if days_to_rebal else None)
    with rb_col2:
        green_count = sum(1 for d in top6 if d["entry_rank"] == 0)
        st.metric("Top6 うち🟢買い圏", f"{green_count} / 6銘柄")
    with rb_col3:
        avg_6m = np.mean([d["perf_6m"] for d in top6 if d["perf_6m"] is not None])
        st.metric("Top6 平均6Mリターン", f"{avg_6m*100:+.1f}%" if not np.isnan(avg_6m) else "N/A")

    st.markdown("---")

    # ── TOP 6 カード ──────────────────────────────────────────────────────────
    st.markdown("### 🥇 6ヶ月パフォーマンス 上位6銘柄（保有候補）")
    st.caption("エントリー圏 🟢 の銘柄が買い増し・新規エントリーの優先候補。⚠️ RSI>70 は過熱注意。")

    # モバイルでは st.columns(6) が潰れるため、
    # HTML グリッドで直接レンダリングする
    top6_html_cards = ""
    for d in top6:
        er    = d["entry_rank"]
        ec    = ENTRY_COLORS[er]
        eb    = ENTRY_BGS[er]
        el    = ENTRY_LABELS[er]
        p6    = d["perf_6m"] or 0
        p3    = d["perf_3m"] or 0
        p1    = d["perf_1m"] or 0
        rsi_v = d["rsi"]
        price = d["price"] or 0

        p6_color  = "#0a7c42" if p6 > 0 else "#c0392b"
        p3_color  = "#0a7c42" if p3 > 0 else "#c0392b"
        p3_arrow  = "▲" if p3 > 0 else "▼"
        p1_color  = "#0a7c42" if p1 > 0 else "#c0392b"
        rsi_str   = f"{rsi_v:.0f}" if rsi_v else "N/A"
        rsi_color = "#c0392b" if rsi_v and rsi_v > 70 else "#1a1a2e"
        rsi_warn  = " ⚠️" if rsi_v and rsi_v > 70 else ""

        glow = "box-shadow:0 0 0 3px #b7f5d8,0 0 12px 4px #4ade80;" if er == 0 else ""
        top6_html_cards += f"""
        <div style="background:#fff;border-radius:12px;padding:14px;
                    border:1px solid #e4e8f0;border-top:4px solid {ec};
                    box-shadow:0 1px 4px rgba(0,0,0,0.06);{glow}">
          <div style="font-size:1rem;font-weight:800;color:#1a1a2e">{d['ticker']}</div>
          <div style="font-size:0.68rem;color:#888;margin-bottom:6px;white-space:nowrap;
                      overflow:hidden;text-overflow:ellipsis">{d['name']}</div>
          <div style="background:{eb};color:{ec};border-radius:5px;padding:3px 7px;
                      font-size:0.7rem;font-weight:700;display:inline-block;
                      margin-bottom:8px">{el}</div>
          <div style="margin-bottom:8px">
            <div style="font-size:0.65rem;color:#999">6ヶ月リターン</div>
            <div style="font-size:1.5rem;font-weight:800;color:{p6_color};line-height:1.1">
              {p6*100:+.1f}%</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;
                      font-size:0.75rem;margin-bottom:8px">
            <div style="background:#f8f9fc;border-radius:4px;padding:4px 6px">
              <div style="color:#999;font-size:0.62rem">3M</div>
              <div style="color:{p3_color};font-weight:700">{p3_arrow}{abs(p3)*100:.1f}%</div>
            </div>
            <div style="background:#f8f9fc;border-radius:4px;padding:4px 6px">
              <div style="color:#999;font-size:0.62rem">1M</div>
              <div style="color:{p1_color};font-weight:700">{p1*100:+.1f}%</div>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.75rem;
                      padding-top:6px;border-top:1px solid #f0f0f0">
            <div><span style="color:#999">RSI </span>
              <span style="font-weight:700;color:{rsi_color}">{rsi_str}{rsi_warn}</span>
            </div>
            <div><span style="color:#999">$ </span>
              <span style="font-weight:700">{price:.1f}</span>
            </div>
          </div>
        </div>"""

    # PC: 6列 / モバイル: 2列 — CSS grid で自動切替
    st_html.html(f"""
    <div style="font-family:sans-serif">
      <style>
        .top6-grid {{
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 10px;
        }}
        @media (max-width: 768px) {{
          .top6-grid {{
            grid-template-columns: repeat(2, 1fr);
          }}
        }}
      </style>
      <div class="top6-grid">{top6_html_cards}</div>
    </div>
    """, height=700, scrolling=True)

    # ── 6M パフォーマンス 横棒グラフ（全21銘柄） ──────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 全21銘柄 パフォーマンス比較")

    sorted_all = sorted(smt_data, key=lambda x: x["perf_6m"] if x["perf_6m"] is not None else -99, reverse=True)
    bar_tickers = [d["ticker"] for d in sorted_all]
    bar_6m      = [(d["perf_6m"] or 0)*100 for d in sorted_all]
    bar_3m      = [(d["perf_3m"] or 0)*100 for d in sorted_all]
    bar_colors  = [ENTRY_COLORS[d["entry_rank"]] for d in sorted_all]
    bar_opacity = [1.0 if t in top6_tickers else 0.45 for t in bar_tickers]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="6Mリターン",
        x=bar_tickers, y=bar_6m,
        marker_color=bar_colors,
        marker_opacity=bar_opacity,
        text=[f"{v:+.1f}%" for v in bar_6m],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig_bar.add_trace(go.Scatter(
        name="3Mリターン",
        x=bar_tickers, y=bar_3m,
        mode="markers",
        marker=dict(symbol="diamond", size=10, color="#1a56db",
                    line=dict(width=1.5, color="#fff")),
    ))
    fig_bar.add_hline(y=0, line_color="#ccc", line_width=1)

    # 上位6境界線
    if len(sorted_all) >= 6:
        fig_bar.add_vline(
            x=5.5, line_dash="dash", line_color="#0a7c42", line_width=2,
            annotation_text="↑ 上位6銘柄", annotation_position="top right",
            annotation_font_color="#0a7c42",
        )

    fig_bar.update_layout(
        height=420,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8f9fc",
        font_color="#1a1a2e",
        xaxis=dict(gridcolor="#dde1eb"),
        yaxis=dict(gridcolor="#dde1eb", title="リターン (%)"),
        legend=dict(orientation="h", y=1.08),
        bargap=0.3,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── 正規化チャート: Top6 vs 残り（6M） ────────────────────────────────────
    st.markdown("### 📈 Top6 パフォーマンス推移（6ヶ月）")

    fig_line = go.Figure()
    palette6 = ["#1a56db","#0a7c42","#b07c00","#8b5cf6","#e74c3c","#0891b2"]
    for i, d in enumerate(top6):
        h = d.get("history")
        if h is not None and len(h) >= 126:
            series = h.iloc[-126:]
            norm   = series / series.iloc[0] * 100
            er = d["entry_rank"]
            fig_line.add_trace(go.Scatter(
                x=norm.index, y=norm.values,
                name=f"{d['ticker']} ({d['name']})",
                line=dict(color=palette6[i], width=2.2),
                mode="lines",
            ))

    fig_line.add_hline(y=100, line_dash="dot", line_color="#bbb",
                       annotation_text="基準 (100)")
    fig_line.update_layout(
        height=380,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8f9fc",
        font_color="#1a1a2e",
        xaxis=dict(gridcolor="#dde1eb"),
        yaxis=dict(gridcolor="#dde1eb", title="正規化価格"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # ── 入れ替え判断テーブル ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔁 3ヶ月入れ替え判断ガイド")
    st.caption("3Mリターンが下位のTop6銘柄と、全体上位に浮上しつつある銘柄を比較して入れ替えを検討")

    rebal_rows = []
    for rank, d in enumerate(sorted_all, 1):
        in_top6 = d["ticker"] in top6_tickers
        er = d["entry_rank"]
        rebal_rows.append({
            "順位(6M)":    rank,
            "保有":        "✅ 保有中" if in_top6 else "—",
            "ティッカー":  d["ticker"],
            "企業名":      d["name"],
            "エントリー":  ENTRY_LABELS[er],
            "6Mリターン":  f"{(d['perf_6m'] or 0)*100:+.1f}%",
            "3Mリターン":  f"{(d['perf_3m'] or 0)*100:+.1f}%",
            "1Mリターン":  f"{(d['perf_1m'] or 0)*100:+.1f}%",
            "RSI":         f"{d['rsi']:.0f}" if d["rsi"] else "N/A",
            "株価":        f"{d['price']:.2f}" if d["price"] else "N/A",
            "判断":        (
                "🔴 入れ替え検討" if in_top6 and rank > 10 else
                "🟡 モニタリング" if in_top6 and rank > 6 else
                "🟢 継続保有"     if in_top6 else
                "⬆️ 組み入れ候補" if rank <= 6 else
                "—"
            ),
        })

    rebal_df = pd.DataFrame(rebal_rows)
    st.dataframe(
        rebal_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "6Mリターン": st.column_config.TextColumn("6Mリターン"),
            "3Mリターン": st.column_config.TextColumn("3Mリターン"),
            "1Mリターン": st.column_config.TextColumn("1Mリターン"),
        }
    )

    st.markdown(
        "<div style='font-size:0.75rem;color:#aaa;margin-top:6px'>"
        "※ 構成銘柄はSMT米国モメンタムファンドの典型的な保有銘柄に基づく参考値です。"
        "実際のファンド組入銘柄は運用会社の月次レポートで確認してください。"
        "</div>",
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 📁 保有ポートフォリオ — 購入記録 & 長期監視
    # ══════════════════════════════════════════════════════════════════════════
    import json

    # ポートフォリオはローカルファイル + session_state の2段階で永続化。
    # Streamlit Cloud ではファイルが再起動で消えるため session_state を正とし、
    # ローカル実行時はファイルをバックアップとして利用する。
    PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "smt_portfolio.json")

    def load_portfolio() -> list[dict]:
        # session_state が既にある場合はそちらを優先
        if "smt_portfolio" in st.session_state:
            return st.session_state["smt_portfolio"]
        # ローカルファイルから読み込み（初回 or ローカル実行）
        if os.path.exists(PORTFOLIO_FILE):
            try:
                data = json.loads(open(PORTFOLIO_FILE, encoding="utf-8").read())
                st.session_state["smt_portfolio"] = data
                return data
            except Exception:
                pass
        st.session_state["smt_portfolio"] = []
        return []

    def save_portfolio(data: list[dict]):
        st.session_state["smt_portfolio"] = data
        # ローカル実行時はファイルにも書き出す（Cloud では無視される）
        try:
            open(PORTFOLIO_FILE, "w", encoding="utf-8").write(
                json.dumps(data, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass

    st.markdown("---")
    st.subheader("📁 保有ポートフォリオ")

    portfolio = load_portfolio()

    # ── 銘柄追加フォーム ─────────────────────────────────────────────────────
    with st.form("pf_form", clear_on_submit=True):
        st.markdown("**銘柄を追加**")
        smt_ticker_opts = [f"{c['ticker']} — {c['name']}" for c in SMT_CONSTITUENTS]
        sel_ticker_str = st.selectbox("ティッカー", smt_ticker_opts, key="pf_ticker")

        col_b, col_c = st.columns(2)
        with col_b:
            buy_price = st.number_input("購入価格 ($)", min_value=0.01, value=100.0,
                                        step=1.0, format="%.2f", key="pf_price")
        with col_c:
            buy_shares = st.number_input("株数", min_value=1, value=1,
                                         step=1, format="%d", key="pf_shares")
        buy_date = st.date_input("購入日", value=date.today(), key="pf_date")
        add_btn = st.form_submit_button("➕ 追加", use_container_width=True)

    if add_btn:
        sel_ticker = sel_ticker_str.split(" — ")[0]
        portfolio.append({
            "ticker":    sel_ticker,
            "name":      sel_ticker_str.split(" — ")[1],
            "buy_price": buy_price,
            "shares":    int(buy_shares),
            "buy_date":  str(buy_date),
        })
        save_portfolio(portfolio)
        st.success(f"{sel_ticker} を追加しました")
        st.rerun()

    # 削除UI
    if portfolio:
        with st.expander("🗑️ 保有銘柄を削除"):
            del_opts = [
                f"{p['ticker']}  ${p['buy_price']:.2f} × {int(p['shares'])}株  ({p['buy_date']})"
                for p in portfolio
            ]
            del_sel = st.selectbox("削除する銘柄", del_opts, key="pf_del_sel")
            if st.button("削除", key="pf_del_btn", type="secondary"):
                idx = del_opts.index(del_sel)
                portfolio.pop(idx)
                save_portfolio(portfolio)
                st.rerun()

    if not portfolio:
        st.info("「➕ 保有銘柄を追加・編集」から購入記録を入力してください。")
    else:
        # ── 現在値取得 ──────────────────────────────────────────────────────
        @st.cache_data(ttl=300)
        def get_current_prices(tickers: tuple) -> dict:
            prices = {}
            for tk in tickers:
                try:
                    h = yf.Ticker(tk).history(period="5d")
                    if h is not None and not h.empty:
                        prices[tk] = h["Close"].iloc[-1]
                except Exception:
                    pass
            return prices

        held_tickers = tuple(sorted({p["ticker"] for p in portfolio}))
        current_prices = get_current_prices(held_tickers)

        # ── サマリーメトリクス ───────────────────────────────────────────────
        total_cost  = sum(p["buy_price"] * p["shares"] for p in portfolio)
        total_value = sum(
            current_prices.get(p["ticker"], p["buy_price"]) * p["shares"]
            for p in portfolio
        )
        total_pnl     = total_value - total_cost
        total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0

        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("投資元本", f"${total_cost:,.2f}")
        sm2.metric("現在評価額", f"${total_value:,.2f}")
        sm3.metric("含み損益", f"${total_pnl:+,.2f}",
                   delta=f"{total_pnl_pct:+.2f}%",
                   delta_color="normal")
        sm4.metric("保有銘柄数", f"{len(portfolio)} ポジション")

        st.markdown("---")

        # ── 損益テーブル ────────────────────────────────────────────────────
        st.markdown("#### 📋 保有一覧 & 損益")
        pf_rows = []
        for p in portfolio:
            cur  = current_prices.get(p["ticker"], None)
            cost = p["buy_price"] * p["shares"]
            val  = (cur * p["shares"]) if cur else None
            pnl  = (val - cost) if val else None
            pct  = (pnl / cost * 100) if (pnl is not None and cost) else None

            # エントリー圏チェック（smt_dataと照合）
            smt_entry = next(
                (d["entry_rank"] for d in smt_data if d["ticker"] == p["ticker"]), 3
            )

            pf_rows.append({
                "エントリー":   ENTRY_LABELS[smt_entry],
                "ティッカー":   p["ticker"],
                "企業名":       p["name"],
                "購入日":       p["buy_date"],
                "購入価格":     f"${p['buy_price']:.2f}",
                "株数":         int(p["shares"]),
                "現在値":       f"${cur:.2f}" if cur else "N/A",
                "取得コスト":   f"${cost:,.2f}",
                "評価額":       f"${val:,.2f}" if val else "N/A",
                "含み損益$":    f"${pnl:+,.2f}" if pnl is not None else "N/A",
                "含み損益%":    f"{pct:+.2f}%" if pct is not None else "N/A",
                "_pct":         pct or 0,
            })

        pf_df = pd.DataFrame(pf_rows)
        display_pf = [c for c in pf_df.columns if not c.startswith("_")]
        st.dataframe(
            pf_df[display_pf],
            use_container_width=True,
            hide_index=True,
            column_config={
                "含み損益%": st.column_config.TextColumn("含み損益%"),
                "含み損益$": st.column_config.TextColumn("含み損益$"),
            }
        )

        # ── 損益ウォーターフォールチャート ──────────────────────────────────
        st.markdown("#### 📊 銘柄別 損益 ($)")
        pf_sorted = sorted(pf_rows, key=lambda x: x["_pct"], reverse=True)
        bar_labels = [r["ティッカー"] for r in pf_sorted]
        bar_vals   = []
        bar_pct    = []
        for r in pf_sorted:
            raw = r["含み損益$"].replace("$","").replace(",","").replace("N/A","0")
            try:
                bar_vals.append(float(raw))
            except Exception:
                bar_vals.append(0)
            raw2 = r["含み損益%"].replace("%","").replace("N/A","0")
            try:
                bar_pct.append(float(raw2))
            except Exception:
                bar_pct.append(0)

        bar_clr = ["#0a7c42" if v >= 0 else "#c0392b" for v in bar_vals]
        fig_pf = go.Figure(go.Bar(
            x=bar_labels, y=bar_vals,
            marker_color=bar_clr,
            text=[f"{p:+.1f}%" for p in bar_pct],
            textposition="outside",
            textfont=dict(size=11),
        ))
        fig_pf.add_hline(y=0, line_color="#ccc", line_width=1)
        fig_pf.update_layout(
            height=320,
            paper_bgcolor="#ffffff", plot_bgcolor="#f8f9fc",
            font_color="#1a1a2e",
            yaxis=dict(gridcolor="#dde1eb", title="損益 ($)"),
            xaxis=dict(gridcolor="#dde1eb"),
            margin=dict(t=30, b=30),
        )
        st.plotly_chart(fig_pf, use_container_width=True)

        # ── 個別パフォーマンスチャート（購入日〜現在） ──────────────────────
        st.markdown("#### 📈 購入後パフォーマンス推移")

        @st.cache_data(ttl=300)
        def get_history_from(ticker: str, from_date: str) -> pd.Series | None:
            try:
                h = yf.Ticker(ticker).history(start=from_date)
                if h is not None and not h.empty:
                    return h["Close"].dropna()
            except Exception:
                pass
            return None

        fig_ph = go.Figure()
        palette_pf = ["#1a56db","#0a7c42","#b07c00","#8b5cf6","#e74c3c",
                      "#0891b2","#d97706","#059669","#7c3aed","#dc2626"]
        added = 0
        for i, p in enumerate(portfolio):
            hist_p = get_history_from(p["ticker"], p["buy_date"])
            if hist_p is not None and len(hist_p) >= 2:
                # 正規化: 購入価格を100として推移
                norm = hist_p / p["buy_price"] * 100
                label = f"{p['ticker']} (購入 ${p['buy_price']:.2f} × {p['shares']}株)"
                fig_ph.add_trace(go.Scatter(
                    x=norm.index, y=norm.values,
                    name=label,
                    line=dict(color=palette_pf[added % len(palette_pf)], width=2),
                    mode="lines",
                    hovertemplate=f"{p['ticker']}<br>%{{x|%Y-%m-%d}}<br>%{{y:.1f}} (購入比)<extra></extra>",
                ))
                added += 1

        if added:
            fig_ph.add_hline(y=100, line_dash="dot", line_color="#bbb",
                             annotation_text="取得コスト (100)")
            fig_ph.update_layout(
                height=400,
                paper_bgcolor="#ffffff", plot_bgcolor="#f8f9fc",
                font_color="#1a1a2e",
                xaxis=dict(gridcolor="#dde1eb"),
                yaxis=dict(gridcolor="#dde1eb", title="購入価格比 (購入時=100)"),
                legend=dict(orientation="h", yanchor="bottom", y=-0.4),
            )
            st.plotly_chart(fig_ph, use_container_width=True)
        else:
            st.info("価格履歴が取得できませんでした。しばらく後に再試行してください。")

        st.markdown(
            "<div style='font-size:0.75rem;color:#aaa;margin-top:4px'>"
            "※ 株価はyfinance経由の参考値です。実際の損益は証券会社の口座でご確認ください。"
            "</div>",
            unsafe_allow_html=True,
        )
