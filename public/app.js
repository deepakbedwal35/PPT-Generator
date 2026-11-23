const byId = id => document.getElementById(id);
const latex = byId('latex');
const generate = byId('generate');
const compile = byId('compile');
const openOverleaf = byId('open-overleaf');
const download = byId('download');
const pdfInput = byId('pdf');
const slide = byId('slide');
const status = byId('status');
const pptxType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
let config = { generate: false, compile: false };
let busy = false;
let slides = [];
let page = 0;
let deckUrl;
let pdfUrl;

function setStatus(message, isError = false) {
  status.textContent = message;
  status.dataset.error = isError;
}

function refreshControls() {
  const hasSource = Boolean(latex.value.trim());
  generate.disabled = busy || !config.generate;
  compile.disabled = busy || !config.compile || !hasSource;
  openOverleaf.disabled = busy || !hasSource;
  byId('save-source').disabled = busy || !hasSource;
  latex.readOnly = busy;
  byId('sample').disabled = busy;
  byId('choose-pdf').disabled = busy;
}

function showPage() {
  byId('empty-preview').hidden = slides.length > 0;
  slide.hidden = slides.length === 0;
  byId('navigation').hidden = slides.length === 0;
  if (!slides.length) {
    slide.removeAttribute('src');
    slide.alt = '';
    return;
  }
  slide.src = slides[page];
  slide.alt = `Rendered slide ${page + 1} of ${slides.length}`;
  byId('page-number').textContent = `${page + 1} / ${slides.length}`;
  byId('previous').disabled = page === 0;
  byId('next').disabled = page === slides.length - 1;
}

function setDeck(nextSlides, nextDeckUrl, nextPdfUrl) {
  if (deckUrl) URL.revokeObjectURL(deckUrl);
  if (pdfUrl) URL.revokeObjectURL(pdfUrl);
  deckUrl = nextDeckUrl;
  pdfUrl = nextPdfUrl;
  slides = nextSlides;
  page = 0;
  if (deckUrl) download.href = deckUrl;
  else download.removeAttribute('href');
  download.setAttribute('aria-disabled', String(!deckUrl));
  const pdfDownload = byId('download-pdf');
  if (pdfUrl) pdfDownload.href = pdfUrl;
  else pdfDownload.removeAttribute('href');
  pdfDownload.setAttribute('aria-disabled', String(!pdfUrl));
  showPage();
}

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(problem.error || `Request failed (${response.status}).`);
  }
  return response;
}

function postJson(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function work(message, action) {
  if (busy) return;
  busy = true;
  setDeck([]);
  refreshControls();
  setStatus(message);
  try {
    await action();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    busy = false;
    refreshControls();
  }
}

async function buildPowerPoint(pdf) {
  if (pdf.size > 15 * 1024 * 1024) throw new Error('PDF files must be 15 MB or smaller.');
  setStatus('Rendering slides and building PowerPoint…');
  const response = await request('/api/pptx', {
    method: 'POST',
    headers: { 'Content-Type': 'application/pdf', Accept: 'application/json' },
    body: pdf,
  });
  const result = await response.json();
  const bytes = atob(result.pptx);
  const binary = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) binary[i] = bytes.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([binary], { type: pptxType }));
  setDeck(result.slides, url, URL.createObjectURL(pdf));
  setStatus(`${slides.length} ${slides.length === 1 ? 'slide' : 'slides'} ready to download.`);
}

async function compileSource() {
  setStatus('Compiling Beamer…');
  const response = await postJson('/api/compile', { latex: latex.value });
  await buildPowerPoint(await response.blob());
}

function updateSource(source) {
  latex.value = source;
  setDeck([]);
  refreshControls();
}

byId('generate-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!config.generate) return;
  work('Generating Beamer source…', async () => {
    const response = await postJson('/api/latex', {
      brief: byId('brief').value,
      slideCount: byId('slide-count').valueAsNumber,
    });
    updateSource((await response.json()).latex);
    if (config.compile) await compileSource();
    else setStatus('Source is ready. Configure a local TeX compiler or open it in Overleaf.');
  });
});

byId('sample').addEventListener('click', () => work('Loading example…', async () => {
  const response = await request('/sample.tex');
  updateSource(await response.text());
  setStatus('Example loaded. Compile it or open it in Overleaf.');
}));

latex.addEventListener('input', () => {
  if (slides.length) setDeck([]);
  setStatus('');
  refreshControls();
});

byId('save-source').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([latex.value], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'main.tex';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

byId('overleaf-form').addEventListener('submit', event => {
  if (!latex.value.trim() || busy) {
    event.preventDefault();
    return;
  }
  const source = latex.value.trim().replace(/^```(?:latex|tex)?\s*\n([\s\S]*?)\n```$/i, '$1');
  byId('overleaf-source').value = encodeURIComponent(source);
  setStatus('Compile the project in Overleaf, download its PDF, and import it here.');
});

compile.addEventListener('click', () => work('Preparing source…', compileSource));
byId('choose-pdf').addEventListener('click', () => pdfInput.click());
pdfInput.addEventListener('change', () => {
  const file = pdfInput.files[0];
  pdfInput.value = '';
  if (file) work('Importing PDF…', () => buildPowerPoint(file));
});
byId('previous').addEventListener('click', () => { page -= 1; showPage(); });
byId('next').addEventListener('click', () => { page += 1; showPage(); });

request('/api/config').then(response => response.json()).then(data => {
  config = data;
  compile.hidden = !config.compile;
  generate.textContent = config.compile ? 'Generate & build' : 'Generate LaTeX';
  byId('generation-note').textContent = config.generate
    ? `Gemini: ${config.model}. You can also paste Beamer source below.`
    : 'Set a Gemini API key and model in .env, or paste Beamer source below.';
  const isMac = navigator.platform.includes('Mac') || navigator.userAgent.includes('Mac');
  const compilerText = config.compile
    ? 'Compiler ready.'
    : isMac
      ? 'Compiler missing: brew install basictex (or use "Open in Overleaf").'
      : 'Compiler missing: install TeX Live/MiKTeX or configure LATEX_COMMAND.';
  const rendererText = config.render
    ? 'PDF renderer ready.'
    : isMac
      ? 'Renderer missing: brew install poppler.'
      : 'Renderer missing: install Poppler and configure PDFTOPPM_PATH.';
  byId('setup-status').textContent = `${compilerText} ${rendererText}`;
  refreshControls();
}).catch(error => {
  byId('generation-note').textContent = 'LLM configuration could not be loaded.';
  setStatus(error.message, true);
});
