"""
Cardiac Review Pipeline — Streamlit GUI
=======================================
Run with:
    .venv/bin/streamlit run app.py
"""

import io
import os
import re
import subprocess
import sys
import unicodedata
import uuid
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
import streamlit as st
from venn import venn

ROOT = os.path.dirname(__file__)
JSON_DIR = os.path.join(ROOT, "json_files")
EXPORTED = os.path.join(ROOT, "exported_dfs")
IMAGES = os.path.join(ROOT, "images")

sys.path.insert(0, ROOT)
from utils.gui_utils import (  # noqa: E402
    suggest_pattern, build_query_preview,
    get_term_suggestions, fetch_mesh_terms, apply_pending_term,
)
from scripts.run_review_pubmed_search import SEARCH_TERMS as _SEARCH_TERMS  # noqa: E402

# Flatten from {key: [string]} → {key: string} for the GUI table
DEFAULT_TERMS: dict[str, str] = {k: v[0] for k, v in _SEARCH_TERMS.items()}

REVIEW_PREFIXES = tuple(_SEARCH_TERMS.keys())

DEFAULT_TAGS = pd.DataFrame([
    {
        "Tag label":   "Cardiac model",
        "What it means": "Paper describes an in-vitro/ex-vivo cardiac tissue model",
        "Regex pattern (pipe = OR, case-insensitive)": "engineered heart tissue|EHT|heart-on-a-chip|microphysiological|organoid|spheroid|hiPSC|iPSC-derived",
    },
    {
        "Tag label":   "Aging / maturation",
        "What it means": "Paper discusses age, senescence, or maturation of the model",
        "Regex pattern (pipe = OR, case-insensitive)": "aging|aged|senescence|inflammaging|age-related|adult-like|maturation",
    },
    {
        "Tag label":   "Engineering intervention",
        "What it means": "Paper applies a physical/mechanical/electrical knob to the model",
        "Regex pattern (pipe = OR, case-insensitive)": "pacing|electrical stimulation|mechanical loading|stretch|preload|afterload|stiffness|alignment|anisotropy|co-culture",
    },
    {
        "Tag label":   "Functional endpoint",
        "What it means": "Paper reports a measurable cardiac function readout",
        "Regex pattern (pipe = OR, case-insensitive)": "contractility|force|calcium|action potential|APD|arrhythmia|mitochondria|metabolism|fibrosis|ECM|beta-adrenergic|isoproterenol",
    },
    {
        "Tag label":   "Drug / toxicity",
        "What it means": "Paper involves drug screening, cardiotoxicity, or clinical prediction",
        "Regex pattern (pipe = OR, case-insensitive)": "cardiotoxicity|drug screening|proarrhythmia|QT|torsades|predict|translational",
    },
])


# ── helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _cached_mesh_terms(query: str, scope: str) -> list[str]:
    """Fetch MeSH terms from NLM API (cached 1h) then merge with local tiab suggestions."""
    mesh = fetch_mesh_terms(query, max_results=6)
    local = get_term_suggestions(query, scope=scope)
    # Interleave: MeSH first, then tiab — deduplicated
    seen: set[str] = set()
    merged: list[str] = []
    for t in mesh + local:
        if t not in seen:
            seen.add(t)
            merged.append(t)
    return merged[:12]  # cap at 12 chips


def normalize_title(t):
    if not isinstance(t, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", t)
    return re.sub(r"[^a-z0-9]", "", nfkd.encode("ascii", "ignore").decode().lower())


def fig_to_png_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def df_to_xlsx_bytes(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Screening")
        ws = writer.sheets["Screening"]
        for col in ws.columns:
            max_len = max((len(str(c.value)) for c in col if c.value), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)
    buf.seek(0)
    return buf.read()


# ── streamlit page ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Literature Review Pipeline",
    layout="wide",
)

st.title("Literature Review Pipeline")
st.caption(
    "Search PubMed, tag papers, and generate figures for your systematic review."
)
st.divider()

tab_scrape, tab_table, tab_figs = st.tabs(
    ["Scrape PubMed", "Build Master Table", "Figures"]
)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SCRAPE
# ══════════════════════════════════════════════════════════════════════════════
with tab_scrape:
    st.header("PubMed Search Queries")

    # ── Query table (raw edit mode) ───────────────────────────────────────────
    if "query_df" not in st.session_state:
        st.session_state.query_df = pd.DataFrame(
            [{"Query Name": k, "Query String (PubMed boolean)": v}
             for k, v in DEFAULT_TERMS.items()]
        )

    col_add, col_reset = st.columns([1, 1])
    with col_add:
        if st.button("+ Add blank row"):
            st.session_state.query_df = pd.concat(
                [st.session_state.query_df,
                 pd.DataFrame([{"Query Name": "NEW_QUERY", "Query String (PubMed boolean)": ""}])],
                ignore_index=True,
            )
    with col_reset:
        if st.button("Reset to defaults"):
            st.session_state.query_df = pd.DataFrame(
                [{"Query Name": k, "Query String (PubMed boolean)": v}
                 for k, v in DEFAULT_TERMS.items()]
            )

    edited_df = st.data_editor(
        st.session_state.query_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Query Name": st.column_config.TextColumn(
                "Query Name", width="medium", help="Alphanumeric + underscores only"
            ),
            "Query String (PubMed boolean)": st.column_config.TextColumn(
                "Query String (PubMed boolean)", width="large",
                help="Full PubMed boolean string; will be AND-ed with the year filter automatically",
            ),
        },
        key="query_editor",
    )
    st.session_state.query_df = edited_df

    # ── Visual Query Builder ──────────────────────────────────────────────────
    st.divider()
    with st.expander("Visual Query Builder — compose a query from concept blocks"):
        st.markdown(
            "Each **block** is a concept (its terms are OR'd). "
            "Blocks are joined top-to-bottom by the **connector** you choose. "
            "Move blocks up/down with the arrow buttons. "
            "When you're happy, click **Add to query table** above."
        )

        # Each block has a stable UUID so widget keys survive reorder/delete
        def _make_block(name="", terms="", connector="AND"):
            return {"id": str(uuid.uuid4()), "name": name, "terms": terms, "connector": connector}

        _DEFAULT_BLOCKS = [
            _make_block("Cardiac models",
                        '"engineered heart tissue"[tiab]\nhiPSC-CM[tiab]\n"heart-on-a-chip"[tiab]\nMPS[tiab]\n"organ-on-a-chip"[tiab]',
                        "AND"),
            _make_block("Age / maturation",
                        'aging[tiab]\nsenescence[tiab]\nmaturation[tiab]\n"adult-like"[tiab]',
                        "AND"),
        ]

        if "qb_blocks" not in st.session_state:
            st.session_state.qb_blocks = _DEFAULT_BLOCKS[:]

        blocks = st.session_state.qb_blocks
        n = len(blocks)

        for idx, block in enumerate(blocks):
            bid = block["id"]
            is_last = idx == n - 1

            card_cols = st.columns([0.04, 0.96])
            with card_cols[0]:
                if idx > 0 and st.button("^", key=f"qb_up_{bid}", help="Move up"):
                    blocks[idx - 1], blocks[idx] = blocks[idx], blocks[idx - 1]
                    st.rerun()
                if idx < n - 1 and st.button("v", key=f"qb_dn_{bid}", help="Move down"):
                    blocks[idx], blocks[idx + 1] = blocks[idx + 1], blocks[idx]
                    st.rerun()
                if n > 1 and st.button("x", key=f"qb_del_{bid}", help="Delete block"):
                    blocks.pop(idx)
                    st.rerun()

            with card_cols[1]:
                st.markdown(f"**Block {idx + 1}** — {block['name'] or 'unnamed'}")
                b_cols = st.columns([2, 5, 2])
                with b_cols[0]:
                    block["name"] = st.text_input(
                        "Block name",
                        value=block["name"],
                        key=f"qb_name_{bid}",
                        label_visibility="collapsed",
                        placeholder="Block name",
                    )
                with b_cols[1]:
                    # Apply any pending chip addition BEFORE the textarea renders.
                    # We update session_state for the textarea's key directly so the
                    # widget itself shows the new term, not just the preview.
                    pending_key = f"qb_pending_{bid}"
                    terms_key = f"qb_terms_{bid}"
                    if pending_key in st.session_state:
                        term_to_add = st.session_state.pop(pending_key)
                        existing = st.session_state.get(terms_key, block["terms"])
                        updated = apply_pending_term(existing, term_to_add)
                        st.session_state[terms_key] = updated
                        block["terms"] = updated

                    block["terms"] = st.text_area(
                        "Terms",
                        key=terms_key,
                        height=110,
                        help="One search term per line — all OR'd together. "
                             "Use PubMed field tags, e.g. aging[tiab] or \"Aging\"[MeSH Terms]",
                        label_visibility="collapsed",
                    )

                    # Suggestion chips: live MeSH lookup + local tiab fallback
                    _scope = st.session_state.get("search_scope_select", "tiab")
                    suggestions = _cached_mesh_terms(block["name"], _scope) if block["name"].strip() else []
                    if suggestions:
                        st.caption("Suggested terms — click to add:")
                        chip_cols = st.columns(min(len(suggestions), 4))
                        for ci, term in enumerate(suggestions[:12]):
                            with chip_cols[ci % 4]:
                                short = term.split("[")[0].strip('"').strip()[:26]
                                if st.button(short, key=f"chip_{bid}_{ci}", help=term):
                                    st.session_state[pending_key] = term
                                    st.rerun()
                with b_cols[2]:
                    if not is_last:
                        conn_options = ["AND", "OR", "NOT"]
                        # Key is stable (UUID-based) so Streamlit persists the chosen value correctly
                        block["connector"] = st.selectbox(
                            "Connector",
                            options=conn_options,
                            index=conn_options.index(block.get("connector") or "AND"),
                            key=f"qb_conn_{bid}",
                            help="How this block connects to the next one",
                        )
                    else:
                        st.caption("(last block)")
                        block["connector"] = "AND"

            if not is_last:
                st.markdown(
                    f"<div style='text-align:center;font-weight:bold;color:#555;"
                    f"letter-spacing:2px;padding:4px 0'>&mdash; {block.get('connector','AND')} &mdash;</div>",
                    unsafe_allow_html=True,
                )

        badd, breset = st.columns([1, 1])
        with badd:
            if st.button("+ Add block"):
                blocks.append(_make_block(f"Block {n + 1}"))
                st.rerun()
        with breset:
            if st.button("Reset builder"):
                st.session_state.qb_blocks = _DEFAULT_BLOCKS[:]
                # Clear stale widget state for old block IDs
                for key in list(st.session_state.keys()):
                    if key.startswith(("qb_conn_", "qb_name_", "qb_terms_", "qb_up_", "qb_dn_", "qb_del_")):
                        del st.session_state[key]
                st.rerun()

        # Build preview using the shared utility
        _preview_df = pd.DataFrame([
            {"Block Name": b["name"], "Terms": b["terms"], "Connector": b.get("connector") or "—"}
            for b in blocks
        ])
        preview_str = build_query_preview(_preview_df)

        st.divider()
        st.markdown("**Query preview:**")
        st.code(preview_str or "(add terms to the blocks above)", language=None)

        new_query_name = st.text_input(
            "Name for this query (will be added to the table above)",
            value="MY_QUERY", key="qb_name_final",
        )
        if st.button("Add to query table", disabled=not preview_str or not new_query_name.strip()):
            new_row = pd.DataFrame([{
                "Query Name": new_query_name.strip().upper().replace(" ", "_"),
                "Query String (PubMed boolean)": preview_str,
            }])
            st.session_state.query_df = pd.concat(
                [st.session_state.query_df, new_row], ignore_index=True
            )
            st.success(f"Added {new_query_name.strip().upper()} to the query table. Scroll up to see it.")

    st.divider()
    st.subheader("Year Range & Output")

    search_scope = st.selectbox(
        "Search scope",
        options=["tiab", "tw"],
        format_func=lambda x: {
            "tiab": "Title/Abstract only — precise, fewer hits",
            "tw": "Text Word — title, abstract, MeSH, keywords (broader, more hits)",
        }[x],
        index=0,
        key="search_scope_select",
        help="[tiab] = title + abstract. [tw] = also MeSH terms, author keywords, and other indexed fields.",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        start_year = st.number_input("Start year", min_value=1990, max_value=2030, value=2000, step=1)
    with c2:
        end_year = st.number_input(
            "End year (inclusive)",
            min_value=1990,
            max_value=2030,
            value=2026,
            step=1,
            help="The scraper uses an exclusive upper bound internally, so 2026 here → range ends at 2026.",
        )
    with c3:
        increment = st.number_input(
            "Year chunk size",
            min_value=1,
            max_value=10,
            value=1,
            help="Number of years per API call. 1 = one call per year (safest; PubMed returns max 10,000 results per query, so broad queries need 1). Use 2–5 for narrow queries to speed up.",
        )
    with c4:
        out_dir = st.text_input("Output directory", value="./json_files")

    import math
    n_queries = max(len(edited_df), 1)
    n_chunks = max(math.ceil((end_year - start_year + 1) / max(increment, 1)), 1)
    n_api_calls = n_queries * n_chunks
    secs_per_call = 3  # conservative estimate; PubMed rate-limits to ~3 req/s
    est_secs = n_api_calls * secs_per_call
    est_min = est_secs // 60
    est_sec_rem = est_secs % 60
    time_str = f"{est_min}m {est_sec_rem}s" if est_min else f"~{est_secs}s"
    st.info(
        f"{n_queries} quer{'y' if n_queries==1 else 'ies'} "
        f"× {n_chunks} chunk{'s' if n_chunks!=1 else ''} "
        f"({start_year}–{end_year}, chunk size {increment}) "
        f"= **{n_api_calls} API calls** — estimated {time_str}."
    )

    if st.button("Run Scrape", type="primary", use_container_width=True):
        # Build terms from table; apply search scope (tiab vs tw)
        terms_dict = {}
        for _, row in edited_df.iterrows():
            if not row["Query Name"] or not row["Query String (PubMed boolean)"]:
                continue
            q = str(row["Query String (PubMed boolean)"])
            if search_scope == "tw":
                q = q.replace("[Title/Abstract]", "[tw]").replace("[tiab]", "[tw]")
            terms_dict[row["Query Name"]] = [q]

        tmp_script = os.path.join(ROOT, "_tmp_scrape_runner.py")
        with open(tmp_script, "w") as f:
            f.write("import sys, os\n")
            f.write(f"sys.path.insert(0, {ROOT!r})\n")
            f.write("from PubMedScraper import PubMedScraper\n")
            f.write(f"SEARCH_TERMS = {terms_dict!r}\n")
            f.write(
                f"scraper = PubMedScraper(SEARCH_TERMS)\n"
                f"scraper.generate_queries({start_year}, {end_year + 1}, {increment})\n"
                f"scraper.scrape_pubmed(output_dir={out_dir!r})\n"
            )

        python = os.path.join(ROOT, ".venv", "bin", "python")
        if not os.path.exists(python):
            python = sys.executable

        n_calls = len(terms_dict) * max(1, (end_year - start_year + 1 + increment - 1) // increment)
        status_box = st.empty()
        with st.spinner(f"Scraping PubMed ({n_calls} API calls) — running in background..."):
            proc = subprocess.Popen(
                [python, tmp_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # suppress warnings; capture separately for error reporting
                text=True,
                cwd=ROOT,
            )
            # Stream only meaningful stdout lines (query progress), no warnings
            progress_lines: list[str] = []
            for line in proc.stdout:
                s = line.rstrip()
                if s and not any(s.startswith(p) for p in ("WARNING", "/Users", "/opt", "warn")):
                    progress_lines.append(s)
                    status_box.caption(progress_lines[-1])
            stderr_out = proc.stderr.read()
            proc.wait()

        status_box.empty()
        os.remove(tmp_script)
        if proc.returncode == 0:
            st.success("Scrape complete. JSONL files are in `json_files/`.")
        else:
            # Show stderr only on failure
            err_lines = [l for l in stderr_out.splitlines()
                         if l.strip() and not l.startswith("WARNING")]
            st.error("Scraper exited with an error:\n\n" + "\n".join(err_lines[-20:]))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUILD MASTER TABLE
# ══════════════════════════════════════════════════════════════════════════════
with tab_table:
    st.header("Build Master Table")
    st.markdown(
        "Loads all scraped JSONL files, removes duplicate papers, and labels each paper "
        "with the tags you define below. You then choose a rule to decide which papers are "
        "worth manually reading."
    )

    # ── Step 1: Tags ──────────────────────────────────────────────────────────
    st.subheader("Step 1 — Define your labels (tags)")
    st.markdown(
        "Each tag is a **label** you want to attach to a paper. "
        "When a paper's title or abstract contains any of the words/phrases in the **pattern**, "
        "it gets that label. You can rename, edit, add or delete tags freely — "
        "they don't have to match your PubMed queries."
    )

    if "tags_df" not in st.session_state:
        st.session_state.tags_df = DEFAULT_TAGS.copy()

    tag_reset_col, _ = st.columns([1, 3])
    with tag_reset_col:
        if st.button("Reset tags to defaults"):
            st.session_state.tags_df = DEFAULT_TAGS.copy()

    tags_df_edited = st.data_editor(
        st.session_state.tags_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Tag label": st.column_config.TextColumn(
                "Tag label",
                width="small",
                help="Short name you give this concept, e.g. 'cardiac model' or 'clinical outcome'",
            ),
            "What it means": st.column_config.TextColumn(
                "What it means (optional note)",
                width="medium",
                help="Free-text description for your own reference",
            ),
            "Regex pattern (pipe = OR, case-insensitive)": st.column_config.TextColumn(
                "Pattern — words/phrases separated by | (pipe)",
                width="large",
                help=(
                    "Any paper whose title or abstract contains at least one of these "
                    "words/phrases (case-insensitive) will get this tag.\n\n"
                    "Use | to separate alternatives, e.g.:\n"
                    "  heart failure|HF|cardiac dysfunction"
                ),
            ),
        },
        key="tags_editor",
    )
    st.session_state.tags_df = tags_df_edited

    # Suggest button — uses suggest_pattern imported from utils.gui_utils
    suggest_col, _ = st.columns([1, 3])
    with suggest_col:
        if st.button(
            "Suggest patterns from labels & descriptions",
            help="For any tag with an empty pattern, generates a suggestion from its label and description.",
        ):
            updated = st.session_state.tags_df.copy()
            pat_col = "Regex pattern (pipe = OR, case-insensitive)"
            for idx, row in updated.iterrows():
                if not isinstance(row.get(pat_col), str) or not row[pat_col].strip():
                    updated.at[idx, pat_col] = suggest_pattern(
                        str(row.get("Tag label", "")),
                        str(row.get("What it means", "")),
                    )
            st.session_state.tags_df = updated
            st.rerun()

    # Derive internal column name from label: lowercase + underscores
    def _tag_col(label: str) -> str:
        return "tag_" + re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

    valid_tags = [
        (row["Tag label"], _tag_col(row["Tag label"]), row["Regex pattern (pipe = OR, case-insensitive)"])
        for _, row in tags_df_edited.iterrows()
        if isinstance(row.get("Tag label"), str) and row["Tag label"].strip()
        and isinstance(row.get("Regex pattern (pipe = OR, case-insensitive)"), str)
        and row["Regex pattern (pipe = OR, case-insensitive)"].strip()
    ]

    st.divider()

    # ── Step 2: Screening rule ────────────────────────────────────────────────
    st.subheader("Step 2 — Set the screening rule")
    st.markdown(
        "The screening rule decides which papers go into your shortlist for manual review. "
        "A paper is **kept** only if it satisfies the rule you set here."
    )

    all_labels = [label for label, _, _ in valid_tags]

    if not all_labels:
        st.warning("Define at least one tag above to set a screening rule.")
    else:
        gr1, gr2 = st.columns(2)
        with gr1:
            st.markdown("##### Must contain ALL of these")
            st.caption("A paper is excluded if even one of these tags is missing.")
            required_labels = st.multiselect(
                "Required tags",
                options=all_labels,
                default=[l for l in all_labels[:2] if l in all_labels],
                label_visibility="collapsed",
            )
        with gr2:
            st.markdown("##### Must contain AT LEAST ONE of these")
            st.caption("A paper is excluded if none of these tags appear. Leave empty to skip this check.")
            optional_labels = st.multiselect(
                "Optional tags (at least one)",
                options=all_labels,
                default=[l for l in all_labels[2:] if l in all_labels],
                label_visibility="collapsed",
            )

        # Plain-English preview of the rule
        def _plain(label: str) -> str:
            return f'**"{label}"**'
        if required_labels and optional_labels:
            rule_preview = (
                "Keep a paper if: "
                + " AND ".join(_plain(l) for l in required_labels)
                + "  **AND**  at least one of ( "
                + " OR ".join(_plain(l) for l in optional_labels)
                + " )"
            )
        elif required_labels:
            rule_preview = "Keep a paper if: " + " AND ".join(_plain(l) for l in required_labels)
        elif optional_labels:
            rule_preview = "Keep a paper if at least one of: " + " OR ".join(_plain(l) for l in optional_labels)
        else:
            rule_preview = "⚠️ No rule defined — all papers will be kept."
        st.info(rule_preview, icon="🔎")

    st.divider()

    # ── Step 3: Build ─────────────────────────────────────────────────────────
    st.subheader("Step 3 — Build")
    json_dir_table = st.text_input(
        "Folder containing the scraped JSONL files",
        value="./json_files",
        key="json_dir_table",
        help="This is the folder where the scraper saved its output. Default: ./json_files",
    )

    if st.button("Build Master Table", type="primary", use_container_width=True):
        if not valid_tags:
            st.error("Add at least one tag before building.")
            st.stop()

        abs_json = os.path.join(ROOT, json_dir_table.lstrip("./"))
        if not os.path.isdir(abs_json):
            abs_json = json_dir_table

        with st.spinner("Loading JSONL files and applying tags…"):
            try:
                all_jsonl = [f for f in os.listdir(abs_json) if f.endswith(".jsonl")]
            except FileNotFoundError:
                st.error(f"Folder not found: {abs_json}")
                st.stop()

            if not all_jsonl:
                st.error("No JSONL files found in that folder. Run the scrape first.")
                st.stop()

            frames = []
            for fname in sorted(all_jsonl):
                path = os.path.join(abs_json, fname)
                try:
                    df = pd.read_json(path, lines=True)
                except Exception:
                    continue
                if df.empty:
                    continue
                stem = os.path.splitext(fname)[0]
                df["query_file"] = stem
                df["query_group"] = re.sub(r"_\d{4}(_\d{4})?_PubMed$", "", stem)
                frames.append(df)

            master = pd.concat(frames, ignore_index=True)
            original_len = len(master)

            # Dedup: PMID > DOI > normalised title
            master["_nt"] = master["title"].apply(normalize_title)
            for col in ("pmid", "doi"):
                if col in master.columns:
                    master[col] = master[col].astype(str).str.strip().replace({"nan": "", "None": ""})
            parts = []
            if "pmid" in master.columns:
                has_pmid = master["pmid"].ne("")
                parts.append(master[has_pmid].drop_duplicates("pmid", keep="first"))
                rest = master[~has_pmid]
            else:
                rest = master
            if "doi" in rest.columns:
                has_doi = rest["doi"].ne("")
                parts.append(rest[has_doi].drop_duplicates("doi", keep="first"))
                rest = rest[~has_doi]
            parts.append(rest.drop_duplicates("_nt", keep="first"))
            master = pd.concat(parts, ignore_index=True).drop(columns=["_nt"], errors="ignore")

            # Apply tags
            text = master["title"].fillna("").astype(str) + " " + master.get(
                "abstract", pd.Series([""] * len(master))
            ).fillna("").astype(str)
            for label, col, pattern in valid_tags:
                master[col] = text.str.contains(pattern, case=False, regex=True)

            # Screening rule
            req_cols  = [_tag_col(l) for l in required_labels if _tag_col(l) in master.columns]
            opt_cols  = [_tag_col(l) for l in optional_labels if _tag_col(l) in master.columns]
            keep_mask = pd.Series(True, index=master.index)
            for c in req_cols:
                keep_mask &= master[c].astype(bool)
            if opt_cols:
                opt_mask = pd.Series(False, index=master.index)
                for c in opt_cols:
                    opt_mask |= master[c].astype(bool)
                keep_mask &= opt_mask
            master["keep_for_manual_screening"] = keep_mask

            if "date" in master.columns:
                master["date"] = pd.to_datetime(master["date"], errors="coerce")
                master = master.sort_values("date", ascending=False, na_position="last")

            os.makedirs(EXPORTED, exist_ok=True)
            master.to_csv(os.path.join(EXPORTED, "review_master.csv"), index=False)
            screening = master[master["keep_for_manual_screening"]]
            screening.to_csv(os.path.join(EXPORTED, "review_screening.csv"), index=False)
            try:
                with pd.ExcelWriter(os.path.join(EXPORTED, "review_screening.xlsx"), engine="openpyxl") as w:
                    screening.to_excel(w, index=False, sheet_name="Screening")
            except Exception:
                pass

            st.session_state.master_df = master
            st.session_state.screening_df = screening

        st.success(
            f"Done. {original_len} raw rows -> {len(master)} unique papers -> "
            f"{int(master['keep_for_manual_screening'].sum())} kept for manual review."
        )

    # ── Results ───────────────────────────────────────────────────────────────
    if "master_df" in st.session_state:
        master   = st.session_state.master_df
        screening = st.session_state.screening_df
        tag_cols_present = [c for c in master.columns if c.startswith("tag_")]
        label_map = {_tag_col(l): l for l, _, _ in valid_tags}

        st.divider()
        st.subheader("Results")

        m1, m2, m3 = st.columns(3)
        m1.metric("Total unique papers", len(master))
        m2.metric("Kept for manual review", int(master["keep_for_manual_screening"].sum()))
        m3.metric("Query groups loaded", master["query_group"].nunique())

        with st.expander("Tag hit rates — how many papers carry each label", expanded=True):
            tag_summary = pd.DataFrame([
                {
                    "Tag": label_map.get(c, c),
                    "Papers tagged": int(master[c].sum()),
                    "% of all papers": f"{master[c].mean()*100:.1f}%",
                }
                for c in tag_cols_present
            ])
            st.dataframe(tag_summary, use_container_width=True, hide_index=True)

        with st.expander("Papers per query group"):
            grp = master["query_group"].value_counts().reset_index()
            grp.columns = ["Query group", "Papers"]
            st.dataframe(grp, use_container_width=True, hide_index=True)

        with st.expander("Preview of papers kept for manual review — first 50", expanded=True):
            display_cols = (
                ["title", "abstract", "doi", "journal", "date", "query_group"]
                + tag_cols_present
            )
            display_cols = [c for c in display_cols if c in screening.columns]
            preview = screening[display_cols].head(50).rename(columns=label_map)
            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "title":    st.column_config.TextColumn("Title",    width="large"),
                    "abstract": st.column_config.TextColumn("Abstract", width="large"),
                    "doi":      st.column_config.LinkColumn("DOI",      width="small",
                                                            display_text=r"(.+)"),
                    "journal":  st.column_config.TextColumn("Journal",  width="medium"),
                    "date":     st.column_config.TextColumn("Date",     width="small"),
                },
            )

        st.divider()
        st.subheader("Download outputs")
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                "All papers (CSV)",
                data=master.to_csv(index=False).encode(),
                file_name="review_master.csv", mime="text/csv",
                help="Every unique paper from the scrape, with all tags.",
            )
        with dl2:
            st.download_button(
                "Shortlist for review (CSV)",
                data=screening.to_csv(index=False).encode(),
                file_name="review_screening.csv", mime="text/csv",
                help="Only papers that passed the screening rule.",
            )
        with dl3:
            st.download_button(
                "Shortlist for review (Excel)",
                data=df_to_xlsx_bytes(screening),
                file_name="review_screening.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Same as CSV but formatted for easy manual reading in Excel.",
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — FIGURES
# ══════════════════════════════════════════════════════════════════════════════
with tab_figs:
    st.header("Figures")

    # ── helpers ────────────────────────────────────────────────────────────────
    def _figure_card(title: str, img_bytes: bytes, filename: str):
        st.markdown(f"#### {title}")
        st.image(img_bytes, use_container_width=True)
        st.download_button(
            f"Download {filename}",
            data=img_bytes,
            file_name=filename,
            mime="image/png",
            key=f"dl_{filename}_{id(img_bytes)}",
        )
        st.divider()

    def _emit_fig(title: str, img_bytes: bytes, filename: str):
        """Store figure in session state and render it."""
        if "generated_figs" not in st.session_state:
            st.session_state.generated_figs = []
        st.session_state.generated_figs.append((title, img_bytes, filename))
        _figure_card(title, img_bytes, filename)

    # ── REVIEW_GROUPS for figures (read from loaded query names) ──────────────
    REVIEW_GROUPS_FIG = list(REVIEW_PREFIXES)

    def _short(g: str) -> str:
        return g.replace("_BROAD", "").replace("_AGEFOCUSED", " (age-focused)").replace("_", " ").title()

    TAB_COLORS = [
        "#e377c2","#ff7f0e","#2ca02c","#9467bd","#1f77b4","#8c564b","#d62728","#7f7f7f",
    ]

    os.makedirs(IMAGES, exist_ok=True)
    # Show only figures generated in the current session
    if st.session_state.get("generated_figs"):
        for fig_title, fig_bytes, fig_filename in st.session_state.generated_figs:
            _figure_card(fig_title, fig_bytes, fig_filename)
        st.divider()

    # ── Figure selection & generation ─────────────────────────────────────────
    st.subheader("Generate figures")
    st.markdown("Select the figures you want to produce. Each will appear below with a download button.")

    FIGURES = {
        "papers_per_year": ("Papers per year",       "KDE density + line plot showing publication trend over time per query group"),
        "euler":           ("Query overlap (Venn)",  "How many papers are shared between different query groups (matched by title)"),
        "total_by_group":  ("Total papers per group","Bar chart of total paper count per query group — requires master table"),
        "tag_heatmap":     ("Tag co-occurrence",     "Heatmap of how often pairs of tags appear together in the screened set — requires master table"),
    }

    fig_checks = {}
    c1, c2 = st.columns(2)
    for i, (key, (label, desc)) in enumerate(FIGURES.items()):
        with (c1 if i % 2 == 0 else c2):
            fig_checks[key] = st.checkbox(f"{label}", value=True, key=f"fig_{key}", help=desc)

    selected = [k for k, v in fig_checks.items() if v]

    figs_json_dir = st.text_input(
        "JSONL folder (for Venn / per-year plots)",
        value="./json_files",
        key="figs_json_dir",
        help="Folder containing scraped JSONL files. Only needed for 'Papers per year' and 'Venn' figures.",
    )

    if st.button("Generate selected figures", type="primary", use_container_width=True, disabled=not selected):
        # Clear figures from any previous run so only the current run shows
        st.session_state.generated_figs = []

        abs_json = os.path.join(ROOT, figs_json_dir.lstrip("./"))
        if not os.path.isdir(abs_json):
            abs_json = figs_json_dir

        sns.set_theme(style="whitegrid", context="notebook", font_scale=1.05)
        os.makedirs(IMAGES, exist_ok=True)

        # helper: load raw jsonl per group
        def load_raw_groups(json_dir):
            group_dfs = {}
            for fname in sorted(os.listdir(json_dir)):
                if not fname.endswith(".jsonl"):
                    continue
                for group in REVIEW_GROUPS_FIG:
                    if fname.startswith(group):
                        m = re.search(r"_(\d{4})(?:_\d{4})?_PubMed", fname)
                        if not m:
                            continue
                        year = int(m.group(1))
                        path = os.path.join(json_dir, fname)
                        try:
                            df = pd.read_json(path, lines=True)
                        except Exception:
                            continue
                        if df.empty:
                            continue
                        df["_year"] = year
                        df["query_group"] = group
                        group_dfs.setdefault(group, []).append(df)
                        break
            return {g: pd.concat(fs, ignore_index=True) for g, fs in group_dfs.items() if fs}

        colors = {g: TAB_COLORS[i % len(TAB_COLORS)] for i, g in enumerate(REVIEW_GROUPS_FIG)}

        # Papers per year
        if "papers_per_year" in selected:
            with st.spinner("Generating papers per year…"):
                try:
                    gdfs = load_raw_groups(abs_json)
                    records = [
                        {"year": year, "query_group": g, "count": len(sub)}
                        for g, df in gdfs.items()
                        for year, sub in df.groupby("_year")
                    ]
                    count_df = pd.DataFrame(records)
                    kde_df = pd.concat(gdfs.values(), ignore_index=True)[["_year","query_group"]].rename(columns={"_year":"year"})
                    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
                    fig.suptitle("Papers published per year", fontsize=14, fontweight="bold")
                    for g in REVIEW_GROUPS_FIG:
                        sub = kde_df[kde_df["query_group"] == g]["year"]
                        if len(sub) >= 3:
                            sns.kdeplot(sub, ax=axes[0], label=_short(g), color=colors[g], linewidth=2)
                    axes[0].set_title("Density"); axes[0].set_xlabel("Year"); axes[0].set_ylabel("Density")
                    axes[0].legend(title="Query", fontsize=8); axes[0].xaxis.set_major_locator(mticker.MultipleLocator(5))
                    pivot = count_df.pivot_table(index="year", columns="query_group", values="count", fill_value=0)
                    for g in REVIEW_GROUPS_FIG:
                        if g in pivot.columns:
                            axes[1].plot(pivot.index, pivot[g], label=_short(g), color=colors[g], linewidth=2)
                    axes[1].set_title("Raw count"); axes[1].set_xlabel("Year"); axes[1].set_ylabel("Papers")
                    axes[1].legend(title="Query", fontsize=8); axes[1].xaxis.set_major_locator(mticker.MultipleLocator(5))
                    plt.tight_layout()
                    path = os.path.join(IMAGES, "#Papers_per_year.png")
                    fig.savefig(path, dpi=200, bbox_inches="tight")
                    _emit_fig("Papers per year", fig_to_png_bytes(fig), "papers_per_year.png")
                    plt.close(fig)
                except Exception as e:
                    st.error(f"papers_per_year: {e}")

        # Euler diagram (circle-style; clamp to top 3 groups)
        if "euler" in selected:
            with st.spinner("Generating Euler diagram..."):
                try:
                    from matplotlib_venn import venn2, venn3

                    gdfs = load_raw_groups(abs_json)
                    # Build sets keyed by short label; keep only non-empty
                    sets: dict[str, set] = {
                        _short(g): set(df["title"].apply(normalize_title).dropna())
                        for g, df in gdfs.items()
                        if "title" in df.columns and df["title"].notna().any()
                    }
                    sets = {k: v for k, v in sets.items() if v}
                    n_sets = len(sets)

                    if n_sets < 2:
                        st.warning(
                            f"Need at least 2 query groups with data to draw an Euler diagram. "
                            f"Found {n_sets}. Run the scrape first."
                        )
                    else:
                        # If more than 3 groups, keep the 3 largest so we always
                        # get a clean circle-style Euler diagram instead of a
                        # spiky polygon layout.
                        if n_sets > 3:
                            sets = dict(sorted(sets.items(), key=lambda x: -len(x[1]))[:3])
                            st.info("Showing the 3 largest query groups in the Euler diagram.")

                        labels = list(sets.keys())
                        set_list = [sets[l] for l in labels]

                        fig, ax = plt.subplots(figsize=(10, 8))

                        if len(set_list) == 2:
                            venn2(set_list, set_labels=labels, ax=ax)
                        else:
                            # len == 3 after clamping above
                            venn3(set_list, set_labels=labels, ax=ax)

                        ax.set_title(
                            "Euler diagram — paper overlap between query groups\n(matched by normalised title)",
                            fontsize=13, fontweight="bold", pad=18,
                        )
                        plt.tight_layout()
                        path = os.path.join(IMAGES, "Euler_Diagram.png")
                        fig.savefig(path, dpi=200, bbox_inches="tight")
                        _emit_fig("Euler diagram", fig_to_png_bytes(fig), "Euler_Diagram.png")
                        plt.close(fig)
                except Exception as e:
                    st.error(f"Could not generate Euler diagram: {e}")

        # Master-table based figures
        master_path = os.path.join(EXPORTED, "review_master.csv")
        screening_path = os.path.join(EXPORTED, "review_screening.csv")
        needs_master = any(k in selected for k in ("total_by_group", "tag_heatmap"))
        if needs_master:
            if not os.path.exists(master_path):
                st.warning("Master table not found — run Build Master Table first, then regenerate figures.")
            else:
                master = pd.read_csv(master_path)
                screening = pd.read_csv(screening_path)
                master["date"] = pd.to_datetime(master["date"], errors="coerce")
                master["year"] = master["date"].dt.year
                screening["date"] = pd.to_datetime(screening["date"], errors="coerce")
                tag_cols_m = [c for c in master.columns if c.startswith("tag_")]

                if "total_by_group" in selected:
                    with st.spinner("Total by group..."):
                        df_g = master.groupby("query_group").size().reset_index(name="count").sort_values("count", ascending=False)
                        fig, ax = plt.subplots(figsize=(8, 5))
                        sns.barplot(data=df_g, x="count", y="query_group", hue="query_group", palette="viridis", legend=False, ax=ax)
                        ax.set_title("Total papers per query group"); ax.set_xlabel("Papers"); ax.set_ylabel("")
                        plt.tight_layout()
                        path = os.path.join(IMAGES, "total_papers_by_group.png")
                        fig.savefig(path, dpi=200, bbox_inches="tight")
                        _emit_fig("Total papers per query group", fig_to_png_bytes(fig), "total_papers_by_group.png")
                        plt.close(fig)

                if "tag_heatmap" in selected and tag_cols_m:
                    with st.spinner("Tag co-occurrence heatmap..."):
                        tags = screening[tag_cols_m].astype(bool)
                        n = max(len(tags), 1)
                        co = pd.DataFrame({a: {b: (tags[a]&tags[b]).sum()/n for b in tag_cols_m} for a in tag_cols_m})
                        fig, ax = plt.subplots(figsize=(8, 6))
                        sns.heatmap(co, annot=True, fmt=".2f", cmap="mako", vmin=0, vmax=1, ax=ax)
                        ax.set_title("Tag co-occurrence\n(fraction of screened papers where both tags appear)")
                        plt.tight_layout()
                        path = os.path.join(IMAGES, "tag_cooccurrence_heatmap.png")
                        fig.savefig(path, dpi=200, bbox_inches="tight")
                        _emit_fig("Tag co-occurrence", fig_to_png_bytes(fig), "tag_cooccurrence_heatmap.png")
                        plt.close(fig)

        st.success("Done. All generated figures are saved to `images/`.")
