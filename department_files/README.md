# Department Files

The sample department documents are not included in this repository because some of them contain personal information.

Place your own policy documents here, one folder per department. The folder name decides which department a document is imported into (case-insensitive keyword match, see `backend/scripts/ingest_department_files.py`):

| Folder name contains | Department |
|---|---|
| `academic affairs` | `dept_jwc` |
| `student affairs` | `dept_xsc` |
| `finance` | `dept_cwc` |
| `human resources` | `dept_rsc` |
| `graduate school` | `dept_yjsy` |
| `sino-french` | `dept_zfxy` |
| `logistics` / `security` | `dept_hqaq` |

Supported formats: PDF, DOCX, Markdown, TXT, HTML. Then run:

```bash
docker compose exec backend python -m scripts.ingest_department_files --base /app/department_files
```

Note: `backend/evaluation/real_document_qa.json` refers to the original sample files, so `scripts.evaluate_rag` needs equivalent documents to reproduce its results.
