HTML_PAGE = """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>ExpData Patent Extractor</title>
  <style>
    :root { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
    body { margin: 0; background: #f5f7fb; color: #1f2937; }
    .wrap { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
    .card { background: #fff; border-radius: 12px; padding: 1rem 1.2rem; box-shadow: 0 2px 10px rgba(0,0,0,.08); margin-bottom: 1rem; }
    h1 { margin-top: 0; font-size: 1.4rem; }
    .muted { color: #6b7280; font-size: .95rem; }
    .row { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }
    input[type=file] { border: 1px solid #d1d5db; border-radius: 8px; padding: .4rem; background: #fff; }
    button { border: 0; border-radius: 8px; padding: .55rem .9rem; font-weight: 600; cursor: pointer; background: #2563eb; color: white; }
    button:disabled { opacity: .6; cursor: not-allowed; }
    .status { font-weight: 600; }
    pre { white-space: pre-wrap; word-break: break-word; background: #111827; color: #e5e7eb; padding: .75rem; border-radius: 8px; max-height: 280px; overflow: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .92rem; }
    th, td { border-bottom: 1px solid #e5e7eb; text-align: left; padding: .45rem; vertical-align: top; }
    th { background: #f9fafb; }
    .pill { display: inline-block; padding: .1rem .45rem; border-radius: 999px; font-size: .8rem; }
    .pill.ok { background: #dcfce7; color: #166534; }
    .pill.warn { background: #fee2e2; color: #991b1b; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>Patent PDF → SMILES + Experimental Data</h1>
      <p class=\"muted\">Upload a patent PDF to extract compounds, assay metrics, provenance, and review flags.</p>
      <div class=\"row\">
        <input id=\"fileInput\" type=\"file\" accept=\"application/pdf,.pdf\" />
        <button id=\"runBtn\">Run Extraction</button>
      </div>
      <p id=\"status\" class=\"status muted\">No job submitted yet.</p>
      <p id=\"jobId\" class=\"muted\"></p>
    </div>

    <div class=\"card\">
      <h2>Results</h2>
      <div id=\"resultsTableWrap\" class=\"muted\">No results yet.</div>
    </div>

    <div class=\"card\">
      <h2>Raw JSON</h2>
      <pre id=\"raw\">[]</pre>
    </div>
  </div>

  <script>
    const fileInput = document.getElementById('fileInput');
    const runBtn = document.getElementById('runBtn');
    const statusEl = document.getElementById('status');
    const jobIdEl = document.getElementById('jobId');
    const rawEl = document.getElementById('raw');
    const tableWrap = document.getElementById('resultsTableWrap');

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    async function parseApiResponse(res) {
      const text = await res.text();
      try {
        return { ok: res.ok, status: res.status, data: JSON.parse(text), raw: text };
      } catch {
        return { ok: res.ok, status: res.status, data: null, raw: text };
      }
    }

    function renderTable(records) {
      if (!records || !records.length) {
        tableWrap.innerHTML = 'No records returned.';
        return;
      }
      const rows = records.map(r => {
        const review = r.review?.requires_manual_review
          ? '<span class="pill warn">manual review</span>'
          : '<span class="pill ok">auto accepted</span>';
        return `\n<tr>\n<td>${r.compound_label ?? ''}</td>\n<td><code>${r.canonical_smiles ?? ''}</code></td>\n<td>${r.metric ?? ''} ${r.value ?? ''} ${r.unit ?? ''}</td>\n<td>${r.assay_type_normalized ?? ''}</td>\n<td>${r.source?.section_heading ?? ''} (p.${r.source?.page_number ?? ''})</td>\n<td>${review}</td>\n</tr>`;
      }).join('');

      tableWrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Compound</th>
              <th>SMILES</th>
              <th>Metric</th>
              <th>Assay (Normalized)</th>
              <th>Source</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    async function pollJob(jobId) {
      for (let i = 0; i < 20; i++) {
        const res = await fetch(`/jobs/${jobId}`);
        if (!res.ok) throw new Error('Failed to fetch job status');
        const data = await res.json();
        statusEl.textContent = `Job status: ${data.status}`;
        if (data.status === 'completed') return;
        await sleep(800);
      }
      throw new Error('Timed out waiting for completion');
    }

    runBtn.addEventListener('click', async () => {
      const file = fileInput.files?.[0];
      if (!file) {
        statusEl.textContent = 'Please choose a PDF first.';
        return;
      }

      runBtn.disabled = true;
      statusEl.textContent = 'Submitting job...';
      rawEl.textContent = '[]';
      tableWrap.innerHTML = 'Processing...';

      try {
        const fd = new FormData();
        fd.append('file', file, file.name);

        const submitRes = await fetch('/submit', { method: 'POST', body: fd });
        const submitParsed = await parseApiResponse(submitRes);
        if (!submitParsed.ok) {
          const msg = submitParsed.data?.detail || submitParsed.raw || 'Submit failed';
          throw new Error(msg);
        }

        const jobId = submitParsed.data?.job_id;
        if (!jobId) throw new Error('Submit succeeded but no job_id returned.');
        jobIdEl.textContent = `Job ID: ${jobId}`;
        await pollJob(jobId);

        statusEl.textContent = 'Fetching results...';
        const resultRes = await fetch(`/results/${jobId}`);
        const resultParsed = await parseApiResponse(resultRes);
        if (!resultParsed.ok) {
          const msg = resultParsed.data?.detail || resultParsed.raw || 'Result fetch failed';
          throw new Error(msg);
        }

        const records = Array.isArray(resultParsed.data) ? resultParsed.data : [];
        rawEl.textContent = JSON.stringify(records, null, 2);
        renderTable(records);
        statusEl.textContent = 'Done.';
      } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
        tableWrap.innerHTML = '<span style="color:#991b1b">Request failed.</span>';
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""
