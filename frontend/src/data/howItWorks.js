// Content as data — the /how-it-works walkthrough steps, shared by
// Home's teaser ScrollSpySection and the full /how-it-works page.
export const howItWorksSteps = [
  {
    id: "webhook",
    title: "Webhook fires on edit",
    description:
      "A Google Drive or Notion push notification hits the Express backend the moment a document changes.",
  },
  {
    id: "debounce",
    title: "Debounce & queue",
    description:
      "Rapid successive edits collapse into one job; idempotency keys stop retried deliveries from double-processing.",
  },
  {
    id: "reparse",
    title: "Reparse only the changed doc",
    description:
      "FastAPI extracts entities/relationships from the edited document alone — not the whole corpus.",
  },
  {
    id: "neo4j",
    title: "Partial graph invalidation",
    description:
      "Only the nodes and edges attributed to that document are patched in Neo4j; everything else is untouched.",
  },
  {
    id: "roland",
    title: "Incremental GRU re-embedding",
    description:
      "ROLAND's GRU update rule recomputes embeddings for nodes within k hops of the change — a bounded neighbourhood, not the full graph.",
  },
  {
    id: "pcst",
    title: "PCST-grounded retrieval",
    description:
      "At query time, node/edge prizes are scored by cosine similarity and the Prize Collecting Steiner Tree objective retrieves one connected, explainable subgraph.",
  },
  {
    id: "cited-answer",
    title: "Cited chat answer",
    description:
      "The retrieved subgraph is serialised into a prompt; the LLM grounds every claim in a node, so citations trace back to the source document.",
  },
];
