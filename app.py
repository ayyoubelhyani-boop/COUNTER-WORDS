import re
import time
import requests
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urlparse, urljoin, urldefrag

import streamlit as st

st.set_page_config(page_title="Word Crawler", page_icon="🕷️", layout="centered")

st.markdown("""
<style>
    .block-container { padding-top: 2.5rem; }
    .stat-box {
        background: #f0f4ff;
        border: 1px solid #d1d9f0;
        border-radius: 12px;
        padding: 24px 16px;
        text-align: center;
    }
    .stat-value { font-size: 2.2rem; font-weight: 700; color: #1a56db; }
    .stat-label { font-size: 0.82rem; color: #6b7280; margin-top: 4px; letter-spacing: 0.03em; text-transform: uppercase; }
    .stProgress > div > div { background-color: #1a56db; }
    .word-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 12px;
        border-radius: 8px;
        margin-bottom: 4px;
        background: #f9fafb;
        font-size: 0.95rem;
    }
    .word-row:nth-child(odd) { background: #f0f4ff; }
    .word-name { font-weight: 600; color: #111827; }
    .word-count { color: #1a56db; font-weight: 700; }
    .page-item {
        padding: 6px 12px;
        background: #f9fafb;
        border-radius: 8px;
        margin-bottom: 4px;
        font-size: 0.88rem;
        color: #374151;
        word-break: break-all;
    }
    .page-item:nth-child(odd) { background: #f0f4ff; }
</style>
""", unsafe_allow_html=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

STOP_WORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "is","it","its","be","was","are","were","as","by","from","that","this",
    "have","has","had","not","he","she","they","we","you","i","do","did",
    "will","would","can","could","what","which","who","their","if","so","about"
}

def get_domain(url):
    p = urlparse(url)
    return p.scheme + "://" + p.netloc

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

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
    return re.findall(r"\b[a-zA-ZÀ-ÿ]+\b", text.lower())

def stat(value, label):
    return f'<div class="stat-box"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>'

def render_top_words(freq, n=20):
    st.subheader("Most repeated words")
    rows = ""
    for word, count in freq.most_common(n):
        if word not in STOP_WORDS:
            rows += f'<div class="word-row"><span class="word-name">{word}</span><span class="word-count">{count:,}</span></div>'
    st.markdown(rows, unsafe_allow_html=True)

def render_pages(visited, base_domain):
    st.subheader(f"Crawled pages ({len(visited)})")
    rows = ""
    for page in sorted(visited):
        short = page.replace(base_domain, "") or "/"
        rows += f'<div class="page-item">🔗 {short}</div>'
    st.markdown(rows, unsafe_allow_html=True)

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("🕷️ Web Word Crawler")

mode = st.segmented_control("", ["Single page", "Full website"], default="Single page")
url_input = st.text_input("", placeholder="https://example.com", label_visibility="collapsed")

if mode == "Full website":
    max_pages = st.number_input("Max pages to crawl", min_value=1, max_value=500, value=30)

run = st.button("Analyse", type="primary", use_container_width=True)

if run:
    if not url_input.strip():
        st.warning("Please enter a URL.")
        st.stop()

    url = url_input.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # ── Single page ────────────────────────────────────────────────────────────
    if mode == "Single page":
        with st.spinner("Fetching page..."):
            html = fetch(url)

        if not html:
            st.error("Could not fetch the page. Check the URL or try another site.")
            st.stop()

        words = count_words(extract_text(html))
        freq  = Counter(words)

        st.divider()
        c1, c2 = st.columns(2)
        c1.markdown(stat(f"{len(words):,}", "Total words"), unsafe_allow_html=True)
        c2.markdown(stat(f"{len(freq):,}", "Unique words"), unsafe_allow_html=True)

        st.divider()
        render_top_words(freq)

    # ── Full crawl ─────────────────────────────────────────────────────────────
    else:
        base_domain = get_domain(url)
        visited, queue, all_words = set(), [url.rstrip("/")], []

        st.divider()
        progress_bar = st.progress(0, text="Starting crawl...")

        while queue and len(visited) < max_pages:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)
            progress_bar.progress(
                len(visited) / max_pages,
                text=f"Crawling page {len(visited)} of {max_pages} — {current.replace(base_domain,'') or '/'}"
            )

            html = fetch(current)
            if html:
                words = count_words(extract_text(html))
                all_words.extend(words)
                new_links = extract_links(html, current, base_domain) - visited
                queue.extend(sorted(new_links))

            time.sleep(0.5)

        progress_bar.empty()

        if not all_words:
            st.error("No words collected. The site may be blocking requests.")
            st.stop()

        freq = Counter(all_words)

        c1, c2, c3 = st.columns(3)
        c1.markdown(stat(f"{len(visited):,}", "Pages crawled"), unsafe_allow_html=True)
        c2.markdown(stat(f"{len(all_words):,}", "Total words"),  unsafe_allow_html=True)
        c3.markdown(stat(f"{len(freq):,}",      "Unique words"), unsafe_allow_html=True)

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            render_top_words(freq)
        with col2:
            render_pages(visited, base_domain)