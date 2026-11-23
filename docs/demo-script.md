# Interview demo

**Target time** · 4 minutes

## Before the interview

Use the [Windows setup and startup commands](../README.md#windows-setup). Cache both models and start the backend in offline mode. Open the app on port 5173. Use a fresh local demo library or confirm that the names and conversation titles visible on screen are safe to share.

Prepare a two-page text PDF named `Scholarship Guide.pdf`. Put an unrelated paragraph on page 1. Put “The deadline for scholarship applications is September 30.” and “Scholarship recipients receive an award of 750 dollars.” on page 2. Export with selectable text. An image-only scan requires OCR before upload.

## 0:00–0:40 · Introduce the problem

Open the landing page and select **Get started**.

> “Searching a long PDF can be slow when the heading uses different words from the question. DocuMind AI retrieves passages by meaning and returns their page references. Extraction, search, and generation run in Python on the local CPU.”

Point out the live document and chunk counts and the two model cache indicators on the dashboard.

## 0:40–1:35 · Ingest and search

Go to **Documents** and upload the sample PDF. Show upload progress, then point out the indexed page count, file size, and date. Enter “When is the scholarship application deadline?” under **Semantic search**.

> “PyMuPDF extracts text by page and the chunker keeps the page number with every span. MiniLM maps each span and the question into normalized vectors. FAISS ranks those vectors by similarity, and SQLite maps each result to its document and page.”

## 1:35–2:50 · Ask a cited question

Open **Chat** and select the guide. Ask “What is the deadline for scholarship applications?” Expand the source card and point out page 2. Use **Copy answer** if time permits. The first answer may take longer while the model loads.

> “Chat scopes retrieval to the selected PDFs. FLAN-T5 receives a token-bounded set of excerpts and proposes a short answer. The backend checks the answer against those excerpts and creates the citation from saved metadata. I can open the cited passage to check the answer in context.”

Ask “What is the director's home address?” Show the insufficient-evidence response if it appears. Response behavior can vary with the PDF content. The checked-in evaluation fixture provides a repeatable abstention example.

## 2:50–4:00 · Show persistence and verification

Reload the page and reopen the conversation from **History**. Return to the dashboard and point out the latest conversation and PDF activity. Open the README evaluation section or fall back to its screenshots if the live browser is unavailable.

> “SQLite persists the messages and citations. It also commits document vectors and the serialized FAISS index together. I tested deletion and conversation persistence after a restart, and measured recall, answer correctness, citation accuracy, and latency on a small synthetic fixture.”

Close by explaining the main limit. The source check verifies a matching excerpt, while broader factual interpretation still requires reviewing the PDF. The app is designed for one local user.
