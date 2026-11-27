(function () {
  'use strict';

  /* ===================== DATA: 192 TEMPLATES / 16 CATEGORIES ===================== */
  const CATS = [
    { id: 'ecommerce', name: 'E-Commerce', icon: '🛍️', count: 18,
      blurb: 'mahsulotlar, savat, buyurtma va to\'lovlarni Telegram ichida boshqaradi.',
      cmds: ['/start', '/katalog', '/savat', '/buyurtma', '/tolov', '/chegirma', '/yetkazish', '/help'],
      names: ['Onlayn do\'kon', 'Mahsulot katalogi', 'Savat va buyurtma', 'To\'lov boti', 'Chegirma va kupon', 'Yetkazib berish kuzatuvchi', 'Ombor hisobi', 'Mijozni qaytarish', 'Sotuv analitikasi', 'Qaytarish va almashtirish', 'Pre-order bot', 'Flash sale bot', 'Mahsulot tavsiyachi', 'Narx solishtirish', 'Do\'kon administratori', 'Buyurtma qabul qiluvchi', 'Dropshipping bot', 'Elektronika do\'koni'] },
    { id: 'education', name: 'Ta\'lim', icon: '🎓', count: 14,
      blurb: 'darslar, testlar va o\'quv jarayonini qiziqarli tarzda tashkil qiladi.',
      cmds: ['/start', '/kurslar', '/dars', '/test', '/vazifa', '/jadval', '/help'],
      names: ['Kurs boti', 'Viktorina boti', 'Lug\'at o\'rgatuvchi', 'Dars jadvali', 'Uy vazifasi yordamchisi', 'Imtihon tayyorgarligi', 'Til o\'rganish boti', 'O\'quvchi kuzatuvchi', 'Video darslar kutubxonasi', 'Sertifikat beruvchi', 'Fan yordamchisi', 'Ota-ona bildirishnomasi', 'Matematika mashqlari', 'Motivatsiya boti'] },
    { id: 'content', name: 'Kontent', icon: '✍️', count: 12,
      blurb: 'post, skript va sarlavha g\'oyalarini tezda yaratib beradi.',
      cmds: ['/start', '/goya', '/post', '/skript', '/sarlavha', '/trend', '/help'],
      names: ['Kontent rejalashtiruvchi', 'Post g\'oyalari', 'Rasmlar kutubxonasi', 'Mem generator', 'Matn yozuvchi', 'Hikoya yaratuvchi', 'Podcast transkript', 'Video skript yozuvchi', 'Trend kuzatuvchi', 'Sarlavha generator', 'Kunlik iqtibos', 'So\'rovnoma boti'] },
    { id: 'utility', name: 'AI & Utility', icon: '🛠️', count: 14,
      blurb: 'kundalik vazifalarni AI bilan avtomatlashtiradi va hisoblaydi.',
      cmds: ['/start', '/tarjima', '/yoz', '/qisqa', '/hisobla', '/qidir', '/help'],
      names: ['AI yordamchi', 'Tarjimon bot', 'Matn qisqartiruvchi', 'Ma\'lumot qidiruvchi', 'AI yozuvchi', 'Tasvir generator', 'Narx hisoblagich', 'QR kod generator', 'PDF yordamchi', 'Eslatma va vazifalar', 'Ob-havo boti', 'Kurs kalkulyatori', 'AI maslahatchi', 'Avtomatik javob boti'] },
    { id: 'chatgpt', name: 'ChatGPT & AI', icon: '🤖', count: 10,
      blurb: 'sun\'iy intellekt bilan suhbat, tahlil va ijodiy ishlar qiladi.',
      cmds: ['/start', '/suhbat', '/prompt', '/tahlil', '/kod', '/goya', '/help'],
      names: ['ChatGPT bot', 'AI suhbatdosh', 'AI savol-javob', 'Prompt menejer', 'AI tahlilchi', 'G\'oya generator', 'AI intervyu', 'Kod yordamchisi', 'AI ta\'lim yordamchisi', 'AI yozish ustasi'] },
    { id: 'smm', name: 'SMM', icon: '📱', count: 16,
      blurb: 'ijtimoiy tarmoqlardagi kontent, obunachilar va reklamani boshqaradi.',
      cmds: ['/start', '/post', '/kanal', '/obunachi', '/analitika', '/reklama', '/help'],
      names: ['Instagram yordamchi', 'Kanal boshqaruvchi', 'Post nashr qiluvchi', 'Obunachi hisobi', 'Engagement boti', 'Reklama kuzatuvchi', 'Hashtag generator', 'Kontent takvimi', 'Story yaratuvchi', 'Obunachi oshirish', 'Kanal analitikasi', 'Moderatsiya boti', 'Giveaway boti', 'Izoh yig\'uvchi', 'DM marketing boti', 'SMM hisobot boti'] },
    { id: 'crypto', name: 'Crypto', icon: '₿', count: 12,
      blurb: 'kripto narxlari, portfel va savdo signallarini kuzatadi.',
      cmds: ['/start', '/narx', '/portfel', '/signal', '/kurs', '/yangilik', '/help'],
      names: ['Kripto narx kuzatuvchi', 'Portfel hisobi', 'Coin tavsiyachi', 'Trading signal bot', 'Airdrop kuzatuvchi', 'Blokchain kuzatuvchi', 'Kripto yangiliklar', 'Valyuta kursi boti', 'Staking kalkulyatori', 'NFT katalogi', 'Savdo hisobi', 'Kripto maslahatchi'] },
    { id: 'auto', name: 'Avtomobil', icon: '🚗', count: 10,
      blurb: 'avto e\'lonlar, narxlar va xizmatlarni qulay tarzda taqdim etadi.',
      cmds: ['/start', '/elon', '/narx', '/servis', '/qism', '/sugurta', '/help'],
      names: ['Avto e\'lon bot', 'Mashina baholash', 'Yo\'l qoidalari', 'Avtoservis yozuvchi', 'Yoqilg\'i hisobi', 'Avto sug\'urta', 'Haydovchi yordamchi', 'Avtoqismlar katalogi', 'Ijaraga berish boti', 'Avto yangiliklar'] },
    { id: 'travel', name: 'Turizm', icon: '✈️', count: 10,
      blurb: 'sayohatlar, tur paketlari va bron qilishni osonlashtiradi.',
      cmds: ['/start', '/turlar', '/mehmonxona', '/yonalish', '/viza', '/obhavo', '/help'],
      names: ['Sayyoh yordamchi', 'Tur paketlari', 'Mehmonxona band qilish', 'Yo\'nalish tavsiyachi', 'Aeroport ma\'lumoti', 'Sayohat kundaligi', 'Ekskursiya boti', 'Viza yordamchi', 'Ob-havo va sharoit', 'Sayohat eslatmalari'] },
    { id: 'insurance', name: 'Sug\'urta', icon: '🛡️', count: 8,
      blurb: 'polis hisobi, muddat va da\'volarni avtomatik boshqaradi.',
      cmds: ['/start', '/hisobla', '/polis', '/daivo', '/maslahat', '/help'],
      names: ['Sug\'urta hisoblagich', 'Polis muddati eslatmasi', 'Avto sug\'urta boti', 'Sog\'liq sug\'urtasi', 'Uy sug\'urtasi', 'Da\'vo yuborish', 'Sug\'urta maslahatchi', 'To\'lov jadvali'] },
    { id: 'realty', name: 'Ko\'chmas mulk', icon: '🏠', count: 10,
      blurb: 'uy-joy e\'lonlari, ijara va ipoteka hisoblarini taqdim etadi.',
      cmds: ['/start', '/elon', '/ijara', '/ipoteka', '/katalog', '/baho', '/help'],
      names: ['Uy sotish boti', 'Ijara e\'lonlari', 'Kvadrat hisoblagich', 'Ipoteka kalkulyatori', 'Mulk katalogi', 'Xaridor qidirish', 'E\'lon yaratuvchi', 'Hudud tavsiyachi', 'Mulk baholash', 'Mulk yangiliklari'] },
    { id: 'games', name: 'O\'yin', icon: '🎮', count: 10,
      blurb: 'quiz, turnir va mini o\'yinlar bilan foydalanuvchilarni jalb qiladi.',
      cmds: ['/start', '/och', '/quiz', '/ball', '/turnir', '/help'],
      names: ['Quiz bot', 'O\'yin markazi', 'Lotereya boti', 'Kartochka o\'yini', 'Boshqotirma boti', 'Turnir tashkilotchisi', 'Ballar hisobi', 'Mini o\'yinlar', 'O\'yin tavsiyachi', 'Reyting jadvali'] },
    { id: 'business', name: 'Biznes', icon: '💼', count: 16,
      blurb: 'mijozlar, vazifalar va hisoblarni yagona tizimda boshqaradi.',
      cmds: ['/start', '/crm', '/hisob', '/vazifa', '/mijoz', '/kpi', '/help'],
      names: ['Biznes yordamchi', 'CRM mini bot', 'Hisob-faktura boti', 'Jamoa vazifalari', 'Mijoz bazasi', 'Sotuv voronkasi', 'KPI hisobi', 'Yig\'ilish eslatmasi', 'Xodimlar ishi', 'Byudjet kuzatuvchi', 'Tender e\'lonlari', 'Hamkorlik taklifi', 'Biznes reja yaratuvchi', 'Bo\'lim hisoboti', 'Jarayon avtomatizatsiyasi', 'Biznes maslahatchi'] },
    { id: 'health', name: 'Sog\'liq', icon: '💚', count: 10,
      blurb: 'sog\'lom odatlar, eslatmalar va mashqlarni kuzatishga yordam beradi.',
      cmds: ['/start', '/eslatma', '/suvi', '/kilo', '/workout', '/diet', '/help'],
      names: ['Sog\'liq yordamchi', 'Dori eslatmasi', 'Suv ichish hisobi', 'Kilo kuzatuvchi', 'Workout rejasi', 'Meditatsiya boti', 'Semptom tekshiruvchi', 'Diyet tavsiyachi', 'Uyqu kundaligi', 'Shifokor yozuvchi'] },
    { id: 'services', name: 'Xizmatlar', icon: '🧰', count: 10,
      blurb: 'xizmat buyurtmalari, navbat va ustalarni boshqaradi.',
      cmds: ['/start', '/buyurtma', '/navbat', '/usta', '/kuryer', '/narx', '/help'],
      names: ['Usta yordamchi', 'Navbat boshqaruvchi', 'Xizmat buyurtmasi', 'Usta qidiruvchi', 'Tozalash xizmati', 'Ta\'mirlash yozuvchi', 'Kuryer chaqirish', 'Salon band qilish', 'Narx hisobi', 'Mijoz fikri'] },
    { id: 'tools', name: 'Foydali vositalar', icon: '🧮', count: 12,
      blurb: 'hisob-kitob, eslatma va kundalik ishlar uchun qulay vositalar.',
      cmds: ['/start', '/qr', '/hisob', '/eslatma', '/fayl', '/format', '/help'],
      names: ['QR va Barcode', 'Hisob-kitoblar', 'Vaqt hisoblagich', 'Taqvim eslatma', 'Fayl yordamchi', 'Matn formatlovchi', 'Rang tanlash', 'Kod formatlovchi', 'Til o\'rgatish', 'Eslatmalar', 'Telefon kitobi', 'Umumiy yordamchi'] }
  ];

  const VARIANTS = ['', ' Pro', ' Mini', ' 24/7', ' Master', ' Plus', ' Lite', ' Max', ' Business', ' Smart', ' Premium', ' Basic', ' Club', ' Expert', ' Go', ' Box', ' Hub', ' X'];
  const FEATURES = [
    'Tayyor menyu va tugmalar', 'O\'zbek tilida interfeys', '24/7 avtomatik ishlash',
    'Admin paneli', 'Statistika va hisobot', 'To\'lov integratsiyasi',
    'Cheksiz foydalanuvchi', 'AI bilan boshqaruv', 'Sozlanadigan matnlar', 'Tezkor ishga tushirish'
  ];

  const TEMPLATES = [];
  CATS.forEach(function (cat) {
    for (var i = 0; i < cat.count; i++) {
      var base = cat.names[i % cat.names.length];
      var variant = VARIANTS[Math.floor(i / cat.names.length) % VARIANTS.length];
      var n = i + 1;
      TEMPLATES.push({
        id: cat.id + '-' + n,
        name: base + variant,
        cat: cat.name,
        catId: cat.id,
        icon: cat.icon,
        desc: base + ' — ' + cat.blurb,
        commands: cat.cmds,
        features: [FEATURES[i % FEATURES.length], FEATURES[(i + 3) % FEATURES.length], FEATURES[(i + 6) % FEATURES.length], FEATURES[(i + 8) % FEATURES.length]]
      });
    }
  });

  /* ===================== THEME ===================== */
  var root = document.documentElement;
  var themeBtn = document.getElementById('themeToggle');
  try {
    var saved = localStorage.getItem('venox-theme');
    if (saved === 'light' || saved === 'dark') root.setAttribute('data-theme', saved);
  } catch (e) { /* storage unavailable */ }
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('venox-theme', next); } catch (e) { /* ignore */ }
    });
  }

  /* ===================== MOBILE MENU ===================== */
  var menuBtn = document.getElementById('menuToggle');
  var nav = document.getElementById('nav');
  function closeMenu() {
    if (!nav || !menuBtn) return;
    nav.classList.remove('is-open');
    menuBtn.setAttribute('aria-expanded', 'false');
    menuBtn.setAttribute('aria-label', 'Menyuni ochish');
  }
  if (menuBtn && nav) {
    menuBtn.addEventListener('click', function () {
      var open = nav.classList.toggle('is-open');
      menuBtn.setAttribute('aria-expanded', String(open));
      menuBtn.setAttribute('aria-label', open ? 'Menyuni yopish' : 'Menyuni ochish');
    });
    nav.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', closeMenu); });
    document.addEventListener('click', function (e) {
      if (!nav.contains(e.target) && !menuBtn.contains(e.target)) closeMenu();
    });
  }

  /* ===================== SCROLL REVEAL + COUNTERS ===================== */
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
  }

  function animateCount(el) {
    var target = parseInt(el.getAttribute('data-count'), 10);
    var start = performance.now();
    var dur = 1400;
    function tick(now) {
      var p = Math.min((now - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  var counters = document.querySelectorAll('[data-count]');
  if ('IntersectionObserver' in window && counters.length) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { animateCount(entry.target); cio.unobserve(entry.target); }
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { cio.observe(el); });
  } else {
    counters.forEach(function (el) { el.textContent = el.getAttribute('data-count'); });
  }

  /* ===================== CATALOG ===================== */
  var grid = document.getElementById('templateGrid');
  var chipsWrap = document.getElementById('categoryChips');
  var searchInput = document.getElementById('searchInput');
  var clearSearch = document.getElementById('clearSearch');
  var countEl = document.getElementById('resultCount');
  var moreWrap = document.getElementById('moreWrap');
  var loadMore = document.getElementById('loadMore');
  var emptyState = document.getElementById('emptyState');
  var pageSize = 16;
  var state = { cat: 'all', query: '', visible: pageSize };

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }

  function buildChips() {
    var html = '<button class="chip is-active" type="button" data-cat="all">Hammasi · 192</button>';
    CATS.forEach(function (cat) { html += '<button class="chip" type="button" data-cat="' + cat.id + '">' + esc(cat.icon + ' ' + cat.name) + '</button>'; });
    chipsWrap.innerHTML = html;
    chipsWrap.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        state.cat = chip.getAttribute('data-cat');
        state.visible = pageSize;
        chipsWrap.querySelectorAll('.chip').forEach(function (c) { c.classList.toggle('is-active', c === chip); });
        render();
      });
    });
  }

  function filtered() {
    var q = state.query.trim().toLowerCase();
    return TEMPLATES.filter(function (t) {
      var catOk = state.cat === 'all' || t.catId === state.cat;
      var qOk = !q || (t.name + ' ' + t.cat + ' ' + t.desc).toLowerCase().indexOf(q) !== -1;
      return catOk && qOk;
    });
  }

  function render() {
    var list = filtered();
    countEl.textContent = list.length + (list.length === 1 ? ' ta shablon' : ' ta shablon');
    if (!list.length) {
      grid.innerHTML = '';
      emptyState.hidden = false;
      moreWrap.hidden = true;
      return;
    }
    emptyState.hidden = true;
    var slice = list.slice(0, state.visible);
    grid.innerHTML = slice.map(function (t) {
      return '<button class="template-card" type="button" data-id="' + t.id + '">' +
        '<div class="template-card__top"><span class="template-card__icon">' + esc(t.icon) + '</span>' +
        '<span class="template-card__cat">' + esc(t.cat) + '</span></div>' +
        '<h3>' + esc(t.name) + '</h3><p>' + esc(t.desc) + '</p>' +
        '<div class="template-card__foot"><span>' + t.commands.length + ' ta buyruq</span><span>Ko\'rish →</span></div></button>';
    }).join('');
    grid.querySelectorAll('.template-card').forEach(function (card) {
      card.addEventListener('click', function () {
        var tpl = TEMPLATES.find(function (t) { return t.id === card.getAttribute('data-id'); });
        if (tpl) openModal(tpl);
      });
    });
    moreWrap.hidden = list.length <= state.visible;
    loadMore.textContent = 'Yana ko\'rsatish ↓ (' + Math.min(pageSize, list.length - state.visible) + ')';
  }

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      state.query = searchInput.value;
      state.visible = pageSize;
      clearSearch.hidden = !searchInput.value;
      render();
    });
    clearSearch.addEventListener('click', function () {
      searchInput.value = '';
      state.query = '';
      state.visible = pageSize;
      clearSearch.hidden = true;
      render();
      searchInput.focus();
    });
  }
  if (loadMore) loadMore.addEventListener('click', function () { state.visible += pageSize; render(); });
  buildChips();
  render();

  /* ===================== MODAL ===================== */
  var modal = document.getElementById('modal');
  var modalBody = document.getElementById('modalBody');
  var lastFocused = null;
  function openModal(t) {
    lastFocused = document.activeElement;
    modalBody.innerHTML =
      '<div class="modal__head"><span class="modal__icon">' + esc(t.icon) + '</span><div>' +
      '<span class="modal__cat">' + esc(t.cat) + ' · Shablon</span><h3 id="modalTitle">' + esc(t.name) + '</h3></div></div>' +
      '<p class="modal__desc">' + esc(t.desc) + '</p>' +
      '<div class="modal__label">Buyruqlar</div><div class="modal__commands">' +
      t.commands.map(function (c) { return '<span class="cmd">' + esc(c) + '</span>'; }).join('') + '</div>' +
      '<div class="modal__label">Imkoniyatlar</div><ul class="modal__features">' +
      t.features.map(function (f) { return '<li>' + esc(f) + '</li>'; }).join('') + '</ul>' +
      '<div class="modal__actions">' +
      '<a class="btn btn--primary" href="https://t.me/CodeMinnt_bot/venox" target="_blank" rel="noopener">Bu botni yaratish →</a>' +
      '<button class="btn btn--ghost" type="button" data-close>Yopish</button></div>';
    modal.hidden = false;
    document.body.classList.add('modal-open');
    modal.querySelectorAll('[data-close]').forEach(function (el) { el.addEventListener('click', closeModal); });
    var closeBtn = modal.querySelector('.modal__close');
    if (closeBtn) closeBtn.focus();
  }
  function closeModal() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }
  if (modal) {
    modal.querySelectorAll('[data-close]').forEach(function (el) { el.addEventListener('click', closeModal); });
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeModal(); closeMenu(); } });

  /* ===================== AI BUILDER ===================== */
  var ideaInput = document.getElementById('ideaInput');
  var generateBtn = document.getElementById('generateBtn');
  var resultBox = document.getElementById('builderResult');
  var RULES = [
    { test: /do.?kon|savdo|mahsulot|buyurtma|savat|tolov|shop|market|e-?commerce|dropship/i, cat: CATS[0] },
    { test: /talim|o.?quv|kurs|dars|test|viktorina|imtihon|til|lug.?at|edu|study/i, cat: CATS[1] },
    { test: /kontent|post|skript|sarlavha|blog|trend|yozuv|content/i, cat: CATS[2] },
    { test: /kripto|coin|bitcoin|trading|blokchain|portfel|kurs|valyuta|crypto/i, cat: CATS[6] },
    { test: /ai|sun.?iy|intellekt|chatgpt|gpt|prompt|yordamchi|suhbat|bot yarat/i, cat: CATS[4] },
    { test: /smm|instagram|kanal|obunachi|reklama|hashtag|ijtimoiy/i, cat: CATS[5] },
    { test: /avto|mashina|haydovchi|yo.?l|servis|avtoservis/i, cat: CATS[7] },
    { test: /turizm|sayohat|mehmonxona|viza|ekskursiya|travel/i, cat: CATS[8] },
    { test: /sug.?urta|polis|da.?vo|insurance/i, cat: CATS[9] },
    { test: /uy|kvartira|mulk|ijara|ipoteka|ko.?chmas|realt/i, cat: CATS[10] },
    { test: /oyin|quiz|lotereya|turnir|ball|game/i, cat: CATS[11] },
    { test: /biznes|crm|mijoz|hisob|vazifa|jamoa|kpi|byudjet|business/i, cat: CATS[12] },
    { test: /sog.?liq|dori|kilo|suv|workout|meditatsiya|diet|health/i, cat: CATS[13] },
    { test: /xizmat|usta|navbat|kuryer|salon|tozalash|service/i, cat: CATS[14] },
    { test: /hisob|qr|tarjima|eslatma|fayl|kalkulyator|utility|vosita/i, cat: CATS[3] }
  ];

  function buildBot(text) {
    var lower = text.toLowerCase();
    var cat = CATS[3];
    for (var i = 0; i < RULES.length; i++) { if (RULES[i].test.test(lower)) { cat = RULES[i].cat; break; } }
    var cleaned = text.replace(/\s+/g, ' ').trim()
      .replace(/^(men|biz|assalomu alaykum|salom)[,!]?\s*/i, '')
      .replace(/(bot yaratmoqchiman|bot yaratishni xohlayman|bot kerak|yaratmoqchiman|uchun bot|boti uchun|kerak|haqida|ixtiyoriy)/gi, ' ')
      .replace(/\bboti\b/gi, ' ')
      .replace(/\bbot\b/gi, ' ')
      .replace(/\s+/g, ' ').trim();
    var words = cleaned.split(' ').filter(function (w) { return w.length > 1; }).slice(0, 3).join(' ');
    var name = (words ? words.charAt(0).toUpperCase() + words.slice(1) : cat.name) + ' Bot';
    if (name.length > 34) name = name.slice(0, 32).trim() + '…';
    var cmds = cat.cmds.slice(0, 6);
    if (cmds.indexOf('/start') === -1) cmds.unshift('/start');
    if (cmds.indexOf('/help') === -1) cmds.push('/help');
    var structure = [
      'Boshlang\'ich menyu va xush kelibsiz xabari',
      'Asosiy bo\'lim: ' + cat.name.toLowerCase() + ' funksiyalari',
      'Har bir buyruq uchun alohida handler',
      'Foydalanuvchi ma\'lumotlarini saqlash',
      'Admin paneli va statistika',
      'To\'lov / obuna oqimi (ixtiyoriy)'
    ];
    return { name: name, cat: cat, cmds: cmds, structure: structure };
  }

  function generate() {
    var text = ideaInput ? ideaInput.value.trim() : '';
    if (!text) {
      if (ideaInput) ideaInput.focus();
      if (resultBox) resultBox.innerHTML = '<div class="builder__placeholder"><span>✏️</span><p>Avval g\'oyangizni yozing</p><small>Chap tomondagi maydonga bot haqida yozib, qayta urining.</small></div>';
      return;
    }
    var b = buildBot(text);
    var html = '<div class="build-result">' +
      '<div class="build-result__head"><span class="build-result__icon">' + esc(b.cat.icon) + '</span><div>' +
      '<h4>' + esc(b.name) + '</h4><span>' + esc(b.cat.name) + ' · Avtomatik yaratildi</span></div>' +
      '<span class="build-result__badge">TAYYOR ✓</span></div>' +
      '<div class="build-result__section"><strong>Buyruqlar ro\'yxati</strong><div class="cmd-list">' +
      b.cmds.map(function (c) { return '<span class="cmd">' + esc(c) + '</span>'; }).join('') + '</div></div>' +
      '<div class="build-result__section"><strong>Tuzilma</strong><ul class="structure-list">' +
      b.structure.map(function (s, i) { return '<li><b>' + (i + 1) + '.</b><span>' + esc(s) + '</span></li>'; }).join('') + '</ul></div>' +
      '<div class="build-result__section"><strong>Tavsiya</strong><p class="build-result__desc">' +
      esc(b.cat.blurb.charAt(0).toUpperCase() + b.cat.blurb.slice(1)) + ' Pul ishlash uchun obuna, reklama yoki premium funksiyalarni qo\'shing.</p></div>' +
      '<div class="build-result__cta"><a class="btn btn--primary" href="https://t.me/CodeMinnt_bot/venox" target="_blank" rel="noopener">Bu botni yaratish →</a>' +
      '<button class="btn btn--ghost" type="button" id="copyStructure">Tuzilmani nusxalash</button></div></div>';
    resultBox.innerHTML = html;
    var cbtn = document.getElementById('copyStructure');
    if (cbtn) cbtn.addEventListener('click', function () {
      var plain = b.name + '\nToifa: ' + b.cat.name + '\nBuyruqlar: ' + b.cmds.join(', ') + '\nTuzilma:\n' + b.structure.map(function (s, i) { return (i + 1) + '. ' + s; }).join('\n');
      copyText(plain);
      cbtn.textContent = 'Nusxalandi ✓';
      setTimeout(function () { if (cbtn.parentNode) cbtn.textContent = 'Tuzilmani nusxalash'; }, 1800);
    });
  }
  if (generateBtn) generateBtn.addEventListener('click', generate);
  document.querySelectorAll('.example-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      if (ideaInput) { ideaInput.value = chip.textContent; ideaInput.focus(); }
      generate();
    });
  });

  /* ===================== COPY CARD ===================== */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); });
    } else { fallbackCopy(text); }
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
  }
  var copyBtn = document.getElementById('copyCard');
  if (copyBtn) {
    copyBtn.addEventListener('click', function () {
      var num = document.getElementById('cardNumber').textContent.trim();
      copyText(num);
      var label = document.getElementById('copyLabel');
      label.textContent = 'Nusxalandi ✓';
      setTimeout(function () { label.textContent = 'Karta raqamini nusxalash'; }, 2000);
    });
  }
})();
