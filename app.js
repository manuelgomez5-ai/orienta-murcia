(() => {
  'use strict';

  const DATA_KEYS = ['status', 'ranking', 'vacancies', 'adjudications', 'exclusions', 'annulled', 'documents'];
  let data = {};
  let vacancies = { rows: [] };
  let adjudications = [];
  let exclusions = [];
  let annulled = [];
  let documents = [];
  let ranking = { rows: [] };
  let status = {};

  function applyData(nextData) {
    data = nextData || {};
    const rowsOf = (key) => data[key]?.rows || [];
    vacancies = data.vacancies || { rows: [] };
    adjudications = rowsOf('adjudications');
    exclusions = rowsOf('exclusions');
    annulled = rowsOf('annulled');
    documents = rowsOf('documents');
    ranking = data.ranking || { rows: [] };
    status = data.status || {};
  }

  applyData(window.ORIENTA_DATA || {});

  const $ = (id) => document.getElementById(id);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const esc = (value) => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
  const fold = (value) => String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/\s+/g, ' ')
    .trim();
  const fmtNumber = (value, digits = 0) => new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value || 0));
  const fmtDate = (value, includeTime = false) => {
    if (!value) return '—';
    const date = new Date(value.length === 10 ? `${value}T12:00:00+02:00` : value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('es-ES', {
      day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Madrid',
      ...(includeTime ? { hour: '2-digit', minute: '2-digit' } : {}),
    }).format(date);
  };
  const journeyLabel = (row) => row.jornada === 'Parcial' && row.hours
    ? `Parcial · ${row.hours} h`
    : (row.jornada || '—');
  const emptyRow = (cols, message) => `<tr><td colspan="${cols}" class="empty">${esc(message)}</td></tr>`;

  function showView(name) {
    $$('.view').forEach((el) => el.classList.toggle('active', el.id === `view-${name}`));
    $$('.nav-btn').forEach((el) => el.classList.toggle('active', el.dataset.view === name));
    window.scrollTo({ top: 0, behavior: 'smooth' });
    history.replaceState(null, '', `#${name}`);
  }

  function setupNavigation() {
    $$('.nav-btn').forEach((btn) => btn.addEventListener('click', () => showView(btn.dataset.view)));
    $$('[data-go]').forEach((btn) => btn.addEventListener('click', () => showView(btn.dataset.go)));
    const requested = location.hash.replace('#', '');
    if (requested && $(`view-${requested}`)) showView(requested);
  }

  function newestDocument() {
    return [...documents].sort((a, b) => String(b.date).localeCompare(String(a.date)))[0];
  }

  function renderSummary() {
    const vacRows = vacancies.rows || [];
    const total = vacRows.reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    const complete = vacRows.filter((row) => row.jornada === 'Completa')
      .reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    const partial = vacRows.filter((row) => row.jornada === 'Parcial')
      .reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    const partialHours = [...new Set(vacRows.filter((row) => row.jornada === 'Parcial' && row.hours).map((row) => row.hours))]
      .sort((a, b) => a - b);
    const latest = newestDocument();

    $('vacancyTotal').textContent = fmtNumber(total);
    $('completeTotal').textContent = fmtNumber(complete);
    $('partialTotal').textContent = fmtNumber(partial);
    $('movementTotal').textContent = fmtNumber(adjudications.length + exclusions.length + annulled.length);
    $('vacancyDate').textContent = vacancies.document_date ? `Documento de ${fmtDate(vacancies.document_date)}` : 'Sin documento';
    $('partialHours').textContent = partialHours.length ? `${partialHours.join(', ')} horas semanales` : 'Por horas';
    $('lastCheck').textContent = fmtDate(status.last_check, true);
    $('lastDocument').textContent = latest ? `${latest.type} · ${fmtDate(latest.date)}` : '—';
    $('syncMode').textContent = status.mode === 'automatic' ? 'Sincronización automática activa' : 'Automatización preparada';

    const errorBox = $('errorBox');
    if ((status.errors || []).length) {
      errorBox.classList.remove('hidden');
      errorBox.innerHTML = `<strong>La última revisión terminó con avisos:</strong><br>${status.errors.map(esc).join('<br>')}`;
    }

    renderDocuments('latestDocs', documents.slice(0, 3));
  }

  function renderDocuments(targetId, docs) {
    const target = $(targetId);
    if (!docs.length) {
      target.innerHTML = '<div class="empty">Todavía no hay documentos procesados.</div>';
      return;
    }
    target.innerHTML = docs.map((doc) => `
      <a class="doc-item" href="${esc(doc.url)}" target="_blank" rel="noopener">
        <span class="doc-type">${esc(doc.type || 'Documento')}</span>
        <span><strong>${esc(doc.title || 'Documento oficial')}</strong><small>${fmtDate(doc.date)} · ${Number(doc.orientation_rows || 0) > 0 ? `${fmtNumber(doc.orientation_rows)} registros/plazas detectados` : 'enlace oficial'}</small></span>
        <em>↗</em>
      </a>`).join('');
  }

  function renderVacancies() {
    const query = fold($('vacSearch').value);
    const journey = $('vacJourney').value;
    const profile = $('vacProfile').value;
    const allRows = vacancies.rows || [];
    const filtered = allRows.filter((row) => {
      const haystack = fold([row.centre_code, row.centre, row.locality, row.profile, row.observations].join(' '));
      const journeyOk = journey === 'all' || row.jornada === journey;
      const normalizedProfile = fold(row.profile || 'SIN PERFIL');
      const profileOk = profile === 'all' || normalizedProfile.includes(fold(profile));
      return (!query || haystack.includes(query)) && journeyOk && profileOk;
    });

    $('vacancyBody').innerHTML = filtered.length ? filtered.map((row) => `
      <tr>
        <td><strong>${esc(row.centre || '—')}</strong><br><small>${esc(row.centre_code || '')}</small></td>
        <td>${esc(row.locality || '—')}</td>
        <td><span class="tag ${row.jornada === 'Completa' ? 'complete' : 'partial'}">${esc(journeyLabel(row))}</span></td>
        <td>${fmtNumber(row.quantity || 1)}</td>
        <td>${esc(row.profile || 'Sin perfil')}</td>
        <td>${esc(row.observations || row.section || '—')}</td>
      </tr>`).join('') : emptyRow(6, 'No hay vacantes que coincidan con los filtros.');

    const filteredPlaces = filtered.reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    $('vacancyCount').textContent = `${fmtNumber(filtered.length)} filas · ${fmtNumber(filteredPlaces)} plazas mostradas.`;
  }

  function setupVacancyStats() {
    const allRows = vacancies.rows || [];
    const total = allRows.reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    const complete = allRows.filter((row) => row.jornada === 'Completa').reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    const partial = allRows.filter((row) => row.jornada === 'Parcial').reduce((sum, row) => sum + Number(row.quantity || 1), 0);
    $('vacTotal2').textContent = fmtNumber(total);
    $('vacComplete2').textContent = fmtNumber(complete);
    $('vacPartial2').textContent = fmtNumber(partial);
    $('vacRows2').textContent = fmtNumber(allRows.length);
    $('vacancySubtitle').textContent = vacancies.document_date
      ? `Último documento procesado: ${fmtDate(vacancies.document_date)}. La cifra suma plazas, no solo filas.`
      : 'No se ha procesado todavía un documento de vacantes.';
    if (vacancies.source_url) {
      $('vacancySource').href = vacancies.source_url;
      $('vacancySource').classList.remove('hidden');
    } else {
      $('vacancySource').classList.add('hidden');
    }
  }

  function setupVacancies() {
    setupVacancyStats();
    ['vacSearch', 'vacJourney', 'vacProfile'].forEach((id) => $(id).addEventListener('input', renderVacancies));
    renderVacancies();
  }

  function renderAdjudications() {
    const query = fold($('adjSearch').value);
    const state = $('adjStatus').value;
    const filtered = adjudications
      .filter((row) => {
        const haystack = fold([row.list_number, row.name, row.centre, row.municipality].join(' '));
        return (!query || haystack.includes(query)) && (state === 'all' || row.status === state);
      })
      .sort((a, b) => String(b.document_date).localeCompare(String(a.document_date)));
    $('adjBody').innerHTML = filtered.length ? filtered.map((row) => `
      <tr>
        <td>${fmtDate(row.document_date)}</td>
        <td>${esc(row.list_number || '—')}</td>
        <td><strong>${esc(row.name || '—')}</strong><br><small>${esc(row.masked_id || '')}</small></td>
        <td>${esc(row.centre || '—')}</td>
        <td>${esc(journeyLabel(row))}</td>
        <td><span class="tag ${row.status === 'Definitiva' ? 'final' : 'provisional'}">${esc(row.status || '—')}</span></td>
        <td>${esc(row.scope || '—')}</td>
      </tr>`).join('') : emptyRow(7, 'No hay adjudicaciones que coincidan.');
  }

  function renderExclusions() {
    const query = fold($('excSearch').value);
    const filtered = exclusions
      .filter((row) => !query || fold([row.list_number, row.name, row.reason].join(' ')).includes(query))
      .sort((a, b) => String(b.document_date).localeCompare(String(a.document_date)));
    $('excBody').innerHTML = filtered.length ? filtered.map((row) => `
      <tr>
        <td>${fmtDate(row.document_date)}</td>
        <td>${esc(row.list_number || '—')}</td>
        <td><strong>${esc(row.name || '—')}</strong><br><small>${esc(row.masked_id || '')}</small></td>
        <td>${esc(row.reason || '—')}</td>
        <td><span class="tag ${row.status === 'Definitiva' ? 'final' : 'provisional'}">${esc(row.status || '—')}</span></td>
        <td>${esc(row.course || '—')}</td>
      </tr>`).join('') : emptyRow(6, 'No hay exclusiones que coincidan.');
  }

  function renderAnnulled() {
    const sorted = [...annulled].sort((a, b) => String(b.document_date).localeCompare(String(a.document_date)));
    $('annBody').innerHTML = sorted.length ? sorted.map((row) => `
      <tr>
        <td>${fmtDate(row.document_date)}</td>
        <td>${esc(row.centre || '—')}</td>
        <td>${esc(row.locality || '—')}</td>
        <td>${esc(journeyLabel(row))}</td>
        <td>${fmtNumber(row.quantity || 1)}</td>
      </tr>`).join('') : emptyRow(5, 'Todavía no se han detectado vacantes anuladas de Orientación Educativa.');
  }

  function updateMovementBadges() {
    $('adjBadge').textContent = adjudications.length;
    $('excBadge').textContent = exclusions.length;
    $('annBadge').textContent = annulled.length;
  }

  function setupMovements() {
    updateMovementBadges();
    $$('.tab').forEach((tab) => tab.addEventListener('click', () => {
      $$('.tab').forEach((button) => button.classList.toggle('active', button === tab));
      $$('.movement-panel').forEach((panel) => panel.classList.toggle('active', panel.id === `tab-${tab.dataset.tab}`));
    }));
    $('adjSearch').addEventListener('input', renderAdjudications);
    $('adjStatus').addEventListener('input', renderAdjudications);
    $('excSearch').addEventListener('input', renderExclusions);
    renderAdjudications();
    renderExclusions();
    renderAnnulled();
  }

  function activePosition(row) {
    const rankingRows = ranking.rows || [];
    const priorListNumbers = new Set(rankingRows.filter((person) => Number(person.global) < Number(row.global)).map((person) => String(person.list_number)));
    const relevantAwards = adjudications.filter((award) => award.status === 'Definitiva' && award.affects_interim_ranking !== false && priorListNumbers.has(String(award.list_number)));
    const relevantExclusions = exclusions.filter((item) => item.status === 'Definitiva' && item.affects_interim_ranking !== false && priorListNumbers.has(String(item.list_number)));
    const awardNumbers = new Set(relevantAwards.map((award) => String(award.list_number)));
    const exclusionNumbers = new Set(relevantExclusions.map((item) => String(item.list_number)));
    const discountedNumbers = new Set([...awardNumbers, ...exclusionNumbers]);
    return {
      position: Math.max(1, Number(row.global) - discountedNumbers.size),
      discounted: discountedNumbers.size,
      awards: awardNumbers.size,
      exclusions: exclusionNumbers.size,
    };
  }

  function renderPersonResults() {
    const query = fold($('personSearch').value);
    const target = $('personResults');
    if (!query) {
      target.innerHTML = '<div class="empty">Escribe un nombre, número de lista, DNI enmascarado o puesto.</div>';
      return;
    }
    const matches = (ranking.rows || []).filter((row) => {
      const exactNumber = String(row.global) === query || String(row.block_rank) === query || String(row.list_number) === query;
      const haystack = fold([row.name, row.masked_id, row.list_number, row.global, row.block_rank].join(' '));
      const tokens = query.split(' ').filter(Boolean);
      return exactNumber || haystack.includes(query) || tokens.every((token) => haystack.includes(token));
    }).slice(0, 20);
    if (!matches.length) {
      target.innerHTML = '<div class="empty">No se encontró esa persona en los datos cargados. El prototipo solo incluye un extracto hasta que se importe la lista definitiva completa.</div>';
      return;
    }
    target.innerHTML = matches.map((row) => {
      const active = activePosition(row);
      return `
        <article class="person-card">
          <div class="person-top">
            <div><strong>${esc(row.name)}</strong><small>Nº lista ${esc(row.list_number)} · DNI ${esc(row.masked_id)}</small></div>
            <span class="status ${active.discounted ? 'good' : 'warn'}">${active.discounted ? 'Actualizada' : 'Sin descuentos confirmados'}</span>
          </div>
          <div class="person-metrics">
            <div><span>Puesto oficial</span><b>${fmtNumber(row.global)}</b></div>
            <div><span>Bloque</span><b>${fmtNumber(row.block)}</b></div>
            <div><span>Puesto en bloque</span><b>${fmtNumber(row.block_rank)}</b></div>
            <div><span>Posición activa</span><b>≈ ${fmtNumber(active.position)}</b></div>
          </div>
          <p class="explanation">Puntuación: <strong>${fmtNumber(row.points, 4)}</strong>. Se han descontado ${fmtNumber(active.discounted)} movimientos definitivos anteriores (${fmtNumber(active.awards)} adjudicaciones y ${fmtNumber(active.exclusions)} exclusiones) que el sistema considera relevantes para la lista actual.</p>
        </article>`;
    }).join('');
  }

  function setupRanking() {
    $('rankingNotice').innerHTML = `<strong>Estado del buscador:</strong> ${esc(ranking.notice || 'Sin información sobre la lista cargada.')}`;
    $('personButton').addEventListener('click', renderPersonResults);
    $('personSearch').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') renderPersonResults();
    });
    $('personResults').innerHTML = '<div class="empty">Prueba con “Manuel Gómez”, “25002960” o “282”.</div>';
  }

  function renderSources() {
    $('sourceLastCheck').textContent = fmtDate(status.last_check, true);
    $('sourceLastSuccess').textContent = fmtDate(status.last_success, true);
    const pill = $('syncStatusPill');
    pill.textContent = status.mode === 'automatic' ? 'Activa' : 'Preparada';
    pill.className = `status ${status.errors?.length ? 'warn' : 'good'}`;
    renderDocuments('allDocs', documents);
  }

  let toastTimer;

  function showToast(message, tone = '') {
    const toast = $('updateToast');
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.className = `update-toast show ${tone}`.trim();
    toastTimer = setTimeout(() => { toast.className = 'update-toast'; }, 4800);
  }

  function renderRefreshedData() {
    renderSummary();
    setupVacancyStats();
    renderVacancies();
    updateMovementBadges();
    renderAdjudications();
    renderExclusions();
    renderAnnulled();
    $('rankingNotice').innerHTML = `<strong>Estado del buscador:</strong> ${esc(ranking.notice || 'Sin información sobre la lista cargada.')}`;
    if ($('personSearch').value.trim()) renderPersonResults();
    renderSources();
  }

  async function refreshNow() {
    const button = $('refreshButton');
    const label = button.querySelector('.refresh-label');
    const previousSuccess = status.last_success || '';
    const previousDocument = newestDocument()?.url || '';
    button.disabled = true;
    button.className = 'refresh-button loading';
    label.textContent = 'Comprobando…';

    try {
      if (window.ORIENTA_STANDALONE || location.protocol === 'file:') {
        await new Promise((resolve) => setTimeout(resolve, 650));
        $('lastCheck').textContent = new Intl.DateTimeFormat('es-ES', {
          day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Madrid'
        }).format(new Date());
        button.className = 'refresh-button success';
        label.textContent = 'Comprobado';
        showToast('Demostración actualizada. La consulta real de nuevos PDF se activa al publicar la web.', 'warn');
        return;
      }

      const stamp = Date.now();
      const entries = await Promise.all(DATA_KEYS.map(async (key) => {
        const response = await fetch(`data/${key}.json?v=${stamp}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`No se pudo cargar ${key}.json`);
        return [key, await response.json()];
      }));
      applyData(Object.fromEntries(entries));
      renderRefreshedData();

      const newSuccess = status.last_success || '';
      const newDocument = newestDocument()?.url || '';
      const changed = newSuccess !== previousSuccess || newDocument !== previousDocument;
      button.className = 'refresh-button success';
      label.textContent = changed ? 'Actualizado' : 'Al día';
      showToast(changed ? 'Se han cargado nuevos datos publicados.' : 'Todo está al día. No hay cambios publicados.', 'good');
    } catch (error) {
      console.error(error);
      button.className = 'refresh-button error';
      label.textContent = 'Reintentar';
      showToast('No se pudo comprobar la actualización. Revisa la conexión e inténtalo de nuevo.', 'bad');
    } finally {
      setTimeout(() => {
        button.disabled = false;
        if (!button.classList.contains('error')) button.className = 'refresh-button';
        label.textContent = 'Comprobar actualización';
      }, 1800);
    }
  }

  function setupRefresh() {
    $('refreshButton').addEventListener('click', refreshNow);
  }

  function init() {
    setupNavigation();
    renderSummary();
    setupVacancies();
    setupMovements();
    setupRanking();
    renderSources();
    setupRefresh();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
