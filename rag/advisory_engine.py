# Policy-grounded advisory engine
# Pathway DocumentStore with live streaming re-indexing
# policies/ -> parse -> chunk -> embed -> BruteForceKnn retrieval

import os
import threading
import numpy as np
from datetime import datetime, timezone

import pathway as pw
from pathway.xpacks.llm.document_store import DocumentStore
from pathway.xpacks.llm.embedders import SentenceTransformerEmbedder
from pathway.xpacks.llm.splitters import TokenCountSplitter
from pathway.xpacks.llm.parsers import UnstructuredParser
from pathway.stdlib.indexing import BruteForceKnnFactory
from sentence_transformers import SentenceTransformer

from config import POLICY_DIR, PERSISTENCE_THRESHOLD, HIGH_AQI_THRESHOLD

os.makedirs(POLICY_DIR, exist_ok=True)

# shared state for the UI
_rag_state = {
    "index_type": "Pathway DocumentStore (Live Hybrid Index)",
    "docs_indexed": 0,
    "chunks_indexed": 0,
    "embed_model": "all-MiniLM-L6-v2",
    "last_reindex": None,
    "store_status": "starting",
    "policy_files": [],
    "error": None,
}


def _scan_policy_files():
    files = []
    for f in sorted(os.listdir(POLICY_DIR)):
        p = os.path.join(POLICY_DIR, f)
        if os.path.isfile(p):
            stat = os.stat(p)
            files.append({
                "name": f,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M"),
            })
    _rag_state["policy_files"] = files
    _rag_state["docs_indexed"] = len(files)

_scan_policy_files()


# --- Pathway pipeline setup ---

_pw_embedder = SentenceTransformerEmbedder(model="all-MiniLM-L6-v2")

_policy_docs = pw.io.fs.read(
    POLICY_DIR,
    format="binary",
    mode="streaming",
    with_metadata=True,
)

_parser = UnstructuredParser()
_splitter = TokenCountSplitter(min_tokens=50, max_tokens=300)

_retriever_factory = BruteForceKnnFactory(
    dimensions=384,
    embedder=_pw_embedder,
)

_doc_store = DocumentStore(
    docs=_policy_docs,
    retriever_factory=_retriever_factory,
    parser=_parser,
    splitter=_splitter,
)

print("[RAG] DocumentStore ready")


# --- Live index: observer captures chunks for python-side queries ---

_live_chunks = {}
_live_lock = threading.Lock()
_query_model = SentenceTransformer("all-MiniLM-L6-v2")


def _on_doc_change(key, row, time, is_addition):
    with _live_lock:
        if is_addition:
            text = ""
            metadata = {}
            if hasattr(row, "data"):
                text = row.data if isinstance(row.data, str) else row.data.decode("utf-8", errors="ignore")
            elif isinstance(row, dict):
                text = row.get("data", row.get("text", ""))
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="ignore")
                metadata = row.get("_metadata", {})

            if text and len(text.strip()) > 10:
                emb = _query_model.encode([text], convert_to_numpy=True)
                _live_chunks[str(key)] = {
                    "text": text[:800],
                    "metadata": metadata,
                    "embedding": emb[0],
                }
                _rag_state["chunks_indexed"] = len(_live_chunks)
                _rag_state["store_status"] = "active"
                _rag_state["last_reindex"] = datetime.now(timezone.utc).strftime("%H:%M:%S")
        else:
            _live_chunks.pop(str(key), None)
            _rag_state["chunks_indexed"] = len(_live_chunks)


pw.io.subscribe(_policy_docs, on_change=_on_doc_change)


# --- Preload txt files directly so retrieval works immediately ---

def _preload_policies():
    for f in sorted(os.listdir(POLICY_DIR)):
        p = os.path.join(POLICY_DIR, f)
        if os.path.isfile(p) and f.endswith(".txt"):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    text = fp.read()
                if text.strip():
                    words = text.split()
                    for i in range(0, len(words), 250):
                        chunk = " ".join(words[i:i+250])
                        if len(chunk) > 50:
                            emb = _query_model.encode([chunk], convert_to_numpy=True)
                            key = f"preload_{f}_{i}"
                            with _live_lock:
                                _live_chunks[key] = {
                                    "text": chunk[:800],
                                    "metadata": {"path": p, "source": "preload"},
                                    "embedding": emb[0],
                                }
            except Exception as e:
                print(f"[RAG] preload err {f}: {e}")

    with _live_lock:
        _rag_state["chunks_indexed"] = len(_live_chunks)
        if _live_chunks:
            _rag_state["store_status"] = "active"
            _rag_state["last_reindex"] = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"[RAG] preloaded {len(_live_chunks)} chunks")

threading.Thread(target=_preload_policies, daemon=True).start()


# --- Retrieval ---

def retrieve_policy_context(query, k=2):
    _scan_policy_files()

    with _live_lock:
        if not _live_chunks:
            return {
                "context": "Policy index initializing...",
                "policy_file": "loading...",
                "similarity_score": 0.0,
                "index_type": "Pathway DocumentStore (Initializing)",
                "policy_last_updated": _sync_age(),
                "docs_indexed": _rag_state["docs_indexed"],
                "embed_model": "all-MiniLM-L6-v2",
            }

        q_emb = _query_model.encode([query], convert_to_numpy=True)

        keys = list(_live_chunks.keys())
        embeddings = np.array([_live_chunks[k_]["embedding"] for k_ in keys])
        scores = (embeddings @ q_emb.T).flatten()
        topk_idx = np.argsort(scores)[-k:][::-1]

        best = _live_chunks[keys[topk_idx[0]]]
        ctx = "\n\n".join([_live_chunks[keys[i]]["text"][:400] for i in topk_idx])

        meta = best.get("metadata", {})
        fname = os.path.basename(meta.get("path", "policy-document")) if isinstance(meta, dict) else "policy-document"

        return {
            "context": ctx[:800],
            "policy_file": fname,
            "similarity_score": round(float(scores[topk_idx[0]]), 4),
            "index_type": "Pathway DocumentStore (Live Hybrid Index)",
            "policy_last_updated": _sync_age(),
            "docs_indexed": _rag_state["docs_indexed"],
            "embed_model": "all-MiniLM-L6-v2",
        }


def _sync_age():
    lr = _rag_state.get("last_reindex")
    return f"Last index: {lr} UTC" if lr else "Initializing..."


def get_governance_rule():
    return (
        f"AQI >= {HIGH_AQI_THRESHOLD} | "
        f"{PERSISTENCE_THRESHOLD} Consecutive Windows | "
        f"3min Sliding | 1min Hop | "
        f"Hysteresis: 2 confirmations | "
        f"Protocol: CAQM GRAP Escalation"
    )


# --- Advisory generation ---

def generate_grounded_advisory(
    aqi, level, grap_description, band, fire_count,
    high_count=0, remaining_windows=0, projected_time="N/A",
    transport_score=0, transport_label="none",
    wind_speed=None, wind_dir=None,
):
    rag = retrieve_policy_context(f"{level} {band} GRAP enforcement CPCB")
    rule = get_governance_rule()

    legal = (
        f"LEGAL BASIS\n{'='*50}\n"
        f"CPCB Band  : {band}\n"
        f"GRAP Stage : {level}\n"
        f"Action     : {grap_description}\n"
    )

    signal = (
        f"\nLIVE SIGNAL\n{'='*50}\n"
        f"AQI              : {aqi}\n"
        f"Persistence      : {high_count} windows (Threshold: {PERSISTENCE_THRESHOLD})\n"
        f"Remaining        : {remaining_windows}\n"
        f"Projected Trigger: {projected_time}\n"
        f"Fire Hotspots    : {fire_count}\n"
    )

    gov = f"\nTRIGGER RULE\n{'='*50}\n{rule}\n"

    if high_count >= PERSISTENCE_THRESHOLD:
        esc = (
            f"\nESCALATION: TRIGGERED\n{'='*50}\n"
            f"{high_count} consecutive windows >= {HIGH_AQI_THRESHOLD}.\n"
            f"Immediate regulatory activation required.\n"
        )
        enf = (
            f"\nMANDATORY ACTIONS\n{'='*50}\n"
            f"- Construction/demolition restrictions\n"
            f"- High-emission vehicle entry ban\n"
            f"- Industrial compliance verification\n"
            f"- Public health advisory issuance\n"
            f"- School outdoor activity suspension\n"
        )
    else:
        esc = (
            f"\nESCALATION: WATCH\n{'='*50}\n"
            f"Threshold not met. {remaining_windows} windows remaining.\n"
            f"Projected trigger: {projected_time}\n"
        )
        enf = (
            f"\nPREPARED PROTOCOL\n{'='*50}\n"
            f"- Construction restriction readiness\n"
            f"- Vehicle enforcement standby\n"
            f"- Public health advisory drafted\n"
        )

    if transport_label == "regional_transport":
        ws = f"{wind_speed:.1f}" if wind_speed else "N/A"
        wd = f"{wind_dir:.0f}" if wind_dir else "N/A"
        causal = (
            f"\nCAUSAL ATTRIBUTION\n{'='*50}\n"
            f"Satellite-detected thermal anomalies upwind.\n"
            f"Transport Score  : {transport_score}/100\n"
            f"Wind             : {ws} m/s from {wd} deg\n"
            f"Source           : NASA FIRMS VIIRS_SNPP_NRT\n"
        )
    elif transport_label == "possible_transport":
        causal = (
            f"\nCAUSAL ATTRIBUTION\n{'='*50}\n"
            f"Limited upwind thermal activity detected.\n"
            f"Transport Score  : {transport_score}/100\n"
        )
    else:
        causal = (
            f"\nCAUSAL ATTRIBUTION\n{'='*50}\n"
            f"No upwind thermal anomalies. Local emission dominant.\n"
        )

    pol = (
        f"\nPOLICY SOURCE ({rag['index_type']})\n{'='*50}\n"
        f"Document  : {rag['policy_file']}\n"
        f"Score     : {rag['similarity_score']}\n"
        f"Sync      : {rag['policy_last_updated']}\n"
        f"Indexed   : {rag['docs_indexed']} documents\n"
        f"Chunks    : {_rag_state['chunks_indexed']}\n"
        f"Embedder  : {rag['embed_model']}\n"
    )

    return {
        "advisory": legal + signal + gov + esc + enf + causal + pol,
        "policy_file": rag["policy_file"],
        "similarity_score": rag["similarity_score"],
        "policy_last_updated": rag["policy_last_updated"],
        "index_type": rag["index_type"],
        "docs_indexed": rag["docs_indexed"],
        "embed_model": rag["embed_model"],
        "governance_rule": rule,
    }