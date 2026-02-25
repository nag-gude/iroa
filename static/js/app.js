/**
 * IROA Demo UI — Incident Response + Observability Agent
 * Handles analyze form, fetch to POST /analyze, and result rendering.
 */
(function() {
  'use strict';

  var base = window.location.origin;
  function el(id) { return document.getElementById(id); }
  var errEl = el('error');
  var loadEl = el('loading');
  var resultEl = el('result');

  function showError(msg) {
    errEl.textContent = msg;
    errEl.classList.add('visible');
    resultEl.classList.remove('visible');
  }

  function clearError() {
    errEl.textContent = '';
    errEl.classList.remove('visible');
  }

  function setLoading(on) {
    loadEl.classList.toggle('visible', on);
    el('submit').disabled = on;
  }

  function escapeHtml(s) {
    if (typeof s !== 'string') return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function renderResult(data) {
    el('out-summary').textContent = data.summary || '—';
    el('out-root_cause').textContent = data.root_cause || '—';
    var conf = (data.confidence || '').toLowerCase();
    var confEl = el('out-confidence');
    confEl.textContent = data.confidence ? 'Confidence: ' + data.confidence : '';
    confEl.className = 'confidence ' + (conf === 'high' ? 'high' : conf === 'medium' ? 'medium' : 'low');

    var sectionActions = el('section-actions');
    var actionsUl = el('out-actions');
    if (data.actions_taken && data.actions_taken.length > 0) {
      sectionActions.style.display = 'block';
      actionsUl.innerHTML = data.actions_taken.map(function(a) {
        return '<li><strong>' + escapeHtml(a.action) + '</strong> (' + escapeHtml(a.system || 'N/A') + '): ' +
          escapeHtml(a.identifier || 'N/A') + (a.link ? ' <a href="' + escapeHtml(a.link) + '" target="_blank" rel="noopener">Link</a>' : '') + '</li>';
      }).join('');
    } else {
      sectionActions.style.display = 'none';
    }

    var evidenceEl = el('out-evidence');
    if (data.evidence && data.evidence.length > 0) {
      var frag = document.createDocumentFragment();
      data.evidence.slice(0, 15).forEach(function(c) {
        var snip = c.snippet || (c.fields && JSON.stringify(c.fields)) || '—';
        var div = document.createElement('div');
        div.className = 'evidence-item';
        div.innerHTML = '<div class="type">' + escapeHtml(c.type + (c.index ? ' — ' + c.index : '')) + '</div><pre class="snippet">' + escapeHtml(snip) + '</pre>';
        frag.appendChild(div);
      });
      evidenceEl.innerHTML = '';
      evidenceEl.appendChild(frag);
    } else {
      evidenceEl.innerHTML = '<p class="empty-state">No evidence returned.</p>';
    }

    var auditUl = el('out-audit');
    auditUl.innerHTML = (data.audit_trail || []).map(function(s) { return '<li>' + escapeHtml(s) + '</li>'; }).join('');

    var sectionExpl = el('section-explanation');
    var explEl = el('out-explanation');
    if (data.explanation) {
      sectionExpl.style.display = 'block';
      explEl.textContent = data.explanation;
    } else {
      sectionExpl.style.display = 'none';
    }

    resultEl.classList.add('visible');
    requestAnimationFrame(function() {
      resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function runAnalyze() {
    var query = el('query').value.trim();
    if (!query) {
      showError('Enter a query.');
      return;
    }
    clearError();
    setLoading(true);
    resultEl.classList.remove('visible');

    var payload = {
      query: query,
      time_range_minutes: parseInt(el('time_range').value, 10) || 15,
      create_ticket: el('create_ticket').checked,
    };

    fetch(base + '/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function(res) {
        return res.json().then(function(data) { return { res: res, data: data }; }).catch(function() { return { res: res, data: {} }; });
      })
      .then(function(ref) {
        var res = ref.res;
        var data = ref.data;
        if (!res.ok) {
          showError(data.detail || res.statusText || 'Request failed');
          return;
        }
        renderResult(data);
      })
      .catch(function(e) {
        showError(e.message || 'Network or unexpected error');
      })
      .finally(function() {
        setLoading(false);
      });
  }

  el('submit').addEventListener('click', runAnalyze);
})();
