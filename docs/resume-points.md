# Resume and interview notes

## Resume bullets

- Built DocuMind AI, a local document question-answering application using React, TypeScript, FastAPI, SQLite, and Python, with PDF upload, semantic search, cited answers, and persistent chat history.
- Implemented a CPU-based RAG pipeline with PyMuPDF page-aware chunking, MiniLM embeddings, FAISS similarity search, and FLAN-T5 generation. Validated citations against retrieved PDF chunks and handled insufficient evidence.
- Added automated coverage for ingestion, retrieval, conversation persistence, and deletion. Evaluated local inference on three sample PDFs and five questions, measuring Recall@2, answer and citation correctness, abstention, and request latency.

## 30-second explanation

DocuMind AI helps a user ask questions about PDFs without sending their documents to a hosted AI service. The app extracts text by page, uses MiniLM and FAISS to find relevant passages, and runs FLAN-T5 on the local CPU. The backend checks the answer against the excerpts and returns the original page references. The React app provides a document library, a search view, and persistent chat history.

## Two-minute technical explanation

The React frontend calls a FastAPI service over loopback. On upload, the backend checks the PDF signature, file limit, and content hash. PyMuPDF extracts text page by page. The chunker preserves the original text for citations and normalizes whitespace for MiniLM. The encoder produces normalized 384-dimensional vectors and FAISS uses inner product to rank them. SQLite holds document and chunk metadata, vectors, and the serialized FAISS index. Keeping these in one transaction makes upload and deletion consistent across restarts.

When a user asks a question, the backend validates the selected PDFs and retrieves within their scope. A similarity threshold and token budget limit the excerpts. A single CPU worker loads the cached FLAN-T5 checkpoint on demand and reuses it. The backend accepts answers supported by the prompt excerpts, with narrow normalization for date formats, and gets citation IDs from stored chunks. SQLite saves the two chat messages together. Chrome and automated tests covered the full path from upload to reopening a cited answer. I evaluated retrieval and answer quality on a small fixture and report its sample size alongside the results.

## Five interview questions

1. **Why combine SQLite and FAISS?** FAISS ranks vectors efficiently. SQLite stores source metadata, persists the vector rows, and commits the serialized index with changes to the library. The index can be rebuilt from SQLite if its snapshot is unreadable.
2. **How do you prevent fabricated citations?** The model only produces answer text. The backend checks that text against excerpts included in the prompt and constructs references from the corresponding retrieved IDs and page numbers.
3. **How do you handle a query that has no answer?** Low-similarity retrieval can skip generation entirely. If the generated answer cannot be matched to the prompt evidence, the app returns insufficient evidence without a citation.
4. **How does the app run offline on a laptop?** The public model weights and tokenizers are cached during setup. Inference runs on the CPU. The app reuses the models, bounds the prompt and output lengths, and limits generation to one worker.
5. **What did the evaluation measure?** On three synthetic PDFs, four factual questions measured retrieval Recall@2 and answer accuracy. Emitted citations were checked against expected pages and retrieved chunk IDs. A fifth question measured abstention, and request timing included the first model load.

## Engineering challenges

| Challenge | Implemented approach |
| --- | --- |
| Keeping source references through extraction and retrieval | Preserve page and chunk IDs through ingestion, indexing, and citation assembly. |
| Recovering from interrupted writes | Commit SQLite metadata, vectors, and index state together. Clean up orphaned app-owned PDF files on startup. |
| Limiting hallucinated source references | Assemble citations in the backend from the retrieved metadata and abstain when the answer check fails. |
| CPU-only latency and memory use | Cache and lazily load models, limit generation concurrency, and bound prompts, outputs, and inference time. |
| Demonstrating reliability | Use deterministic tests alongside separate offline tests with the real models and a labeled fixture. |
