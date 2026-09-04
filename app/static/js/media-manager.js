/**
 * Centralized Media Manager JS Library (WordPress Style)
 * Usage: openMediaManager({ category: 'blog'|'shop'|'general', onSelect: function(file) { ... } })
 */

let currentMediaFiles = [];
let selectedMediaFile = null;
let mediaSelectCallback = null;

function openMediaManager(options = {}) {
  mediaSelectCallback = options.onSelect || null;
  const categoryFilter = options.category || '';

  const catSelect = document.getElementById('mediaCategorySelect');
  if (catSelect && categoryFilter) {
    catSelect.value = categoryFilter;
  }

  const uploadCatSelect = document.getElementById('uploadCategorySelect');
  if (uploadCatSelect && categoryFilter) {
    uploadCatSelect.value = categoryFilter;
  }

  const modalEl = document.getElementById('mediaModal');
  if (modalEl) {
    try {
      let bsModal = (typeof bootstrap !== 'undefined' && bootstrap.Modal) ? (bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)) : null;
      if (bsModal) {
        bsModal.show();
      } else {
        modalEl.classList.add('show');
        modalEl.style.display = 'block';
        modalEl.removeAttribute('aria-hidden');
      }
    } catch (e) {
      console.error('Error initializing Bootstrap modal:', e);
      modalEl.classList.add('show');
      modalEl.style.display = 'block';
    }
    reloadMediaLibrary();
  } else {
    console.error('mediaModal element not found in DOM!');
  }
}

async function reloadMediaLibrary() {
  const grid = document.getElementById('mediaGrid');
  if (!grid) return;
  grid.innerHTML = '<div class="col-12 text-center text-secondary py-5">Loading files...</div>';

  selectedMediaFile = null;
  updateMediaDetailPanel();

  const category = document.getElementById('mediaCategorySelect')?.value || '';
  const search = document.getElementById('mediaSearchInput')?.value || '';

  let url = `/api/media/files?t=${Date.now()}`;
  if (category) url += `&category=${encodeURIComponent(category)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;

  try {
    const resp = await fetch(url);
    if (resp.status === 401) {
      grid.innerHTML = '<div class="col-12 text-center text-danger py-5">⚠️ Trebuie să fii autentificat pentru a accesa biblioteca media. <a href="/admin/login" class="text-primary fw-bold ms-1">Conectează-te ↗</a></div>';
      return;
    }
    const data = await resp.json();
    if (data.ok && Array.isArray(data.files)) {
      currentMediaFiles = data.files;
      renderMediaGrid(currentMediaFiles);
    } else {
      grid.innerHTML = `<div class="col-12 text-center text-danger py-5">Eroare la încărcare: ${data.error || 'Necunoscută'}</div>`;
    }
  } catch (err) {
    console.error(err);
    grid.innerHTML = '<div class="col-12 text-center text-danger py-5">Eroare de rețea la încărcarea fișierelor.</div>';
  }
}

function filterMediaLibrary() {
  reloadMediaLibrary();
}

function renderMediaGrid(files) {
  const grid = document.getElementById('mediaGrid');
  if (!grid) return;
  grid.innerHTML = '';

  if (files.length === 0) {
    grid.innerHTML = '<div class="col-12 text-center text-secondary py-5">No images found in the library.</div>';
    return;
  }

  files.forEach(file => {
    const cardCol = document.createElement('div');
    cardCol.className = 'col-4 col-sm-3 col-md-3 col-lg-2';

    const isSelected = selectedMediaFile && selectedMediaFile.id === file.id;

    cardCol.innerHTML = `
    <div class="card h-100 p-1 text-center border cursor-pointer media-card ${isSelected ? 'border-primary border-2 bg-primary-subtle' : 'bg-white'}"
    style="cursor: pointer;" onclick="selectMediaFile(${file.id})">
    ${file.file_url.match(/\.(zip|rar|7z|gz|pdf|doc|docx)$/i) ? `
      <div class="rounded bg-primary-subtle text-primary d-flex flex-column align-items-center justify-content-center w-100" style="height: 85px;">
      <span class="fs-2">${file.file_url.endsWith('.pdf') ? '📄' : '📦'}</span>
      <span class="badge bg-primary mt-1" style="font-size: 9px;">${file.file_url.rsplit ? file.file_url.rsplit('.').pop() : 'DIGITAL'}</span>
      </div>
      ` : `
      <img src="${file.file_url}" class="rounded object-fit-cover w-100" style="height: 85px;" alt="${file.alt_text}">
      `}
      <div class="small text-truncate mt-1 px-1 fw-semibold text-secondary" style="font-size: 11px;" title="${file.filename}">
      ${file.filename}
      </div>
      </div>
      `;
      grid.appendChild(cardCol);
  });
}

function selectMediaFile(fileId) {
  selectedMediaFile = currentMediaFiles.find(f => f.id === fileId) || null;
  renderMediaGrid(currentMediaFiles);
  updateMediaDetailPanel();
}

function updateMediaDetailPanel() {
  const placeholder = document.getElementById('mediaDetailPlaceholder');
  const content = document.getElementById('mediaDetailContent');
  const insertBtn = document.getElementById('insertMediaBtn');

  if (!selectedMediaFile) {
    placeholder?.classList.remove('d-none');
    content?.classList.add('d-none');
    if (insertBtn) insertBtn.disabled = true;
    return;
  }

  placeholder?.classList.add('d-none');
  content?.classList.remove('d-none');
  if (insertBtn) insertBtn.disabled = false;

  document.getElementById('detailImgPreview').src = selectedMediaFile.file_url;
  document.getElementById('detailFilename').innerText = selectedMediaFile.filename;
  document.getElementById('detailMeta').innerText = `${(selectedMediaFile.file_size / 1024).toFixed(1)} KB • ${selectedMediaFile.category}`;
  document.getElementById('detailFileUrl').value = selectedMediaFile.file_url;
}

function closeMediaManagerModal() {
  const modalEl = document.getElementById('mediaModal');
  if (!modalEl) return;

  if (document.activeElement && modalEl.contains(document.activeElement)) {
    document.activeElement.blur();
  }

  try {
    if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
      const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
      if (bsModal) {
        bsModal.hide();
      }
    }
  } catch (e) {
    console.warn('Bootstrap modal hide warning:', e);
  }

  modalEl.classList.remove('show');
  modalEl.style.display = 'none';
  modalEl.setAttribute('aria-hidden', 'true');
  document.querySelectorAll('.modal-backdrop, .fade.show.modal-backdrop').forEach(b => b.remove());
  document.body.classList.remove('modal-open');
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';

  setTimeout(() => {
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
    modalEl.setAttribute('aria-hidden', 'true');
    document.querySelectorAll('.modal-backdrop, .fade.show.modal-backdrop').forEach(b => b.remove());
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
  }, 150);
}

function confirmMediaSelection() {
  if (!selectedMediaFile) return;

  if (selectedMediaFile.file_url && !selectedMediaFile.file_url.startsWith('http')) {
    selectedMediaFile.file_url = window.location.origin + (selectedMediaFile.file_url.startsWith('/') ? '' : '/') + selectedMediaFile.file_url;
  }

  if (typeof mediaSelectCallback === 'function') {
    mediaSelectCallback(selectedMediaFile);
  }

  closeMediaManagerModal();
}

async function uploadSelectedMediaFiles(inputOrFiles) {
  let files = [];
  if (inputOrFiles instanceof HTMLInputElement) {
    if (inputOrFiles.files) files = Array.from(inputOrFiles.files);
  } else if (inputOrFiles instanceof FileList || Array.isArray(inputOrFiles)) {
    files = Array.from(inputOrFiles);
  }

  if (files.length === 0) return;

  const category = document.getElementById('uploadCategorySelect')?.value || 'general';
  const formData = new FormData();
  formData.append('category', category);

  files.forEach(file => {
    formData.append('upload_files', file);
  });

  try {
    const resp = await fetch('/api/media/upload', {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();
    if (data.ok) {
      if (inputOrFiles instanceof HTMLInputElement) {
        inputOrFiles.value = '';
      }
      if (typeof switchMediaTab === 'function') {
        switchMediaTab('library');
      }
      reloadMediaLibrary();
      if (data.files && data.files.length > 0) {
        selectMediaFile(data.files[0].id);
      }
    } else {
      alert('Eroare la încărcare: ' + (data.error || 'Necunoscută'));
    }
  } catch (err) {
    console.error(err);
    alert('Eroare de rețea la încărcare.');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('mediaDropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.add('border-primary', 'bg-primary-subtle');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => {
      dropzone.classList.remove('border-primary', 'bg-primary-subtle');
    }, false);
  });

  dropzone.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      uploadSelectedMediaFiles(dt.files);
    }
  }, false);
});

async function deleteSelectedMediaFile() {
  if (!selectedMediaFile) return;
  if (!confirm(`Ștergi definitiv imaginea "${selectedMediaFile.filename}" din bibliotecă?`)) return;

  const formData = new FormData();
  formData.append('file_id', selectedMediaFile.id);

  try {
    const resp = await fetch('/api/media/delete', {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();
    if (data.ok) {
      selectedMediaFile = null;
      reloadMediaLibrary();
    } else {
      alert('Eroare la ștergere: ' + (data.error || 'Permisiune respinsă'));
    }
  } catch (err) {
    console.error(err);
    alert('Eroare de rețea la ștergere.');
  }
}

function selectFromMediaLibraryForShop(file) {
  if (!file || !file.file_url) return;
  const fullUrl = file.file_url.startsWith('http') ? file.file_url : (window.location.origin + (file.file_url.startsWith('/') ? '' : '/') + file.file_url);
  const featInput = document.getElementById('prod_featured_image');
  if (featInput) {
    featInput.value = fullUrl;
  }
  const container = document.getElementById('existingImagesContainer');
  const list = document.getElementById('existingImagesList');
  if (list && container) {
    container.classList.remove('d-none');
    const card = document.createElement('div');
    card.className = 'col-6 col-md-3';
    card.innerHTML = `
    <div class="card h-100 p-2 text-center border shadow-sm bg-white">
    <img src="${fullUrl}" class="rounded object-fit-cover mb-2" style="width: 100%; height: 90px;">
    <input type="hidden" name="existing_images" value="${fullUrl}">
    <span class="badge bg-primary small mb-1">🖼️ Din Bibliotecă</span>
    <button type="button" class="btn btn-xs btn-outline-danger py-0 px-2 small mt-1" onclick="this.closest('.col-6').remove()">
    🗑️ Înlătură
    </button>
    </div>
    `;
    list.appendChild(card);
  }
}


async function cropSelectedMedia(preset) {
  if (!selectedMediaFile) return;
  const label = (preset === 'og') ? '1200x630 (OpenGraph Social Card)' : '500x500 (Pătrat Shop)';
  if (!confirm(`Redimensionezi / tai poza "${selectedMediaFile.filename}" în format ${label}?`)) return;

  const formData = new FormData();
  formData.append('file_id', selectedMediaFile.id);
  formData.append('preset', preset);

  try {
    const resp = await fetch('/api/media/crop', {
      method: 'POST',
      body: formData
    });
    const data = await resp.json();
    if (data.ok && data.file) {
      selectedMediaFile.file_size = data.file.file_size;
      const previewImg = document.getElementById('detailImgPreview');
      if (previewImg) {
        previewImg.src = selectedMediaFile.file_url + '?t=' + Date.now();
      }
      reloadMediaLibrary();
      alert('Poza a fost tăiată și redimensionată cu succes de Pillow!');
    } else {
      alert('Eroare la redimensionare: ' + (data.error || 'Necunoscută'));
    }
  } catch (err) {
    console.error(err);
    alert('Eroare de rețea la redimensionare.');
  }
}


function selectHeroImageFromMedia(file) {
  if (!file || !file.file_url) return;
  const relUrl = file.file_url.startsWith('http') ? file.file_url : (file.file_url.startsWith('/') ? file.file_url : '/' + file.file_url);
  const urlInput = document.getElementById('hero_image_url');
  if (urlInput) urlInput.value = relUrl;

  const previewDiv = document.getElementById('hero_image_preview');
  if (previewDiv) {
    previewDiv.innerHTML = '<img src="' + relUrl + '" alt="Hero image" style="max-width: 260px; max-height: 140px; object-fit: cover; border-radius: 8px;" class="shadow-sm border" />';
  }
}


window.selectFromMediaLibraryForShop = selectFromMediaLibraryForShop;
