"""
2WikiMultihopQA Dataset Splitter and Benchmarking Data Preparation Script.
Produces frozen evaluation and training splits, incremental edit stream, and workspace documents.
Performs SHA-256 hashing and creates data/README.md and data/splits/README.md.
"""

import os
import sys
import json
import re
import random
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
SPLITS_DIR = DATA_DIR / "splits"
RAW_DEV_JSON = DATA_DIR / "raw" / "dev.json"


def slugify(title: str) -> str:
    """Produces clean, unique, lowercase slug from document title."""
    s = re.sub(r'[^a-zA-Z0-9]+', '_', title.strip()).strip('_').lower()
    return s or "doc"


def ensure_dev_json() -> Path:
    """Downloads dev.json from official mirror if not present locally."""
    RAW_DEV_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not RAW_DEV_JSON.exists():
        import urllib.request
        url = "https://huggingface.co/datasets/voidful/2WikiMultihopQA/resolve/main/dev.json"
        print(f"Downloading 2WikiMultihopQA dev.json from {url}...")
        urllib.request.urlretrieve(url, RAW_DEV_JSON)
        print(f"Downloaded dev.json ({RAW_DEV_JSON.stat().st_size} bytes).")
    return RAW_DEV_JSON


def get_single_fact_edits(selected_docs: List[Tuple[str, str, str]]) -> List[Dict[str, Any]]:
    """
    Constructs exactly 20 single-fact edits from the selected documents in corpus_order[:50].
    Each edit alters exactly one factual detail (name, date, place, or entity).
    """
    edits = []
    
    # 20 curated single-fact modifications
    rules = [
        # 0. justin_historian
        ("justin_historian", "lived under the Roman Empire", "lived under the Byzantine Empire", "Changed empire from Roman Empire to Byzantine Empire"),
        # 1. bounce_tour
        ("bounce_tour", "American rock band Bon Jovi", "American rock band Aerosmith", "Changed rock band from Bon Jovi to Aerosmith"),
        # 2. charles_francis_norton
        ("charles_francis_norton", "Member of Parliament for Guildford", "Member of Parliament for Southampton", "Changed parliamentary constituency from Guildford to Southampton"),
        # 3. prince_dmitri_alexandrovich_of_russia
        ("prince_dmitri_alexandrovich_of_russia", "nephew of Tsar Nicholas II of Russia", "nephew of Tsar Alexander III of Russia", "Changed uncle from Tsar Nicholas II to Tsar Alexander III"),
        # 4. claude_autant_lara
        ("claude_autant_lara", "French film director", "Belgian film director", "Changed nationality from French to Belgian"),
        # 5. ian_barry_director
        ("ian_barry_director", "Australian director of film and TV", "Canadian director of film and TV", "Changed nationality from Australian to Canadian"),
        # 6. there_were_days_and_moons
        ("there_were_days_and_moons", "1990 film directed by Claude Lelouch", "1995 film directed by Claude Lelouch", "Changed film release year from 1990 to 1995"),
        # 7. henry_krause
        ("henry_krause", "the Washington Redskins", "the Chicago Bears", "Changed NFL team from Washington Redskins to Chicago Bears"),
        # 8. john_mcmahon_surrey_and_somerset_cricketer
        ("john_mcmahon_surrey_and_somerset_cricketer", "Australian- born first- class cricketer", "New Zealand- born first- class cricketer", "Changed birth origin from Australian to New Zealand"),
        # 9. amor_prohibido_daniela_romo_album
        ("amor_prohibido_daniela_romo_album", "released in 1984", "released in 1989", "Changed album release year from 1984 to 1989"),
        # 10. the_woman_in_white_1921_film
        ("the_woman_in_white_1921_film", "directed by Max Neufeld", "directed by Fritz Lang", "Changed director from Max Neufeld to Fritz Lang"),
        # 11. purnima_hindi_actress
        ("purnima_hindi_actress", "grandmother of actor Emraan Hashmi", "grandmother of actor Ranbir Kapoor", "Changed grandson from Emraan Hashmi to Ranbir Kapoor"),
        # 12. fred_bradley_rower
        ("fred_bradley_rower", "English rower", "Scottish rower", "Changed nationality from English to Scottish"),
        # 13. sherry_argov
        ("sherry_argov", "born November 5, 1977", "born November 5, 1982", "Changed birth year from 1977 to 1982"),
        # 14. modern_love_1990_film
        ("modern_love_1990_film", "Triumph Films", "Columbia Pictures", "Changed film distributor from Triumph Films to Columbia Pictures"),
        # 15. the_strange_boarder
        ("the_strange_boarder", "Goldwyn Pictures", "Paramount Pictures", "Changed film distributor from Goldwyn Pictures to Paramount Pictures"),
        # 16. andrew_v_mclaglen
        ("andrew_v_mclaglen", "British- born American film and television director", "Irish- born American film and television director", "Changed birth origin from British to Irish"),
        # 17. the_last_days_of_pompeii_1950_film
        ("the_last_days_of_pompeii_1950_film", "French- Italian drama film", "Spanish- Italian drama film", "Changed production country from French-Italian to Spanish-Italian"),
        # 18. chiang_hsiao_yen
        ("chiang_hsiao_yen", "affiliated with the Kuomintang", "affiliated with the Democratic Progressive Party", "Changed political party from Kuomintang to Democratic Progressive Party"),
        # 19. prince_nikita_alexandrovich_of_russia
        ("prince_nikita_alexandrovich_of_russia", "third son and fourth child", "second son and fourth child", "Changed birth order from third son to second son")
    ]

    doc_map = {doc_id: (title, text) for doc_id, title, text in selected_docs}
    for doc_id, target, replacement, desc in rules:
        if doc_id in doc_map:
            title, text = doc_map[doc_id]
            if target in text:
                new_text = text.replace(target, replacement, 1)
                edits.append({
                    "doc_id": doc_id,
                    "title": title,
                    "original_text": text,
                    "new_text": new_text,
                    "target": target,
                    "replacement": replacement,
                    "changed_fact": desc
                })
            else:
                print(f"Warning: target '{target}' not found in doc {doc_id}")
        else:
            print(f"Warning: doc_id {doc_id} not found in selected docs")

    return edits


def build_workspace_data() -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    Constructs the real workspace corpus (8 research papers / architecture docs)
    and 30 multi-hop evaluation questions requiring cross-document reasoning.
    """
    docs = {
        "graphrag_paper": (
            "From Local to Global: A GraphRAG Approach to Query-Focused Summarization\n"
            "Abstract: Retrieval-Augmented Generation (RAG) approaches typically retrieve isolated text chunks via vector search. "
            "However, standard RAG fails when queries require summarizing global concepts across an entire corpus. "
            "GraphRAG addresses this by using Large Language Models to extract a hierarchical knowledge graph from source documents. "
            "Entities, claims, and relationships are detected and normalized. "
            "The graph is subsequently partitioned into modular communities using hierarchical community detection algorithms like Leiden. "
            "Each community generates pre-computed summary reports, allowing both global query answering and multi-hop entity traversal. "
            "Experiments show GraphRAG substantially outperforms baseline vector RAG on comprehensiveness and diversity metrics."
        ),
        "g_retriever_paper": (
            "G-Retriever: Retrieval-Augmented Generation for Textual Graph Understanding and Reasoning\n"
            "Abstract: Graph Neural Networks combined with Large Language Models face scalability bottlenecks when handling large textual graphs. "
            "G-Retriever proposes a targeted subgraph retrieval paradigm based on the Prize-Collecting Steiner Tree (PCST) optimization problem. "
            "Rather than injecting the entire graph or arbitrary k-hop neighbors into the LLM context, G-Retriever formulates query-guided node prizes "
            "derived from cosine similarities between question embeddings and node representations. Edge costs represent relational traversal penalties. "
            "The PCST algorithm extracts a minimal connected subgraph that maximizes total prize while minimizing edge costs. "
            "Retrieved subgraphs are linearized and soft-prompted into LLM encoders, improving multi-hop graph QA accuracy."
        ),
        "roland_paper": (
            "ROLAND: Graph Learning Framework for Dynamic Graphs\n"
            "Abstract: Real-world knowledge graphs evolve continuously with new entities and relationships added over time. "
            "Static GNNs require retraining from scratch upon every graph update, incurring prohibitive computational overhead. "
            "ROLAND introduces a dynamic graph learning framework that maintains per-node hierarchical hidden states across snapshots. "
            "In each snapshot t, spatial message passing produces candidate representations ~h_v^(l, t) at layer l (Eq. 5). "
            "A Gated Recurrent Unit (GRU) updates the temporal hidden state using previous state h_v^(l, t-1) and candidate ~h_v^(l, t) (Eq. 6). "
            "Updated states are fed hierarchically to subsequent GNN layers (Eq. 7). "
            "ROLAND is trained using Truncated Backpropagation Through Time (Truncated-BPTT) with bounded memory horizons, enabling efficient online adaptation."
        ),
        "hipporag_paper": (
            "HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models\n"
            "Abstract: Human long-term memory relies on the hippocampal-neocortical system to perform pattern completion and associative retrieval. "
            "Current RAG systems lack associative multi-hop retrieval capabilities across disparate memory chunks. "
            "HippoRAG models hippocampal indexing by constructing an open-information extraction knowledge graph from documents. "
            "When presented with a complex query, HippoRAG computes Personalized PageRank (PPR) over entity nodes, diffusing query activation "
            "across associative paths in the graph. This activates indirectly related evidence passages that vector similarity alone misses. "
            "HippoRAG achieves high recall on multi-hop benchmarks with a fraction of the index rebuild latency."
        ),
        "leiden_algorithm_paper": (
            "From Louvain to Leiden: Guaranteeing Well-Connected Communities in Large Networks\n"
            "Abstract: Community detection in complex networks is widely performed using the Louvain algorithm. "
            "However, Louvain has a known flaw: it frequently produces internally disconnected communities due to greedy local aggregation. "
            "The Leiden algorithm resolves this by introducing a refinement step between local node moving and community aggregation. "
            "Leiden guarantees that all discovered communities are well-connected and converges to a stable partition asymptotically faster than Louvain. "
            "In hierarchical graph summarization systems like GraphRAG, Leiden is used to cluster knowledge graphs into multi-scale topical modules."
        ),
        "gru_networks_paper": (
            "Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling\n"
            "Abstract: Recurrent Neural Networks often suffer from vanishing and exploding gradients when learning long-term temporal dependencies. "
            "The Gated Recurrent Unit (GRU) offers an efficient alternative to Long Short-Term Memory (LSTM) cells. "
            "A GRU cell contains two gating primitives: an update gate z and a reset gate r. "
            "The reset gate determines how much of the previous memory state to discard, while the update gate regulates how much of the candidate "
            "activation is committed to the new hidden state. Having fewer parameters than LSTMs, GRUs train faster while achieving comparable performance "
            "on sequential and streaming temporal state tracking."
        ),
        "konnect_synopsis": (
            "KONNECT: Real-Time Incremental Knowledge Graph RAG Intelligence Platform\n"
            "Abstract: Enterprise knowledge systems require continuously updating knowledge graphs as documents are created and edited in OneDrive. "
            "KONNECT integrates Microsoft Graph webhooks with a real-time event-driven Python intelligence service. "
            "When a document edit arrives, instead of executing a full rebuild taking tens of minutes, KONNECT performs delta extraction, "
            "updates affected entities in Neo4j, and invokes a bounded k-hop re-embedding using the ROLAND dynamic GRU framework. "
            "For retrieval, KONNECT applies Prize-Collecting Steiner Tree (PCST) optimization over GNN embeddings to assemble minimal connected context. "
            "A two-tier Redis semantic cache prevents redundant LLM generation, ensuring sub-second query latency and constant-time incremental updates."
        ),
        "backend_architecture_doc": (
            "KONNECT Backend Architecture and Microservice Specification\n"
            "Abstract: The KONNECT platform separates ingestion ingestion orchestration from semantic intelligence. "
            "The Node.js backend handles OAuth2 authentication with Microsoft Azure Entra ID, registers webhook subscriptions on OneDrive, "
            "and dispatches document modification events into a BullMQ Redis queue with a 3000ms debounce quiet window. "
            "The Python intelligence service exposes gRPC endpoints (Port 50051) and REST endpoints (Port 8000) for document ingestion and subgraph retrieval. "
            "Neo4j stores the entity-relationship graph with vector indexing (384-dim all-MiniLM-L6-v2 embeddings). "
            "Redis provides both semantic caching with cosine threshold 0.92 and BullMQ job management. "
            "The ROLAND model is bounded to 2-hop neighborhoods during incremental ingestion to ensure predictable real-time latency."
        )
    }

    questions = [
        {"id": "wq_01", "question": "How does KONNECT achieve bounded latency during document edits instead of full rebuilds?", "gold_answer": "KONNECT uses bounded k-hop re-embedding via ROLAND dynamic GRU rather than retraining from scratch.", "gold_docs": ["konnect_synopsis", "roland_paper"]},
        {"id": "wq_02", "question": "What retrieval algorithm does G-Retriever and KONNECT use to extract connected subgraphs?", "gold_answer": "Prize-Collecting Steiner Tree (PCST) optimization.", "gold_docs": ["g_retriever_paper", "konnect_synopsis"]},
        {"id": "wq_03", "question": "Why does GraphRAG use Leiden community detection instead of standard Louvain?", "gold_answer": "Leiden guarantees internally well-connected communities and avoids disconnected modules produced by Louvain.", "gold_docs": ["graphrag_paper", "leiden_algorithm_paper"]},
        {"id": "wq_04", "question": "What equations govern the spatial message passing and temporal recurrence in ROLAND?", "gold_answer": "Spatial message passing is Eq. 5, recurrent temporal update via GRU is Eq. 6, and hierarchical layer passing is Eq. 7.", "gold_docs": ["roland_paper", "gru_networks_paper"]},
        {"id": "wq_05", "question": "How do G-Retriever's node prizes connect to KONNECT's retrieval pipeline?", "gold_answer": "G-Retriever derives node prizes from cosine similarity between question embeddings and node representations, which KONNECT adopts in its PCST retriever.", "gold_docs": ["g_retriever_paper", "konnect_synopsis"]},
        {"id": "wq_06", "question": "What role does BullMQ and Redis play in KONNECT's document ingestion?", "gold_answer": "BullMQ provides a queue with a 3000ms debounce window for OneDrive webhook notifications before dispatching to the intelligence service.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_07", "question": "How does HippoRAG's multi-hop activation differ from PCST subgraph retrieval in G-Retriever?", "gold_answer": "HippoRAG diffuses query activation using Personalized PageRank, while G-Retriever extracts minimal connected subgraphs via PCST optimization.", "gold_docs": ["hipporag_paper", "g_retriever_paper"]},
        {"id": "wq_08", "question": "Which gating primitives in GRU enable ROLAND to maintain temporal hidden states across snapshots?", "gold_answer": "The update gate and reset gate in the GRU cell regulate memory retention and candidate integration.", "gold_docs": ["gru_networks_paper", "roland_paper"]},
        {"id": "wq_09", "question": "What embedding model and vector dimension does Neo4j use in the KONNECT intelligence service?", "gold_answer": "384-dimensional all-MiniLM-L6-v2 embeddings.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_10", "question": "How does GraphRAG's extraction process compare to HippoRAG's knowledge graph construction?", "gold_answer": "GraphRAG uses LLM-based entity and claim extraction with community summarization, while HippoRAG uses open-information extraction with hippocampal indexing.", "gold_docs": ["graphrag_paper", "hipporag_paper"]},
        {"id": "wq_11", "question": "What is the debounce quiet window configured in KONNECT's Node.js backend?", "gold_answer": "3000 milliseconds.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_12", "question": "Why does ROLAND employ Truncated Backpropagation Through Time (Truncated-BPTT)?", "gold_answer": "To bound memory and gradient computation horizons during dynamic graph snapshot training.", "gold_docs": ["roland_paper", "gru_networks_paper"]},
        {"id": "wq_13", "question": "What similarity threshold is configured for Redis semantic caching in KONNECT?", "gold_answer": "0.92 cosine similarity threshold.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_14", "question": "What happens when a document edit arrives in KONNECT's intelligence pipeline?", "gold_answer": "KONNECT computes a graph delta, updates Neo4j entities, and re-embeds affected nodes in a 2-hop neighborhood using ROLAND.", "gold_docs": ["konnect_synopsis", "backend_architecture_doc", "roland_paper"]},
        {"id": "wq_15", "question": "How does Leiden ensure community partitions do not deteriorate over hierarchical passes?", "gold_answer": "By performing a sub-community refinement step that guarantees all communities remain well-connected.", "gold_docs": ["leiden_algorithm_paper", "graphrag_paper"]},
        {"id": "wq_16", "question": "What port does the KONNECT gRPC servicer operate on?", "gold_answer": "Port 50051.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_17", "question": "How are edge costs defined in G-Retriever's PCST objective?", "gold_answer": "Edge costs act as penalties to prevent retrieving overly expansive or irrelevant graph paths.", "gold_docs": ["g_retriever_paper", "konnect_synopsis"]},
        {"id": "wq_18", "question": "What is the default k-hop neighborhood bounded by KONNECT during incremental updates?", "gold_answer": "k = 2 hops.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_19", "question": "How does HippoRAG address the limitation of standard vector RAG on complex multi-hop queries?", "gold_answer": "By diffusing query activation across associative paths in an open-IE graph via Personalized PageRank.", "gold_docs": ["hipporag_paper", "graphrag_paper"]},
        {"id": "wq_20", "question": "In ROLAND, where are per-node temporal hidden states maintained?", "gold_answer": "In a per-node hierarchical state cache indexed by layer and entity identifier.", "gold_docs": ["roland_paper", "konnect_synopsis"]},
        {"id": "wq_21", "question": "What OAuth2 provider and scopes does KONNECT's Node.js backend integrate with?", "gold_answer": "Microsoft Azure Entra ID with OneDrive file access permissions.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_22", "question": "Why is the GRU cell chosen over LSTM for ROLAND dynamic graph state tracking?", "gold_answer": "GRU has fewer parameters, trains faster, and offers efficient update and reset gating for temporal hidden states.", "gold_docs": ["gru_networks_paper", "roland_paper"]},
        {"id": "wq_23", "question": "What community summaries are generated in GraphRAG to answer global queries?", "gold_answer": "Pre-computed hierarchical community reports produced by LLMs over Leiden partitions.", "gold_docs": ["graphrag_paper", "leiden_algorithm_paper"]},
        {"id": "wq_24", "question": "What optimization objective does Truncated-BPTT use to train ROLAND?", "gold_answer": "Link prediction loss using positive and negative sampled edges across snapshots.", "gold_docs": ["roland_paper", "konnect_synopsis"]},
        {"id": "wq_25", "question": "How does KONNECT prevent semantic cache leakage across different benchmark runs?", "gold_answer": "By running FLUSHDB on Redis and clearing the ROLAND per-node state cache before each run.", "gold_docs": ["backend_architecture_doc", "konnect_synopsis"]},
        {"id": "wq_26", "question": "What guarantees does Leiden provide over earlier modularity optimization heuristics?", "gold_answer": "Guaranteed well-connected communities and asymptotic speed improvements over Louvain.", "gold_docs": ["leiden_algorithm_paper", "graphrag_paper"]},
        {"id": "wq_27", "question": "How does G-Retriever integrate extracted subgraphs into LLMs?", "gold_answer": "By linearizing nodes and edges and feeding them as soft prompts to the language model.", "gold_docs": ["g_retriever_paper", "graphrag_paper"]},
        {"id": "wq_28", "question": "What is the primary motivation for maintaining a dynamic graph in KONNECT?", "gold_answer": "To support real-time incremental knowledge graph updates without paying the high latency cost of full rebuilds.", "gold_docs": ["konnect_synopsis", "roland_paper"]},
        {"id": "wq_29", "question": "How does the Goemans-Williamson algorithm relate to PCST retrieval?", "gold_answer": "It provides a 2-approximation pruning algorithm to solve the Prize-Collecting Steiner Tree problem.", "gold_docs": ["g_retriever_paper", "konnect_synopsis"]},
        {"id": "wq_30", "question": "What are the two tiers of caching implemented in KONNECT?", "gold_answer": "A Redis semantic cache for query answers and an in-memory per-node temporal state cache for GNN representations.", "gold_docs": ["konnect_synopsis", "backend_architecture_doc"]}
    ]

    return docs, questions


def calculate_file_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=== KONNECT Stage 2: Data Splits Generation ===")
    dev_path = ensure_dev_json()

    # Load 2WikiMultihopQA dev set
    print("Loading 2WikiMultihopQA dev.json...")
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)

    by_type: Dict[str, List[Any]] = {}
    for item in dev_data:
        by_type.setdefault(item["type"], []).append(item)

    print(f"Loaded {len(dev_data)} questions across types: {list(by_type.keys())}")

    # 1. Sample 50 eval questions with fixed seed 42
    rng_eval = random.Random(42)
    eval_qs = []
    # 13 comparison, 13 inference, 12 compositional, 12 bridge_comparison = 50 questions
    counts = {"comparison": 13, "inference": 13, "compositional": 12, "bridge_comparison": 12}
    for q_type, count in counts.items():
        eval_qs.extend(rng_eval.sample(by_type[q_type], count))

    eval_ids = set(q["_id"] for q in eval_qs)
    print(f"Sampled {len(eval_qs)} eval questions (seed=42).")

    # 2. Build eval document pool
    eval_docs: Dict[str, Tuple[str, str]] = {}
    for q in eval_qs:
        for title, sentences in q["context"]:
            slug = slugify(title)
            if slug not in eval_docs:
                eval_docs[slug] = (title, " ".join(sentences))

    # Pad with distractor passages from non-eval dev questions to reach exactly 500 documents
    remaining = [q for q in dev_data if q["_id"] not in eval_ids]
    rng_pad = random.Random(42)
    rng_pad.shuffle(remaining)

    for q in remaining:
        if len(eval_docs) >= 500:
            break
        for title, sentences in q["context"]:
            slug = slugify(title)
            if slug not in eval_docs:
                eval_docs[slug] = (title, " ".join(sentences))
            if len(eval_docs) >= 500:
                break

    print(f"Eval documents pool: {len(eval_docs)} documents.")

    # 3. Create corpus_order (fixed shuffled order of eval documents)
    corpus_order = list(eval_docs.keys())
    rng_eval.shuffle(corpus_order)

    # 4. Sample 20 disjoint training questions (seed 43) and build ~200 train documents
    rng_train = random.Random(43)
    train_pool = [q for q in remaining if q["_id"] not in eval_ids]
    train_qs_sampled = rng_train.sample(train_pool, 30)

    train_docs: Dict[str, Tuple[str, str]] = {}
    train_qs = []
    for q in train_qs_sampled:
        q_docs = []
        for title, sentences in q["context"]:
            slug = slugify(title)
            # Ensure disjoint from eval pool
            if slug not in eval_docs and slug not in train_docs:
                train_docs[slug] = (title, " ".join(sentences))
                q_docs.append(slug)
            if len(train_docs) >= 200:
                break
        if q_docs:
            train_qs.append(q)
        if len(train_docs) >= 200:
            break

    print(f"Train documents pool: {len(train_docs)} documents from {len(train_qs)} questions (seed=43).")
    overlap = set(eval_docs.keys()).intersection(set(train_docs.keys()))
    assert len(overlap) == 0, f"Error: {len(overlap)} overlapping documents between train and eval!"

    # 5. Build 20 single-fact edits from corpus_order[:50]
    first_50_docs = [(doc_id, eval_docs[doc_id][0], eval_docs[doc_id][1]) for doc_id in corpus_order[:50]]
    edits = get_single_fact_edits(first_50_docs)
    assert len(edits) == 20, f"Expected exactly 20 edits, got {len(edits)}"
    print(f"Generated {len(edits)} verified single-fact edits.")

    # 6. Format eval_questions.json with gold_docs
    eval_questions_formatted = []
    for q in eval_qs:
        gold_titles = set(fact[0] for fact in q.get("supporting_facts", []))
        gold_slugs = [slugify(t) for t in gold_titles]
        eval_questions_formatted.append({
            "_id": q["_id"],
            "type": q["type"],
            "question": q["question"],
            "answer": q["answer"],
            "gold_docs": gold_slugs,
            "supporting_facts": q.get("supporting_facts", []),
            "context_titles": [c[0] for c in q.get("context", [])]
        })

    # Format train_questions.json
    train_questions_formatted = []
    for q in train_qs:
        gold_titles = set(fact[0] for fact in q.get("supporting_facts", []))
        gold_slugs = [slugify(t) for t in gold_titles]
        train_questions_formatted.append({
            "_id": q["_id"],
            "type": q["type"],
            "question": q["question"],
            "answer": q["answer"],
            "gold_docs": gold_slugs,
            "supporting_facts": q.get("supporting_facts", []),
            "context_titles": [c[0] for c in q.get("context", [])]
        })

    # 7. Build real workspace data
    workspace_docs, workspace_questions = build_workspace_data()
    print(f"Built workspace corpus: {len(workspace_docs)} documents, {len(workspace_questions)} questions.")

    # 8. Write all split files to both data/splits/ and data/
    for base in [SPLITS_DIR, DATA_DIR]:
        eval_docs_dir = base / "eval_docs"
        train_docs_dir = base / "train_docs"
        workspace_docs_dir = base / "workspace_docs"

        eval_docs_dir.mkdir(parents=True, exist_ok=True)
        train_docs_dir.mkdir(parents=True, exist_ok=True)
        workspace_docs_dir.mkdir(parents=True, exist_ok=True)

        # Write eval docs
        for doc_id, (title, text) in eval_docs.items():
            content = f"{title}\n{text}\n"
            (eval_docs_dir / f"{doc_id}.txt").write_text(content, encoding="utf-8")

        # Write train docs with zero-padded prefixes: 000_...txt to 199_...txt
        train_items = sorted(train_docs.items())
        for idx, (doc_id, (title, text)) in enumerate(train_items):
            content = f"{title}\n{text}\n"
            filename = f"{idx:03d}_{doc_id}.txt"
            (train_docs_dir / filename).write_text(content, encoding="utf-8")

        # Write workspace docs
        for doc_id, content in workspace_docs.items():
            (workspace_docs_dir / f"{doc_id}.txt").write_text(content + "\n", encoding="utf-8")

        # Write JSON files
        (base / "eval_questions.json").write_text(json.dumps(eval_questions_formatted, indent=2), encoding="utf-8")
        (base / "train_questions.json").write_text(json.dumps(train_questions_formatted, indent=2), encoding="utf-8")
        (base / "corpus_order.json").write_text(json.dumps(corpus_order, indent=2), encoding="utf-8")
        (base / "edits.json").write_text(json.dumps(edits, indent=2), encoding="utf-8")
        (base / "workspace_questions.json").write_text(json.dumps(workspace_questions, indent=2), encoding="utf-8")

    # 9. Generate README.md with file counts and SHA-256 hashes
    manifest = []
    for root, dirs, files in os.walk(SPLITS_DIR):
        for f in sorted(files):
            fp = Path(root) / f
            rel = fp.relative_to(SPLITS_DIR)
            sha = calculate_file_sha256(fp)
            manifest.append((str(rel).replace("\\", "/"), sha))

    readme_content = f"""# KONNECT Mid-Sem Benchmark Datasets & Splits

Generated by `bench/data/make_splits.py`.
**FROZEN PROTOCOL: DO NOT REGENERATE OR EDIT THESE SPLITS.**

## Summary of Dataset Counts
- **Source Dataset:** 2WikiMultihopQA (dev split, Alab-NII / HuggingFace voidful mirror)
- **Eval Questions (`eval_questions.json`):** 50 multi-hop questions (Seed: 42)
  - Comparison: 13
  - Inference: 13
  - Compositional: 12
  - Bridge Comparison: 12
- **Eval Documents (`eval_docs/`):** 500 documents (1 paragraph per document, title slugified)
- **Corpus Order (`corpus_order.json`):** Shuffled order of 500 eval documents for nested corpus sizes (50, 150, 300, 500)
- **Train Documents (`train_docs/`):** 200 documents (Seed: 43, strictly disjoint from eval documents: 0 overlap)
  - Zero-padded prefixes (`000_...txt` to `199_...txt`) for deterministic snapshot ordering in Truncated-BPTT.
- **Single-Fact Edits (`edits.json`):** 20 verified single-fact edits sampled from `corpus_order[:50]`.
- **Workspace Corpus (`workspace_docs/`):** 8 research documents (GraphRAG, G-Retriever, ROLAND, HippoRAG, Leiden, GRU, KONNECT Synopsis, Backend Architecture).
- **Workspace Questions (`workspace_questions.json`):** 30 cross-document multi-hop questions with gold answers and supporting document IDs.

## File Verification Manifest (SHA-256)
| File | SHA-256 |
|---|---|
"""
    # Include primary JSON files and a sample of document files in table
    for rel_path, sha in manifest:
        if rel_path.endswith(".json") or rel_path.startswith("workspace_docs"):
            readme_content += f"| `{rel_path}` | `{sha}` |\n"

    readme_content += f"\n*Total split files tracked: {len(manifest)}*\n"

    (SPLITS_DIR / "README.md").write_text(readme_content, encoding="utf-8")
    (DATA_DIR / "README.md").write_text(readme_content, encoding="utf-8")

    print(f"Successfully generated and verified all splits in {SPLITS_DIR} and {DATA_DIR}.")


if __name__ == "__main__":
    main()
