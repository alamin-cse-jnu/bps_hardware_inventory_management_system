/**
 * OfficeBrowser — self-contained macOS Finder-style column browser.
 * Usage: OfficeBrowser.init(containerId, data, options)
 *   data:    [{id, parentId, nameEn, nameBn, isAbstractOffice}, ...]
 *   options: { initialValue (office id), onSelect (callback) }
 */
(function () {
  'use strict';

  // ── DOM helper ─────────────────────────────────────────────────────────────
  function el(tag, attrs) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.entries(attrs).forEach(([k, v]) => {
        if (k === 'style') node.style.cssText = v;
        else if (k === 'class') node.className = v;
        else node.setAttribute(k, v);
      });
    }
    return node;
  }

  // ── Data utilities ─────────────────────────────────────────────────────────
  function buildTree(data) {
    const byId = new Map();
    const byParent = new Map();
    data.forEach(node => {
      byId.set(node.id, node);
      const pid = node.parentId || 0;
      if (!byParent.has(pid)) byParent.set(pid, []);
      byParent.get(pid).push(node);
    });
    byParent.forEach(children =>
      children.sort((a, b) => a.nameEn.localeCompare(b.nameEn))
    );
    return { byId, byParent };
  }

  // Returns [root_child, ..., direct_parent] (nearest-to-root first).
  function getAncestors(id, byId) {
    const ancestors = [];
    let node = byId.get(id);
    while (node && node.parentId) {
      const parent = byId.get(node.parentId);
      if (!parent) break;
      ancestors.unshift(parent);
      node = parent;
    }
    return ancestors;
  }

  // ── Main ───────────────────────────────────────────────────────────────────
  window.OfficeBrowser = {
    init(containerId, data, opts = {}) {
      const container = document.getElementById(containerId);
      if (!container) return;

      const { byId, byParent } = buildTree(data);
      let selectedId = null;
      let columnTrail = [0]; // each entry is the parentId of the column to render

      // ── Build skeleton ───────────────────────────────────────────────────
      container.innerHTML = '';
      container.style.cssText =
        'background:#fff;border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;font-family:inherit';

      // Search row
      const searchInput = el('input', {
        type: 'text',
        placeholder: 'Search offices by name…',
        style: 'flex:1;height:34px;padding:0 10px;border:1px solid #E5E7EB;border-radius:4px;font-size:13px;outline:none;font-family:inherit',
      });
      const clearBtn = el('button', {
        type: 'button',
        title: 'Clear search',
        style: 'display:none;border:none;background:#F3F4F6;color:#6C757D;cursor:pointer;border-radius:4px;padding:0 10px;height:34px;font-size:20px;line-height:1;font-family:inherit',
      });
      clearBtn.textContent = '×';
      const searchRow = el('div', {
        style: 'padding:12px 16px;border-bottom:1px solid #E5E7EB;display:flex;gap:8px;align-items:center',
      });
      searchRow.append(searchInput, clearBtn);
      container.appendChild(searchRow);

      // Search results panel
      const searchPanel = el('div', {
        style: 'display:none;background:#fff;border-bottom:1px solid #E5E7EB;max-height:360px;overflow-y:auto',
      });
      container.appendChild(searchPanel);

      // Breadcrumb strip
      const breadcrumb = el('div', {
        style: 'padding:8px 16px;border-bottom:1px solid #E5E7EB;background:#F8F9FA;min-height:36px;display:flex;align-items:center;gap:4px;flex-wrap:wrap;font-size:12px;color:#6C757D',
      });
      container.appendChild(breadcrumb);

      // Column browser
      const browser = el('div', {
        style: 'display:flex;overflow-x:auto;min-height:260px;max-height:380px;border-bottom:1px solid #E5E7EB',
      });
      container.appendChild(browser);

      // Selected office panel
      const selPanel = el('div', {
        style: 'display:none;padding:16px;background:#F0F9FF;border-top:2px solid #0076A7',
      });
      container.appendChild(selPanel);

      // ── Render ───────────────────────────────────────────────────────────
      function render() {
        renderColumns();
        renderBreadcrumb();
      }

      function renderBreadcrumb() {
        breadcrumb.innerHTML = '';
        const home = el('span', { style: 'cursor:pointer;color:#0076A7;font-weight:600' });
        home.textContent = 'All Offices';
        home.onclick = () => {
          columnTrail = [0];
          selectedId = null;
          render();
          renderSelPanel();
        };
        breadcrumb.appendChild(home);

        columnTrail.slice(1).forEach((nodeId, idx) => {
          const node = byId.get(nodeId);
          if (!node) return;
          const sep = el('span', { style: 'color:#D1D5DB;margin:0 3px' });
          sep.textContent = '›';
          const crumb = el('span', { style: 'cursor:pointer;color:#0076A7;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle' });
          crumb.title = node.nameEn;
          crumb.textContent = node.nameEn;
          const pos = idx + 1;
          crumb.onclick = () => {
            columnTrail = columnTrail.slice(0, pos + 1);
            render();
          };
          breadcrumb.append(sep, crumb);
        });
      }

      function renderColumns() {
        browser.innerHTML = '';
        columnTrail.forEach((parentId, colIdx) => {
          browser.appendChild(makeColumn(parentId, colIdx));
        });
        requestAnimationFrame(() => { browser.scrollLeft = browser.scrollWidth; });
      }

      function makeColumn(parentId, colIdx) {
        const items = byParent.get(parentId) || [];
        const col = el('div', {
          style: 'min-width:240px;max-width:280px;border-right:1px solid #E5E7EB;display:flex;flex-direction:column;flex-shrink:0;overflow:hidden',
        });

        // Column-level filter — only shown if > 12 items (critical for 350-item columns)
        let filterInput = null;
        if (items.length > 12) {
          const fWrap = el('div', {
            style: 'padding:6px 8px;border-bottom:1px solid #F0F0F0;background:#FAFAFA;flex-shrink:0',
          });
          filterInput = el('input', {
            type: 'text',
            placeholder: 'Filter…',
            style: 'width:100%;height:26px;padding:0 8px;border:1px solid #E5E7EB;border-radius:3px;font-size:12px;outline:none;font-family:inherit',
          });
          fWrap.appendChild(filterInput);
          col.appendChild(fWrap);
        }

        const list = el('div', { style: 'overflow-y:auto;flex:1' });
        col.appendChild(list);

        function paintList(q) {
          list.innerHTML = '';
          const shown = q
            ? items.filter(n =>
                n.nameEn.toLowerCase().includes(q.toLowerCase()) ||
                n.nameBn.includes(q)
              )
            : items;

          if (shown.length === 0) {
            const empty = el('div', { style: 'padding:16px;font-size:12px;color:#9CA3AF;text-align:center' });
            empty.textContent = 'No results';
            list.appendChild(empty);
            return;
          }

          shown.forEach(node => {
            const isSel = node.id === selectedId;
            const hasKids = (byParent.get(node.id) || []).length > 0;

            const row = el('div', {
              style: `padding:8px 12px;cursor:pointer;border-bottom:1px solid #F3F4F6;display:flex;align-items:center;gap:8px${isSel ? ';background:#006633' : ''}`,
            });
            if (!isSel) {
              row.onmouseover = () => { row.style.background = '#F0F9FF'; };
              row.onmouseout  = () => { row.style.background = ''; };
            }

            const textWrap = el('div', { style: 'flex:1;min-width:0' });

            const nameEnEl = el('div', {
              style: `font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:${isSel ? '#fff' : '#212529'}`,
            });
            nameEnEl.textContent = node.nameEn;
            textWrap.appendChild(nameEnEl);

            if (node.nameBn) {
              const nameBnEl = el('div', {
                style: `font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:1px;color:${isSel ? 'rgba(255,255,255,.7)' : '#9CA3AF'}`,
              });
              nameBnEl.textContent = node.nameBn;
              textWrap.appendChild(nameBnEl);
            }
            row.appendChild(textWrap);

            if (hasKids) {
              const arrow = el('span', {
                style: `font-size:14px;flex-shrink:0;color:${isSel ? 'rgba(255,255,255,.8)' : '#9CA3AF'}`,
              });
              arrow.textContent = '›';
              row.appendChild(arrow);
            }

            row.onclick = () => {
              selectedId = node.id;
              if (hasKids) {
                columnTrail = [...columnTrail.slice(0, colIdx + 1), node.id];
              }
              render();
              renderSelPanel();
            };

            list.appendChild(row);
          });
        }

        if (filterInput) filterInput.addEventListener('input', () => paintList(filterInput.value));
        paintList('');
        return col;
      }

      function renderSelPanel() {
        if (!selectedId) { selPanel.style.display = 'none'; return; }
        const node = byId.get(selectedId);
        if (!node) { selPanel.style.display = 'none'; return; }

        const ancestors = getAncestors(selectedId, byId);
        selPanel.innerHTML = '';
        selPanel.style.display = 'block';

        if (node.isAbstractOffice) {
          const warn = el('div', {
            style: 'display:inline-flex;align-items:center;gap:5px;background:#FFF7ED;border:1px solid #FED7AA;color:#C2410C;font-size:11px;font-weight:700;padding:3px 8px;border-radius:4px;margin-bottom:10px',
          });
          warn.textContent = '⚠ Group — not a selectable office';
          selPanel.appendChild(warn);
        }

        const nameEnEl = el('div', { style: 'font-size:15px;font-weight:700;color:#212529;margin-bottom:2px' });
        nameEnEl.textContent = node.nameEn;
        selPanel.appendChild(nameEnEl);

        if (node.nameBn) {
          const nameBnEl = el('div', { style: 'font-size:13px;color:#6C757D;margin-bottom:6px' });
          nameBnEl.textContent = node.nameBn;
          selPanel.appendChild(nameBnEl);
        }

        if (ancestors.length) {
          const pathEl = el('div', { style: 'font-size:12px;color:#6C757D;margin-bottom:4px' });
          pathEl.textContent = ancestors.map(a => a.nameEn).join(' › ');
          selPanel.appendChild(pathEl);
        }

        const idEl = el('div', { style: 'font-size:11px;color:#9CA3AF;margin-bottom:12px' });
        idEl.textContent = `Office ID: ${node.id}`;
        selPanel.appendChild(idEl);

        const confirmBtn = el('button', {
          type: 'button',
          style: 'display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 14px;background:#0076A7;color:#fff;border:none;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit',
        });
        confirmBtn.textContent = '✓ Select this office';
        confirmBtn.onclick = () => {
          if (opts.onSelect) {
            opts.onSelect({ id: node.id, nameEn: node.nameEn, nameBn: node.nameBn, isAbstractOffice: node.isAbstractOffice, path: ancestors });
          }
        };
        selPanel.appendChild(confirmBtn);
      }

      // ── Search mode ──────────────────────────────────────────────────────
      function setSearchMode(active) {
        browser.style.display    = active ? 'none' : 'flex';
        breadcrumb.style.display = active ? 'none' : 'flex';
        searchPanel.style.display = active ? 'block' : 'none';
      }

      searchInput.addEventListener('input', () => {
        const q = searchInput.value.trim();
        clearBtn.style.display = q ? 'block' : 'none';
        if (!q) { setSearchMode(false); return; }
        setSearchMode(true);
        paintSearchResults(q);
      });
      searchInput.addEventListener('focus', () => {
        searchInput.style.borderColor = '#0076A7';
        searchInput.style.boxShadow = '0 0 0 2px rgba(0,118,167,.1)';
      });
      searchInput.addEventListener('blur', () => {
        searchInput.style.borderColor = '#E5E7EB';
        searchInput.style.boxShadow = '';
      });
      clearBtn.onclick = () => {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        setSearchMode(false);
      };

      function paintSearchResults(q) {
        searchPanel.innerHTML = '';
        const lc = q.toLowerCase();
        const matches = [];
        for (const [, node] of byId) {
          if (matches.length >= 25) break;
          if (node.nameEn.toLowerCase().includes(lc) || node.nameBn.includes(q)) {
            matches.push(node);
          }
        }

        if (matches.length === 0) {
          const empty = el('div', { style: 'padding:20px;font-size:13px;color:#9CA3AF;text-align:center' });
          empty.textContent = 'No offices found';
          searchPanel.appendChild(empty);
          return;
        }

        matches.forEach(node => {
          const ancestors = getAncestors(node.id, byId);
          const item = el('div', { style: 'padding:10px 16px;cursor:pointer;border-bottom:1px solid #F3F4F6' });
          item.onmouseover = () => { item.style.background = '#F0F9FF'; };
          item.onmouseout  = () => { item.style.background = ''; };

          const nameEnEl = el('div', { style: 'font-size:13px;font-weight:600;color:#212529' });
          nameEnEl.textContent = node.nameEn;
          item.appendChild(nameEnEl);

          if (node.nameBn) {
            const nameBnEl = el('div', { style: 'font-size:11.5px;color:#9CA3AF;margin-top:1px' });
            nameBnEl.textContent = node.nameBn;
            item.appendChild(nameBnEl);
          }

          if (ancestors.length) {
            const pathEl = el('div', { style: 'font-size:11px;color:#6C757D;margin-top:3px' });
            pathEl.textContent = ancestors.map(a => a.nameEn).join(' › ');
            item.appendChild(pathEl);
          }

          item.onclick = () => {
            selectedId = node.id;
            columnTrail = [0, ...getAncestors(node.id, byId).map(a => a.id)];
            searchInput.value = '';
            clearBtn.style.display = 'none';
            setSearchMode(false);
            render();
            renderSelPanel();
          };

          searchPanel.appendChild(item);
        });

        const footer = el('div', { style: 'padding:6px 16px;font-size:11px;color:#9CA3AF;background:#FAFAFA;border-top:1px solid #F3F4F6' });
        footer.textContent = matches.length >= 25
          ? 'Showing first 25 results'
          : `${matches.length} result${matches.length === 1 ? '' : 's'}`;
        searchPanel.appendChild(footer);
      }

      // ── Initial render ───────────────────────────────────────────────────
      if (opts.initialValue) {
        const initNode = byId.get(opts.initialValue);
        if (initNode) {
          selectedId = opts.initialValue;
          columnTrail = [0, ...getAncestors(opts.initialValue, byId).map(a => a.id)];
          render();
          renderSelPanel();
          return;
        }
      }
      render();
    },
  };
})();
