import re
import time
import csv
import io
import requests
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urlparse, urljoin, urldefrag

import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Word Crawler",
    page_icon="🕷️",
    layout="wide",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stat-box {
        background: #f0f4f8;
        border-radius: 10px;
        padding: 18px 22px;
        text-align: center;
    }
    .stat-value { font-size: 2rem; font-weight: 700; color: #1a56db; }
    .stat-label { font-size: 0.85rem; color: #6b7280; margin-top: 2px; }
    .stProgress > div > div { background-color: #1a56db; }
</style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Core functions ─────────────────────────────────────────────────────────────
def get_domain(url):
    p = urlparse(url)
    return p.scheme + "://" + p.netloc

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None, str(e)

def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "meta", "noscript", "head", "footer", "nav", "aside"]):
        tag.decompose()
    return soup.get_text(separator=" ")

def extract_links(html, current_url, base_domain):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        full, _ = urldefrag(urljoin(current_url, a["href"]))
        if full.startswith(base_domain) and urlparse(full).scheme in ("http", "https"):
            links.add(full.rstrip("/"))
    return links

def count_words(text):
    words = re.findall(r"\b[a-zA-ZÀ-ÿ]+\b", text.lower())
    return words

def make_chart(freq, top_n, title):
    top_words, top_counts = zip(*freq.most_common(top_n))
    fig, ax = plt.subplots(figsize=(10, max(5, top_n * 0.38)))
    bars = ax.barh(list(reversed(top_words)), list(reversed(top_counts)),
                   color="#1a56db", edgecolor="white", linewidth=0.5)
    for bar, count in zip(bars, reversed(top_counts)):
        ax.text(bar.get_width() + max(top_counts) * 0.005,
                bar.get_y() + bar.get_height() / 2,
                f"{count:,}", va="center", fontsize=9, color="#374151")
    ax.set_xlabel("Occurrences", fontsize=11)
    ax.set_title(title, fontsize=13, pad=12)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    return fig

def to_csv_bytes(freq, total_words):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["word", "count", "frequency_%"])
    for word, count in freq.most_common():
        writer.writerow([word, count, f"{count / total_words * 100:.4f}"])
    return buf.getvalue().encode("utf-8")

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("🕷️ Web Word Crawler")
st.caption("Count and analyse words across one page or an entire website.")

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Mode", ["Single page", "Full website crawl"])
    if mode == "Full website crawl":
        max_pages = st.number_input("Max pages to crawl", min_value=1, max_value=500, value=30)
        delay = st.slider("Delay between requests (s)", 0.0, 3.0, 0.5, step=0.1)
    
    st.divider()
    st.caption("💡 **Tip:** Keep delay ≥ 0.5 s to avoid being blocked.")

url_input = st.text_input("Enter a URL", placeholder="https://example.com")
top_n = 20
run = st.button("🚀 Start", type="primary", use_container_width=True)

# ── Run ────────────────────────────────────────────────────────────────────────
if run:
    if not url_input.strip():
        st.warning("Please enter a URL.")
        st.stop()

    url = url_input.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # ── SINGLE PAGE ────────────────────────────────────────────────────────────
    if mode == "Single page":
        with st.spinner("Fetching page..."):
            html = fetch(url)
        if not html:
            st.error("Could not fetch the page. Check the URL or try another site.")
            st.stop()

        text  = extract_text(html)
        words = count_words(text)
        freq  = Counter(words)

        total_words  = len(words)
        unique_words = len(freq)

        st.success(f"✅ Analysed **{urlparse(url).netloc}**")

        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="stat-box"><div class="stat-value">{total_words:,}</div><div class="stat-label">Total words</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="stat-box"><div class="stat-value">{unique_words:,}</div><div class="stat-label">Unique words</div></div>', unsafe_allow_html=True)

        st.divider()
        fig = make_chart(freq, top_n, f"Top {top_n} words on {urlparse(url).netloc}")
        st.pyplot(fig)

        tab1, tab2 = st.tabs(["📋 Full table", "⬇️ Download"])
        with tab1:
            df = pd.DataFrame(freq.most_common(), columns=["Word", "Count"])
            df["Frequency %"] = (df["Count"] / total_words * 100).round(3)
            st.dataframe(df, use_container_width=True, height=400)
        with tab2:
            st.download_button("Download CSV", to_csv_bytes(freq, total_words),
                               "word_counts.csv", "text/csv", use_container_width=True)

    # ── FULL CRAWL ─────────────────────────────────────────────────────────────
    else:
        base_domain = get_domain(url)
        visited     = set()
        queue       = [url.rstrip("/")]
        all_words   = []
        page_counts = {}
        errors      = []

        st.info(f"Crawling **{base_domain}** — up to {max_pages} pages")

        progress_bar  = st.progress(0)
        status_text   = st.empty()
        log_container = st.expander("📜 Live crawl log", expanded=False)
        log_lines     = []

        while queue and len(visited) < max_pages:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)
            pct = len(visited) / max_pages
            progress_bar.progress(min(pct, 1.0))
            short = current.replace(base_domain, "") or "/"
            status_text.markdown(f"**[{len(visited)}/{max_pages}]** Crawling `{short}`")

            html = fetch(current)
            if not html:
                errors.append(current)
                log_lines.append(f"⚠️ Skipped: {short}")
            else:
                text  = extract_text(html)
                words = count_words(text)
                all_words.extend(words)
                page_counts[current] = len(words)
                log_lines.append(f"✅ [{len(words):,} words] {short}")

                new_links = extract_links(html, current, base_domain) - visited
                queue.extend(sorted(new_links))

            with log_container:
                st.text("\n".join(log_lines[-30:]))  # show last 30 lines

            time.sleep(delay)

        progress_bar.progress(1.0)
        status_text.empty()

        if not all_words:
            st.error("No words collected. The site may be blocking requests.")
            st.stop()

        freq         = Counter(all_words)
        total_words  = len(all_words)
        unique_words = len(freq)
        total_pages  = len(page_counts)

        st.success(f"✅ Crawl complete — **{total_pages}** pages visited")

        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="stat-box"><div class="stat-value">{total_pages:,}</div><div class="stat-label">Pages crawled</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="stat-box"><div class="stat-value">{total_words:,}</div><div class="stat-label">Total words</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="stat-box"><div class="stat-value">{unique_words:,}</div><div class="stat-label">Unique words</div></div>', unsafe_allow_html=True)

        st.divider()

        fig = make_chart(freq, top_n,
                         f"Top {top_n} words across {total_pages} pages of {base_domain}")
        st.pyplot(fig)

        tab1, tab2, tab3 = st.tabs(["📋 Word table", "📄 Pages breakdown", "⬇️ Download"])
        with tab1:
            df = pd.DataFrame(freq.most_common(), columns=["Word", "Count"])
            df["Frequency %"] = (df["Count"] / total_words * 100).round(3)
            st.dataframe(df, use_container_width=True, height=400)

        with tab2:
            df_pages = pd.DataFrame(
                sorted(page_counts.items(), key=lambda x: x[1], reverse=True),
                columns=["URL", "Word Count"]
            )
            df_pages["URL"] = df_pages["URL"].str.replace(base_domain, "", regex=False)
            st.dataframe(df_pages, use_container_width=True, height=400)

        with tab3:
            st.download_button("Download words CSV", to_csv_bytes(freq, total_words),
                               "word_counts.csv", "text/csv", use_container_width=True)
            pages_csv = df_pages.to_csv(index=False).encode("utf-8")
            st.download_button("Download pages CSV", pages_csv,
                               "page_breakdown.csv", "text/csv", use_container_width=True)