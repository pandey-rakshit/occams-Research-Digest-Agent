import json
import os
import sys
import tempfile

import streamlit as st

from config.logging_config import setup_logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


setup_logging()

st.set_page_config(page_title="Research Digest Agent", page_icon="📑", layout="wide")

STATUS_ICONS = {"success": "✅", "failed": "❌", "empty": "⚠️"}


def render_sidebar():
    with st.sidebar:
        st.header("Configuration")

        input_mode = st.radio("Input Mode", ["URLs", "Upload Files", "Both"])

        urls = []
        uploaded_files = []

        if input_mode in ["URLs", "Both"]:
            url_input = st.text_area(
                "Enter URLs (one per line)",
                placeholder="https://example.com/article1\nhttps://example.com/article2",
                height=150,
            )
            urls = [u.strip() for u in url_input.strip().split("\n") if u.strip()]

        if input_mode in ["Upload Files", "Both"]:
            uploaded_files = st.file_uploader(
                "Upload .txt or .html files",
                type=["txt", "html", "htm"],
                accept_multiple_files=True,
            )

        st.divider()
        st.subheader("Advanced Settings")

        similarity_threshold = st.slider(
            "Grouping Similarity Threshold",
            min_value=0.5,
            max_value=0.95,
            value=0.80,
            step=0.05,
            help="Higher = stricter grouping",
        )

        chunk_size = st.number_input(
            "Chunk Size", min_value=200, max_value=3000, value=1000, step=100
        )
        chunk_overlap = st.number_input(
            "Chunk Overlap", min_value=0, max_value=500, value=200, step=50
        )

        st.divider()
        show_history = st.toggle("Show Last Run", value=False, help="Load results from the previous pipeline run")

    return urls, uploaded_files, similarity_threshold, chunk_size, chunk_overlap, show_history


def save_uploaded_files(uploaded_files):
    local_paths = []
    if not uploaded_files:
        return local_paths

    temp_dir = tempfile.mkdtemp()
    for uf in uploaded_files:
        path = os.path.join(temp_dir, uf.name)
        with open(path, "wb") as f:
            f.write(uf.getbuffer())
        local_paths.append(path)

    return local_paths


def run_pipeline(urls, local_paths, similarity_threshold, chunk_size, chunk_overlap):
    from src.grouping.deduplicator import ClaimDeduplicator
    from src.orchestrator import ResearchDigestOrchestrator
    from src.processing.chunker import DocumentChunker

    orchestrator = ResearchDigestOrchestrator(
        chunker=DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
        deduplicator=ClaimDeduplicator(similarity_threshold=similarity_threshold),
    )

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    return (
        orchestrator.run(urls=urls, local_paths=local_paths, output_dir=output_dir),
        output_dir,
    )


def render_metrics(result):
    col1, col2, col3, col4 = st.columns(4)
    sources = result["sources"]

    col1.metric(
        "Sources Processed", sum(1 for s in sources if s.metadata.status == "success")
    )
    col2.metric(
        "Failed Sources", sum(1 for s in sources if s.metadata.status == "failed")
    )
    col3.metric("Total Claims", result["total_claims"])
    col4.metric("Claim Groups", len(result["claim_groups"]))


def render_digest_tab(result):
    st.markdown(result["digest_md"])


def render_claims_tab(result):
    for group in result["claim_groups"]:
        conflict_tag = " ⚠️ Conflicting" if group.is_conflicting else ""
        label = f"Group {group.group_id + 1}: {group.theme[:80]}...{conflict_tag}"

        with st.expander(
            f"{label}  |  {len(group.claims)} claims, {len(group.source_ids)} sources"
        ):
            for claim in group.claims:
                st.markdown(f"**Claim:** {claim.claim_text}")
                st.markdown(f"> {claim.supporting_quote}")
                st.caption(f"Source: {claim.source_title or claim.source_id}")
                st.divider()


def render_sources_tab(result):
    for source in result["sources"]:
        icon = STATUS_ICONS.get(source.metadata.status, "❓")
        title = source.metadata.title or source.metadata.source_path

        with st.expander(f"{icon} {title}"):
            st.write(f"**Type:** {source.metadata.source_type}")
            st.write(f"**Path:** {source.metadata.source_path}")
            st.write(f"**Length:** {source.metadata.char_length:,} chars")
            st.write(f"**Status:** {source.metadata.status}")

            if source.metadata.error_message:
                st.error(source.metadata.error_message)
            if source.claims:
                st.write(f"**Claims extracted:** {len(source.claims)}")


def render_downloads_tab(output_dir):
    digest_path = os.path.join(output_dir, "digest.md")
    sources_path = os.path.join(output_dir, "sources.json")

    if os.path.exists(digest_path):
        with open(digest_path, "r") as f:
            st.download_button(
                "Download digest.md",
                f.read(),
                file_name="digest.md",
                mime="text/markdown",
            )

    if os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            st.download_button(
                "Download sources.json",
                f.read(),
                file_name="sources.json",
                mime="application/json",
            )


def load_last_run(output_dir):
    digest_path = os.path.join(output_dir, "digest.md")
    sources_path = os.path.join(output_dir, "sources.json")

    if not os.path.exists(digest_path) and not os.path.exists(sources_path):
        return None

    last_run = {}

    if os.path.exists(digest_path):
        with open(digest_path, "r", encoding="utf-8") as f:
            last_run["digest_md"] = f.read()

    if os.path.exists(sources_path):
        with open(sources_path, "r", encoding="utf-8") as f:
            last_run["sources_json"] = json.load(f)

    return last_run


def render_last_run(last_run, output_dir):
    st.subheader("Last Run Results")

    tab1, tab2, tab3 = st.tabs(["Digest", "Sources", "Downloads"])

    with tab1:
        if "digest_md" in last_run:
            st.markdown(last_run["digest_md"])
        else:
            st.info("No digest found.")

    with tab2:
        if "sources_json" in last_run:
            sources_list = last_run["sources_json"].get("sources", [])
            for source in sources_list:
                title = source.get("title") or source.get("source_path", "Unknown")
                status = source.get("status", "unknown")
                icon = STATUS_ICONS.get(status, "❓")
                claim_count = len(source.get("claims", []))
                with st.expander(f"{icon} {title} ({claim_count} claims)"):
                    st.write(f"**Type:** {source.get('source_type', 'N/A')}")
                    st.write(f"**Path:** {source.get('source_path', 'N/A')}")
                    st.write(f"**Length:** {source.get('char_length', 0):,} chars")
                    st.write(f"**Status:** {status}")
                    if source.get("error"):
                        st.error(source["error"])
                    for claim in source.get("claims", []):
                        st.markdown(f"**Claim:** {claim.get('claim', '')}")
                        st.markdown(f"> {claim.get('supporting_quote', '')}")
                        st.divider()
        else:
            st.info("No sources found.")

    with tab3:
        render_downloads_tab(output_dir)


def main():
    st.title("Research Digest Agent")
    st.caption(
        "Ingest sources, extract claims, deduplicate, and generate structured research briefs."
    )

    urls, uploaded_files, threshold, chunk_size, chunk_overlap, show_history = render_sidebar()

    output_dir = os.path.join(os.path.dirname(__file__), "output")

    if show_history:
        last_run = load_last_run(output_dir)
        if last_run:
            render_last_run(last_run, output_dir)
            st.divider()
        else:
            st.info("No previous run found. Run the pipeline first.")
            st.divider()

    total_sources = len(urls) + len(uploaded_files or [])
    st.info(f"**{total_sources}** source(s) configured. Minimum 5 recommended.")

    if not st.button(
        "Run Digest Pipeline", type="primary", disabled=(total_sources == 0)
    ):
        return

    if total_sources == 0:
        st.error("Please provide at least one source.")
        return

    local_paths = save_uploaded_files(uploaded_files)

    with st.spinner("Running pipeline... This may take a few minutes."):
        try:
            result, output_dir = run_pipeline(
                urls, local_paths, threshold, chunk_size, chunk_overlap
            )
        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            st.exception(e)
            return

    if result["status"] == "error":
        st.error(result["message"])
        return

    st.success("Pipeline completed successfully!")
    render_metrics(result)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Digest", "Claims & Groups", "Sources", "Downloads"]
    )

    with tab1:
        render_digest_tab(result)
    with tab2:
        render_claims_tab(result)
    with tab3:
        render_sources_tab(result)
    with tab4:
        render_downloads_tab(output_dir)


if __name__ == "__main__":
    main()
