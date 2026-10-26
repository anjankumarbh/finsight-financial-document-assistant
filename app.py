"""FinSight localhost interface. Run with: streamlit run app.py"""

import hashlib
import re
import time

import streamlit as st

from src.agent import answer_question
from src.config import Settings, UPLOAD_DIR, api_key, ensure_directories
from src.documents import read_document
from src.mapping import parse_number, suggest_field
from src.rag import SearchIndex
from src.storage import clear_workspace, save_processed, save_upload

# Configure Streamlit and create the local data folders before drawing the page.
st.set_page_config(page_title="FinSight", page_icon="📊", layout="wide")
ensure_directories()
settings = Settings()

# These friendly names keep internal field names out of the user-facing tables.
FIELD_LABELS = {
    "revenue": "Revenue",
    "net_profit": "Net profit",
    "operating_cash_flow": "Operating cash flow",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
}


# ---------- Workspace state and upload processing ----------


def init_state() -> None:
    """Create the Streamlit state used by the upload, analysis, and chat screens."""
    # Streamlit reruns this file after most clicks, so these values keep the
    # workspace alive between reruns.
    st.session_state.setdefault("documents", {})
    st.session_state.setdefault("rejected_documents", {})
    st.session_state.setdefault("field_mappings", {})
    st.session_state.setdefault("mapping_context", "")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("uploader_version", 0)
    st.session_state.setdefault("upload_attempts", {})

    if "index" in st.session_state:
        return

    # Build the search index once, then restore files saved by an earlier run.
    st.session_state.index = SearchIndex()
    for saved_path in sorted(UPLOAD_DIR.iterdir()):
        if not saved_path.is_file():
            continue
        try:
            record = read_document(saved_path.name, saved_path.read_bytes())
            st.session_state.documents[saved_path.name] = record
            st.session_state.index.add_document(record.text, record.source)
        except Exception as exc:
            st.session_state.rejected_documents[saved_path.name] = str(exc)


def reset_workspace() -> None:
    """Remove saved files and reset every in-memory value."""
    next_uploader_version = int(st.session_state.get("uploader_version", 0)) + 1
    clear_workspace()
    st.session_state.clear()
    st.session_state.uploader_version = next_uploader_version


def discover_values() -> list[dict]:
    """Find numeric financial rows that can be shown in the mapping table."""
    found: list[dict] = []
    for name, record in st.session_state.documents.items():
        for table in record.tables:
            if table.empty or len(table.columns) < 2:
                continue
            label_column = table.columns[0]
            period_columns = list(table.columns[1:])
            for _, row in table.iterrows():
                original_label = row[label_column]
                field, _ = suggest_field(original_label)
                if not field:
                    continue
                for period_column in period_columns:
                    number = parse_number(row[period_column])
                    if number is not None:
                        found.append(
                            {
                                "field": field,
                                "original_label": str(original_label),
                                "period": str(period_column),
                                "value": number,
                                "source": f"{name} / {original_label}",
                            }
                        )
    return found


def friendly_field(field: str | None) -> str:
    """Convert an internal field key into a readable label for the UI."""
    if not field or field == "__skip__":
        return "Skip this field"
    return FIELD_LABELS.get(field, field.replace("_", " ").title())


# ---------- Streamlit rendering helpers ----------


def stream_answer(text: str):
    """Yield small pieces so the first answer appears with a light typing effect."""
    for piece in re.split(r"(\s+)", text):
        if piece:
            yield piece
            time.sleep(0.012)


# Process one upload separately so one bad file does not block valid files.
def process_upload(upload) -> str:
    """Read, save, and index one upload, returning its result status."""
    name = upload.name
    if name in st.session_state.documents:
        return "duplicate"

    data = upload.getvalue()
    fingerprint = hashlib.sha256(data).hexdigest()
    if st.session_state.upload_attempts.get(name) == fingerprint:
        return "skipped"

    try:
        with st.spinner(f"Reading {name} and preparing its evidence..."):
            record = read_document(name, data)
            save_upload(name, data)
            count = st.session_state.index.add_document(record.text, record.source)
            st.session_state.documents[name] = record
            processed_info = {
                "document_id": record.document_id,
                "chunks": count,
                "warnings": record.warnings,
            }
            save_processed(name, processed_info)
        st.session_state.upload_attempts.pop(name, None)
        st.session_state.last_upload_message = (
            f"{name}: read successfully and indexed {count} text chunk(s)."
        )
        return "accepted"
    except Exception as exc:
        st.session_state.rejected_documents[name] = str(exc)
        st.session_state.upload_attempts[name] = fingerprint
        return "rejected"


# ---------- Page sections ----------


def render_sidebar() -> None:
    """Show short workspace and configuration information in the sidebar."""
    with st.sidebar:
        st.header("Workspace status")
        st.write("Supported: PDF, TXT, CSV, Excel")
        st.write(f"File limit: {settings.max_file_mb:g} MB each")
        if api_key():
            st.success("Gemini key detected")
        else:
            st.warning("Gemini key not configured. Local reading still works.")


def render_upload_area() -> None:
    """Render the uploader and the accepted/rejected file lists."""
    st.markdown("### Upload documents")
    st.caption("PDF, TXT, CSV, or Excel files")
    uploads = st.file_uploader(
        "Choose files to upload",
        accept_multiple_files=True,
        key=f"document_uploader_{st.session_state.uploader_version}",
        help="DOCX, ZIP, Markdown, and other unsupported formats are rejected.",
    )
    if uploads:
        results = []
        for upload in uploads:
            results.append(process_upload(upload))
        accepted = "accepted" in results
        rejected = "rejected" in results or bool(st.session_state.rejected_documents)
        if accepted and not rejected:
            st.success("Document reading is complete. Analysis and Chat are ready.")
        elif accepted and rejected:
            st.info(
                "Some files were rejected. Please upload PDF, TXT, CSV, or Excel files."
            )
        elif "rejected" in results:
            st.warning(
                "Some files were rejected. Please upload PDF, TXT, CSV, or Excel files."
            )

    if st.session_state.documents:
        st.markdown("**Uploaded documents**")
        for name in st.session_state.documents:
            st.markdown(
                f"<div style='color:#16803c; padding:0.15rem 0;'>✅ {name}</div>",
                unsafe_allow_html=True,
            )
    if st.session_state.rejected_documents:
        st.markdown("**Rejected files**")
        for name in st.session_state.rejected_documents:
            st.markdown(
                f"<div style='color:#c62828; padding:0.15rem 0;'>❌ {name}</div>",
                unsafe_allow_html=True,
            )
        st.caption("Please upload the supported formats mentioned above.")


def render_analysis_panel() -> None:
    """Show detected financial labels and allow a user to review mappings."""
    st.info(
        "Recognized financial labels are mapped automatically. Review the final mapping when a document uses an unusual label."
    )
    discovered = discover_values()
    if discovered:
        detected_by_label: dict[str, str] = {}
        source_by_label: dict[str, str] = {}
        for item in discovered:
            detected_by_label.setdefault(item["original_label"], item["field"])
            source_by_label.setdefault(item["original_label"], item["source"])

        automatic_rows = []
        for label, field in detected_by_label.items():
            automatic_rows.append(
                {
                    "Document label": label,
                    "Detected mapping": friendly_field(field),
                    "Source": source_by_label[label],
                }
            )
        st.dataframe(automatic_rows, width="stretch", hide_index=True)
        st.caption(
            "Straightforward labels are mapped directly. Use the review section only if a mapping needs correction."
        )

        mapping_choices: dict[str, str | None] = {}
        with st.expander("Review or change mappings", expanded=False):
            options = ["__skip__", *FIELD_LABELS.keys()]
            for index, (label, detected_field) in enumerate(detected_by_label.items()):
                detected_index = (
                    options.index(detected_field) if detected_field in options else 0
                )
                selected = st.selectbox(
                    f"{label} (detected as {friendly_field(detected_field)})",
                    options,
                    index=detected_index,
                    format_func=friendly_field,
                    key=f"mapping_choice_{index}",
                    help="Change this only when the document label was interpreted incorrectly.",
                )
                mapping_choices[label] = None if selected == "__skip__" else selected

        final_mapping_rows = []
        for label, detected_field in detected_by_label.items():
            final_field = mapping_choices.get(label, detected_field)
            decision = (
                "Changed by user" if final_field != detected_field else "Automatic"
            )
            final_mapping_rows.append(
                {
                    "Document label": label,
                    "Final mapping": friendly_field(final_field),
                    "Decision": decision,
                }
            )
        st.session_state.field_mappings = {
            label: mapping_choices.get(label, detected_field)
            for label, detected_field in detected_by_label.items()
            if mapping_choices.get(label, detected_field)
        }
        st.session_state.mapping_context = "\n".join(
            f"{label} → {friendly_field(field)}"
            for label, field in st.session_state.field_mappings.items()
        )
        st.markdown("**Final document-to-financial mapping**")
        st.dataframe(final_mapping_rows, width="stretch", hide_index=True)
    elif st.session_state.documents:
        st.warning(
            "No recognised financial rows were found. Check that a table contains labels such as Revenue or Net profit."
        )
    else:
        st.info(
            "Upload a financial table to see recognized labels here. Chat works with narrative documents too."
        )


def render_chat_panel() -> None:
    """Render chat history and answer questions using retrieved evidence."""
    st.caption("Ask about the financial information in your uploaded documents.")
    if not st.session_state.documents:
        st.info(
            "📄 Please upload at least one supported document before asking a question."
        )
        st.caption(
            "Then ask about revenue, profit, cash flow, assets, risks, or another topic in your files."
        )
        return
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input(
        "Example: What changed in revenue and profit?", key="chat_question"
    )
    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Collecting evidence from your uploaded documents..."):
                answer, _, _ = answer_question(
                    question, st.session_state.index, st.session_state.mapping_context
                )
            st.write_stream(stream_answer(answer))
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()


def render_panels() -> None:
    """Render the analysis section followed by the chat section."""
    st.markdown("### Analysis")
    render_analysis_panel()
    st.divider()
    st.markdown("### Ask FinSight")
    render_chat_panel()


# ---------- Page startup ----------


init_state()
st.markdown(
    """
    <style>
    .finsight-title {
        font-size: 2.7rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        color: #19324d;
        margin-bottom: 0.1rem;
    }
    .finsight-title span {color: #2e8b82;}
    .finsight-subtitle {
        font-size: 1.08rem;
        color: #526273;
        margin-bottom: 0.9rem;
    }
    .upload-intro {
        background: linear-gradient(90deg, #f2f8fb, #f2faf7);
        border: 1px solid #d9e8ee;
        border-radius: 12px;
        padding: 0.8rem 1rem;
        color: #31475b;
    }
    div[data-testid="stChatInput"],
    div[data-testid="stChatInput"] > div {
        border-color: #2e8b82 !important;
    }
    div[data-testid="stChatInput"]:focus-within,
    div[data-testid="stChatInput"] > div:focus-within {
        box-shadow: 0 0 0 2px rgba(46, 139, 130, 0.2) !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: #2e8b82 !important;
        box-shadow: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

top_left, top_right = st.columns([5, 1])
with top_left:
    st.markdown(
        '<div class="finsight-title">Fin<span>Sight</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="finsight-subtitle">Turn financial documents into clear, evidence-backed answers.</div>',
        unsafe_allow_html=True,
    )
with top_right:
    if st.button(
        "🧹 Clear workspace",
        help="Remove uploaded documents, rejected files, mappings, and chat history.",
        key="clear_workspace_top",
    ):
        reset_workspace()
        st.rerun()

render_sidebar()
st.markdown(
    '<div class="upload-intro">Upload supported financial files to begin.</div>',
    unsafe_allow_html=True,
)
render_upload_area()
st.divider()
render_panels()
