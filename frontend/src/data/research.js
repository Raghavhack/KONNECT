export const researchCards = [
  {
    tag: "GraphRAG",
    source: "Edge et al., Microsoft Research, 2024",
    problem:
      "Query-focused summarisation over an entire corpus: chunk → LLM entity/relationship extraction → Leiden community detection → community summaries.",
    reused: "Representing the corpus as a weighted entity-relationship graph rather than a flat chunk index.",
    adapted: "Community detection is restricted to the local neighbourhood of the changed document's entities instead of the whole corpus.",
    notReused: "GraphRAG has no update rule at all — it assumes a static corpus. That missing rule is exactly what ROLAND supplies.",
  },
  {
    tag: "G-Retriever",
    source: "He et al., 2024",
    problem:
      "Answering questions over a large textual graph by retrieving one connected, relevant subgraph via a Prize Collecting Steiner Tree formulation, instead of independent nodes by vector similarity.",
    reused: "The PCST retrieval objective (prize assignment + connected-subgraph optimisation) is used directly.",
    adapted: "Prize assignment is computed against KONNECT's incrementally maintained embeddings rather than embeddings frozen at indexing time.",
    notReused: "End-to-end fine-tuning of the LLM with a trainable graph encoder — KONNECT uses a frozen embedding model and frozen LLM.",
  },
  {
    tag: "ROLAND",
    source: "You, Du & Leskovec, KDD 2022",
    problem:
      "Standard GNNs recompute embeddings from scratch whenever a graph changes. ROLAND reframes layer-wise embeddings as a hierarchical state that updates via a GRU cell instead.",
    reused: "The GRU-based hierarchical state update rule, and truncated, memory-bounded incremental training.",
    adapted: "A 'time step' is redefined from a calendar interval to a single webhook document-edit event, bounded to a k-hop neighbourhood.",
    notReused: "ROLAND's offline meta-learning evaluation protocol across labelled future links — left as a future extension.",
  },
];
