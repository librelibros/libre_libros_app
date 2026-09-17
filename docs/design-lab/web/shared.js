/* Local-only prototype. No fetch, storage, cookies, modules or dependencies. */
(() => {
  'use strict';
  const variant = document.body.dataset.variant;
  const isB = variant === 'b';
  const $ = (id) => document.getElementById(id);
  const esc = (text) => String(text).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const books = [
    {id:'mates-3', title:'Fracciones en la vida cotidiana', course:'3º Primaria', subject:'Matemáticas', summary:'Repartos, mitades y cuartos con situaciones cercanas.', tag:'Actividad guiada', time:'30 min', cover:'½ + ¼', body:'# Fracciones en la vida cotidiana\n\nObjetivo: reconocer mitades y cuartos en un reparto.\n\n## Explorar\nDibuja una naranja y divídela en cuatro partes iguales. ¿Cuántas partes forman la mitad?\n\n## Practicar\nRepresenta 1/2 y 1/4 con tiras de papel. Compara sus tamaños.\n\n## Cierre\nExplica con tus palabras cómo reconocer un cuarto.'},
    {id:'lengua-3', title:'Historias con principio y final', course:'3º Primaria', subject:'Lengua', summary:'Organiza una narración breve en tres momentos.', tag:'Escritura creativa', time:'45 min', cover:'Aa', body:'# Historias con principio y final\n\nObjetivo: organizar una narración.\n\n## Planificar\nElige un lugar y un personaje imaginario.\n\n## Escribir\nRedacta un inicio, un problema y un desenlace.\n\n## Revisar\nComprueba que la historia se entiende sin explicaciones extra.'},
    {id:'ciencias-4', title:'El pequeño huerto', course:'4º Primaria', subject:'Conocimiento del medio', summary:'Observa las necesidades de las plantas y su entorno.', tag:'Proyecto de aula', time:'45 min', cover:'✳', body:'# El pequeño huerto\n\nObjetivo: identificar las necesidades de las plantas.\n\n## Observar\nDescribe las partes de una planta.\n\n## Investigar\nCompara un entorno soleado con otro de sombra.\n\n## Cierre\nDiseña una ficha de cuidados sin datos personales.'},
    {id:'mates-4', title:'Medimos nuestro entorno', course:'4º Primaria', subject:'Matemáticas', summary:'Longitudes y unidades con objetos de uso cotidiano.', tag:'Práctica manipulativa', time:'30 min', cover:'cm / m', body:'# Medimos nuestro entorno\n\nObjetivo: elegir unidades de longitud.\n\n## Estimar\nEstima cuánto mide una mesa.\n\n## Medir\nComprueba la estimación con una regla.\n\n## Cierre\nExplica cuándo usar centímetros y cuándo metros.'},
    {id:'lengua-5', title:'Leemos una noticia', course:'5º Primaria', subject:'Lengua', summary:'Distingue titular, hechos y opiniones en un texto ficticio.', tag:'Lectura comprensiva', time:'30 min', cover:'¿Qué?', body:'# Leemos una noticia\n\nObjetivo: distinguir hechos y opiniones.\n\n## Leer\nUn parque imaginario estrena una fuente. El ayuntamiento anuncia su apertura el lunes.\n\n## Analizar\nPropón un titular y localiza el hecho principal.\n\n## Cierre\nEscribe una opinión y explica por qué no es un hecho.'},
    {id:'ciencias-6', title:'Cuidamos el agua', course:'6º Primaria', subject:'Conocimiento del medio', summary:'El ciclo del agua y pequeños hábitos de consumo responsable.', tag:'Proyecto de aula', time:'45 min', cover:'H₂O', body:'# Cuidamos el agua\n\nObjetivo: comprender el ciclo del agua.\n\n## Explorar\nDibuja evaporación, condensación y precipitación.\n\n## Proponer\nEnumera tres hábitos para ahorrar agua.\n\n## Cierre\nExplica qué hábito te parece más útil y por qué.'}
  ];
  const drafts = new Map();
  const proposals = [{id:'propuesta-1', book:'mates-3', title:'Añadir un ejemplo de reparto', text:'Propuesta ficticia: añadir una actividad con una naranja dividida en cuartos.', author:'María López', content:'Nuevo ejemplo: representa tres cuartos y compáralos con una mitad.'}];
  let applied = {course:'', subject:''};
  let currentBook = books[0];
  let dialogAction = null;
  let returnFocus = null;
  let importSequence = 0;
  const button = (id, text, action, secondary = false) => `<button type="button" class="button${secondary ? ' secondary' : ''}" data-testid="${id}" data-action="${action}">${text}</button>`;
  const link = (id, text, href, classes = '') => `<a class="${classes}" data-testid="${id}" href="${href}">${text}</a>`;
  const courses = ['1º Primaria','2º Primaria','3º Primaria','4º Primaria','5º Primaria','6º Primaria'];
  const subjects = ['Matemáticas','Lengua','Conocimiento del medio'];
  const options = (values) => values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
  $('app').innerHTML = `
    <a class="skip-link" href="#main-content">Saltar al contenido</a>
    <div class="prototype-note" data-testid="prototype-banner"><strong>PROTOTIPO ${variant.toUpperCase()} · sin servidor</strong> · Datos ficticios, sin alumnado. No conserva cambios tras recarga. <a href="index.html">Cambiar versión</a></div>
    <div class="shell">
      <aside class="sidebar">
        <a class="brand" href="#panel" aria-label="Libre Libros · inicio"><img src="libre-libros-mark.svg" class="brand-mark" width="160" height="70" alt="Biblioteca docente"><span class="brand-note">Biblioteca colaborativa para edición, revisión y publicación de materiales.</span></a>
        <nav class="nav" aria-label="Navegación principal">
          ${link('nav-home', isB ? 'Inicio' : 'Panel', '#panel')}
          ${link('nav-catalog', isB ? 'Catálogo' : 'Libros', '#catalogo')}
          ${link('nav-new', isB ? 'Crear material' : 'Nuevo libro', '#nuevo')}
          ${link('nav-pending', 'Pendientes (1)', '#pendientes')}
          ${button('nav-exit', 'Cerrar sesión', 'exit', true)}
        </nav>
      </aside>
      <main class="content" id="main-content" tabindex="-1">
        <header class="topbar"><div><p class="eyebrow">${isB ? 'Biblioteca docente' : 'Sesión'}</p><h1 id="page-title">${isB ? 'Tu próxima clase empieza aquí' : 'Panel'}</h1></div><div class="profile"><span class="chip" data-testid="user-name">Elena Martín</span><label class="role-label" for="role">Rol de demostración<select id="role" data-testid="role-select"><option value="docente">Docente</option><option value="coordinador">Coordinador</option></select></label></div></header>
        <p class="sr-only" role="status" aria-live="polite" id="global-status" data-testid="global-status"></p>
        <div id="home-view" data-testid="home-view">
          <section class="card pending" id="pending-section" aria-labelledby="pending-title" data-testid="pending-section"><p class="eyebrow">Para ti</p><h2 id="pending-title">${isB ? 'Pendiente de revisión' : 'Avisos y propuestas de cambio'}</h2><p>Hay <strong data-testid="pending-count" id="pending-count">1</strong> propuesta(s) pendiente(s) de revisar.</p><p class="muted">Accesible para docentes y coordinación. Propuestas ficticias; sin publicación real.</p><div id="pending-list"></div></section>
          <section class="stats" id="stats" aria-label="Resumen de biblioteca" data-testid="stats"><article class="card"><p class="eyebrow">Libros visibles</p><strong>6</strong></article><article class="card"><p class="eyebrow">Libros públicos</p><strong>6</strong></article><article class="card"><p class="eyebrow">Actividad reciente</p><strong id="activity-count">1</strong></article></section>
          <section class="card catalog" id="catalog-section" aria-labelledby="catalog-title" data-testid="catalog-section"><div class="section-header"><div><p class="eyebrow">${isB ? 'Encuentra · lee · adapta' : 'Catálogo'}</p><h2 id="catalog-title">${isB ? 'Materiales para tu clase' : 'Libros por curso y materia'}</h2></div>${link('create-material', isB ? 'Crear material' : 'Crear libro', '#nuevo', 'button')}</div><p class="muted">Materiales sintéticos de Primaria. Abre un libro y adapta tu propia copia, sin cambiar el original.</p>
            <form id="filters" class="filters" data-testid="filter-form"><label for="course">Curso<select id="course" name="course" data-testid="filter-course"><option value="">Todos los cursos</option>${options(courses)}</select></label><label for="subject">Materia<select id="subject" name="subject" data-testid="filter-subject"><option value="">Todas las materias</option>${options(subjects)}</select></label><button class="button" type="submit" data-testid="filter-apply">Filtrar</button>${button('filter-clear','Limpiar','clear',true)}</form>
            <p id="result-count" role="status" data-testid="result-count"></p><div id="catalog-results" data-testid="catalog-results"></div><div id="empty-state" class="empty" data-testid="empty-state" hidden><h3>No hay materiales con estos filtros</h3><p>Prueba otro curso o materia, o usa «Limpiar» para ver los seis materiales.</p></div>
          </section>
          <details class="card help"><summary>Ayuda opcional: cómo utilizar la biblioteca</summary><p>Filtra por curso y materia, abre un material y adapta una copia. Guardar conserva una copia solo en memoria; enviar a revisión es otra acción. No necesitas completar ninguna guía.</p></details>
        </div>
        <section class="card stack" id="detail-view" data-testid="detail-view" hidden></section>
        <section class="card stack editor-neutral" id="editor-view" data-testid="editor-view" hidden>
          ${link('editor-back','← Volver al material','#material/mates-3')}
          <div><p class="eyebrow">Mi copia docente · simulación</p><h2 id="editor-title">Adaptar copia</h2><p>El material base no cambia. No introduzcas datos personales ni de alumnado.</p></div>
          <label for="copy-title">Título de mi copia<input id="copy-title" data-testid="copy-title" maxlength="160"></label>
          <label for="import-file">Importar texto (.txt o .md)<input id="import-file" data-testid="import-file" type="file" accept=".txt,.md,text/plain,text/markdown" aria-describedby="import-help"></label><p class="muted" id="import-help">Máximo 1 MB, texto UTF-8. Se pedirá confirmación antes de sustituir el contenido; el título no cambia. No se sube ningún archivo.</p><p id="import-status" role="status" data-testid="import-status"></p>
          <label for="editor-text">Contenido de mi copia<textarea id="editor-text" data-testid="editor-text" rows="14" aria-describedby="editor-help"></textarea></label><p id="editor-help" class="muted">Texto plano o Markdown, sin renderizado. El mismo editor en ambas versiones.</p>
          <div class="actions">${button('save-copy','Guardar copia · SIMULADO','save')}${button('send-review','Enviar a revisión · SIMULADO','review',true)}${button('editor-pdf','Exportar PDF · mock','pdf',true)}</div>
          <p id="copy-status" data-testid="copy-status" role="status"></p><p id="review-status" data-testid="review-status" role="status"></p>
        </section>
        <section class="card stack" id="proposal-view" data-testid="proposal-view" hidden></section>
        <section class="card stack" id="new-view" data-testid="new-view" hidden><h2>Crear material · simulación</h2><p>Se abrirá un borrador local vacío. No se añadirá al catálogo compartido.</p><form id="new-form" class="stack"><label for="new-title">Título<input id="new-title" data-testid="new-title" required maxlength="160"></label><label for="new-course">Curso<select id="new-course" data-testid="new-course">${options(courses)}</select></label><label for="new-subject">Materia<select id="new-subject" data-testid="new-subject">${options(subjects)}</select></label><button class="button" data-testid="new-submit" type="submit">Abrir borrador</button></form></section>
        <footer class="muted">Libre Libros · laboratorio local · Perfil y contenidos ficticios · No genera archivos ni envía propuestas reales.</footer>
      </main>
    </div>
    <dialog id="mock-dialog" data-testid="mock-dialog" aria-labelledby="dialog-title" aria-describedby="dialog-description"><h2 id="dialog-title" data-testid="dialog-title"></h2><p id="dialog-description"></p><div class="actions"><button type="button" class="button secondary" id="dialog-cancel" data-testid="dialog-cancel" autofocus>Cancelar</button><button type="button" class="button" id="dialog-confirm" data-testid="dialog-confirm">Confirmar</button></div></dialog>`;

  // Real DOM order follows visual/task order (also for keyboard and screen readers).
  if (isB) {
    const home = $('home-view');
    home.prepend($('catalog-section'));
    home.insertBefore($('stats'), home.querySelector('.help'));
  }
  function announce(text) { $('global-status').textContent = text; }
  function showDialog(title, description, action, confirmText = 'Confirmar') {
    returnFocus = document.activeElement;
    dialogAction = action || null;
    $('dialog-title').textContent = title;
    $('dialog-description').textContent = description;
    $('dialog-cancel').textContent = action ? 'Cancelar' : 'Cerrar';
    $('dialog-confirm').hidden = !action;
    $('dialog-confirm').textContent = confirmText;
    $('mock-dialog').showModal();
    $('dialog-cancel').focus();
  }
  $('dialog-cancel').addEventListener('click', () => $('mock-dialog').close());
  $('dialog-confirm').addEventListener('click', () => {
    const action = dialogAction;
    $('mock-dialog').close();
    if (action) action();
  });
  $('mock-dialog').addEventListener('close', () => {
    dialogAction = null;
    if (returnFocus && returnFocus.isConnected && !returnFocus.closest('[hidden]')) returnFocus.focus();
  });
  function renderPending() {
    $('pending-count').textContent = proposals.length;
    $('activity-count').textContent = proposals.length;
    document.querySelector('[data-testid="nav-pending"]').textContent = `Pendientes (${proposals.length})`;
    $('pending-list').innerHTML = proposals.map((p) => `<article class="pending-row"><div><span class="chip warning">Pendiente</span><h3>${esc(p.title)}</h3><p class="muted">${esc(books.find((b) => b.id === p.book)?.title || 'Material nuevo')} · ${esc(p.author)} · 1 cambio</p></div>${link(`open-${p.id}`, 'Ver propuesta →', `#propuesta/${p.id}`)}</article>`).join('');
  }
  function renderCatalog() {
    const found = books.filter((b) => (!applied.course || b.course === applied.course) && (!applied.subject || b.subject === applied.subject));
    const card = (b) => `<article class="book-card card" data-testid="material-card-${b.id}" data-material-id="${b.id}"><div class="book-cover" aria-hidden="true">${esc(b.cover)}</div><div class="chips"><span class="chip">${esc(b.course)}</span><span class="chip">${esc(b.subject)}</span></div><h3>${esc(b.title)}</h3><p class="muted">${esc(b.summary)}</p><div class="chips"><span class="chip">${esc(b.tag)}</span><span class="chip">${b.time}</span><span class="chip">${isB ? 'Compartido' : 'public'}</span><span class="chip">${isB ? 'Biblioteca local' : 'local'}</span></div>${link(`open-material-${b.id}`, 'Abrir material →', `#material/${b.id}`, 'open-material')}</article>`;
    if (isB || location.hash === '#catalogo') $('catalog-results').innerHTML = `<div class="catalog-grid">${found.map(card).join('')}</div>`;
    else $('catalog-results').innerHTML = [...new Set(found.map((b) => b.course))].map((course) => `<section class="course-group"><h3>${esc(course)}</h3>${[...new Set(found.filter((b) => b.course === course).map((b) => b.subject))].map((subject) => `<h4>${esc(subject)}</h4><div class="catalog-grid">${found.filter((b) => b.course === course && b.subject === subject).map(card).join('')}</div>`).join('')}</section>`).join('');
    $('result-count').textContent = `${found.length} de 6 materiales${applied.course ? ` · ${applied.course}` : ''}${applied.subject ? ` · ${applied.subject}` : ''}`;
    $('empty-state').hidden = found.length > 0;
  }
  function getDraft(book) {
    if (!drafts.has(book.id)) drafts.set(book.id, {title:`${book.title} · mi copia`, text:book.body, saved:null, sent:null});
    return drafts.get(book.id);
  }
  function updateEditorStatus() {
    const d = getDraft(currentBook);
    const matches = (snapshot) => snapshot && snapshot.title === d.title && snapshot.text === d.text;
    $('copy-status').textContent = matches(d.saved) ? 'Copia guardada · SIMULADO · solo en memoria. No se ha publicado.' : 'Cambios sin guardar. Solo en memoria; se pierden al recargar.';
    $('review-status').textContent = matches(d.sent) ? 'Esta copia se ha enviado a revisión · SIMULADO. No se ha publicado.' : d.sent ? 'Tienes cambios posteriores al último envío simulado.' : 'Esta copia no se ha enviado a revisión.';
  }
  function route() {
    const raw = location.hash.slice(1) || 'panel';
    const [page, id] = raw.split('/');
    ['home','detail','editor','proposal','new'].forEach((v) => { $(`${v}-view`).hidden = true; });
    document.querySelectorAll('.nav a').forEach((a) => {
      a.removeAttribute('aria-current');
      if (a.hash === `#${page}` || (['material','editar'].includes(page) && a.hash === '#catalogo') || (page === 'propuesta' && a.hash === '#pendientes')) a.setAttribute('aria-current','page');
    });
    if (['material','editar'].includes(page)) {
      const book = books.find((b) => b.id === id) || (currentBook.id === id ? currentBook : null);
      if (!book) { location.hash = 'catalogo'; return; }
      currentBook = book;
      $('page-title').textContent = page === 'editar' ? 'Adaptar mi copia' : book.title;
      if (page === 'material') {
        $('detail-view').hidden = false;
        $('detail-view').innerHTML = `${link('detail-back','← Volver al catálogo','#catalogo')}<div><p class="eyebrow">${esc(book.course)} · ${esc(book.subject)}</p><h2 data-testid="material-title">${esc(book.title)}</h2><p>${esc(book.summary)}</p><div class="chips"><span class="chip">Material base · compartido</span><span class="chip">${esc(book.tag)} · ${book.time}</span></div></div><div class="actions">${link('adapt-copy','Adaptar una copia',`#editar/${book.id}`,'button')}${button('detail-pdf','Exportar PDF · mock','pdf',true)}</div><p class="muted">Lectura del material base. Tu copia docente se edita por separado.</p><pre class="reading" data-testid="material-content">${esc(book.body)}</pre>`;
      } else {
        $('editor-view').hidden = false;
        const d = getDraft(book);
        $('editor-title').textContent = book.title;
        $('copy-title').value = d.title;
        $('editor-text').value = d.text;
        document.querySelector('[data-testid="editor-back"]').href = `#material/${book.id}`;
        $('import-file').value = '';
        $('import-status').textContent = '';
        updateEditorStatus();
      }
    } else if (page === 'propuesta') {
      const p = proposals.find((entry) => entry.id === id);
      if (!p) { location.hash = 'pendientes'; return; }
      $('page-title').textContent = 'Propuesta de cambio';
      $('proposal-view').hidden = false;
      $('proposal-view').innerHTML = `${link('proposal-back','← Volver a pendientes','#pendientes')}<span class="chip warning">Pendiente · MOCK</span><h2 data-testid="proposal-title">${esc(p.title)}</h2><p>${esc(p.author)} · Material: ${esc(books.find((b) => b.id === p.book)?.title || 'Material nuevo')}</p><p>${esc(p.text)}</p><pre class="reading" data-testid="proposal-content">${esc(p.content)}</pre><p class="muted">Vista de propuesta ficticia para docentes y coordinación. No hay integración externa ni aprobación real en este prototipo.</p>`;
    } else if (page === 'nuevo') {
      $('page-title').textContent = 'Nuevo material';
      $('new-view').hidden = false;
    } else {
      $('home-view').hidden = false;
      $('page-title').textContent = page === 'pendientes' ? 'Pendientes de revisión' : page === 'catalogo' ? (isB ? 'Catálogo' : 'Libros') : (isB ? 'Tu próxima clase empieza aquí' : 'Panel');
      renderCatalog();
    }
    $('main-content').focus({preventScroll:true});
    if (page === 'catalogo') $('catalog-section').scrollIntoView();
    else if (page === 'pendientes') $('pending-section').scrollIntoView();
    else window.scrollTo(0, 0);
  }
  $('filters').addEventListener('submit', (event) => {
    event.preventDefault();
    applied = {course:$('course').value, subject:$('subject').value};
    renderCatalog();
  });
  $('role').addEventListener('change', () => announce(`Rol ${$('role').value}: las mismas propuestas siguen accesibles.`));
  ['copy-title','editor-text'].forEach((id) => $(id).addEventListener('input', () => {
    const d = getDraft(currentBook);
    d.title = $('copy-title').value;
    d.text = $('editor-text').value;
    updateEditorStatus();
  }));
  $('import-file').addEventListener('change', async () => {
    const file = $('import-file').files[0];
    const sequence = ++importSequence;
    const bookId = currentBook.id;
    if (!file) return;
    const reject = (message) => { $('import-status').textContent = message; $('import-file').value = ''; };
    if (!/\.(txt|md)$/i.test(file.name)) { reject('Archivo rechazado. Solo se admiten .txt o .md; el contenido no se ha modificado.'); return; }
    if (file.size > 1024 * 1024) { reject('Archivo rechazado: supera 1 MB. El contenido no se ha modificado.'); return; }
    try {
      const bytes = await file.arrayBuffer();
      if (sequence !== importSequence || currentBook.id !== bookId || $('editor-view').hidden) return;
      const text = new TextDecoder('utf-8', {fatal:true}).decode(bytes);
      if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(text)) { reject('Archivo rechazado: no parece texto válido. El contenido no se ha modificado.'); return; }
      $('import-status').textContent = 'Archivo leído localmente. Sin sustitución hasta confirmar.';
      showDialog('¿Sustituir el contenido de tu copia?', `«${file.name}» reemplazará todo el texto actual${text.length ? '' : ' por texto vacío'}. El título se mantiene. Cancelar conserva tu texto.`, () => {
        getDraft(currentBook).text = text;
        $('editor-text').value = text;
        $('import-status').textContent = 'Texto importado en memoria. Aún no se ha guardado ni enviado.';
        updateEditorStatus();
      }, 'Sustituir contenido');
      $('import-file').value = '';
    } catch (_) { reject('No se pudo leer como texto UTF-8. El contenido no se ha modificado.'); }
  });
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-action]');
    if (!target) return;
    const action = target.dataset.action;
    if (action === 'clear') {
      $('filters').reset(); applied = {course:'',subject:''}; renderCatalog();
    } else if (action === 'pdf') {
      showDialog('PDF no disponible en este mock', 'Esta acción es una demostración. No se genera, descarga ni imprime ningún PDF.');
    } else if (action === 'exit') {
      showDialog('Sesión ficticia', 'No existe una sesión real que cerrar. Puedes volver al selector con «Cambiar versión»; al salir perderás los cambios locales.');
    } else if (action === 'save' || action === 'review') {
      const d = getDraft(currentBook);
      if (!d.title.trim() || !d.text.trim()) {
        showDialog('Completa tu copia', 'Escribe un título y contenido antes de guardar o enviar a revisión.');
        return;
      }
      if (action === 'save') {
        d.saved = {title:d.title,text:d.text};
        updateEditorStatus();
      } else {
        showDialog('Enviar copia a revisión · SIMULADO', 'Se creará una propuesta ficticia con el texto actual, sin publicar ni guardar tu copia automáticamente. No se envía nada a un servidor.', () => {
          d.sent = {title:d.title,text:d.text};
          proposals.push({id:`propuesta-${proposals.length + 1}`, book:currentBook.id, title:d.title, text:'Envío simulado desde tu copia docente. Solo existe hasta recargar.', author:'Elena Martín', content:d.text});
          renderPending(); updateEditorStatus();
        }, 'Enviar · SIMULADO');
      }
    }
  });
  $('new-form').addEventListener('submit', (event) => {
    event.preventDefault();
    if (!$('new-title').value.trim()) { $('new-title').setCustomValidity('Escribe un título.'); $('new-title').reportValidity(); return; }
    currentBook = {id:`nuevo-${drafts.size + 1}`, title:$('new-title').value.trim(), course:$('new-course').value, subject:$('new-subject').value, summary:'Borrador personal de demostración.',tag:'Borrador',time:'Sin duración',body:''};
    location.hash = `editar/${currentBook.id}`;
  });
  $('new-title').addEventListener('input', () => $('new-title').setCustomValidity(''));
  window.addEventListener('hashchange', route);
  renderPending();
  route();
})();
