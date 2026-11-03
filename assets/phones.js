
(function(){
  "use strict";
  var doc = document;
  function $(id){ return doc.getElementById(id); }
  function all(sel, scope){ return Array.prototype.slice.call((scope || doc).querySelectorAll(sel)); }
  function make(tag, cls, text){ var n = doc.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; }

  /* reveal on scroll */
  var items = all(".reveal");
  if("IntersectionObserver" in window){
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ en.target.classList.toggle("reveal-visible", en.isIntersecting); });
    }, {threshold:0.1, rootMargin:"0px 0px -6% 0px"});
    items.forEach(function(el, i){ el.style.setProperty("--rd", Math.min((i % 6) * 45, 225) + "ms"); io.observe(el); });
    window.requestAnimationFrame(function(){
      items.forEach(function(el){ var r = el.getBoundingClientRect(); if(r.top < window.innerHeight * 0.92 && r.bottom > 0) el.classList.add("reveal-visible"); });
    });
  }else{ document.documentElement.classList.remove("js"); }
  window.__clickdyReady = true;

  var yr = $("year"); if(yr) yr.textContent = new Date().getFullYear();

  /* desktop dropdowns */
  var drops = all("[data-dropdown]");
  function closeDrops(except){
    drops.forEach(function(d){ if(d === except) return; d.classList.remove("open"); d.querySelector(".nav-drop-btn").setAttribute("aria-expanded", "false"); });
  }
  drops.forEach(function(d){
    var b = d.querySelector(".nav-drop-btn");
    b.addEventListener("click", function(ev){
      ev.stopPropagation();
      var open = !d.classList.contains("open");
      closeDrops(d); d.classList.toggle("open", open); b.setAttribute("aria-expanded", String(open)); closeAllSearch();
    });
    all("a", d).forEach(function(a){ a.addEventListener("click", function(){ closeDrops(); }); });
  });

  /* mobile drawer */
  var toggle = $("menuToggle"), panel = $("mobilePanel"), back = $("menuBackdrop");
  var I_MENU = '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  var I_CLOSE = '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
  function setMenu(open){
    panel.classList.toggle("open", open); back.classList.toggle("open", open); doc.body.classList.toggle("mobile-menu-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    toggle.innerHTML = open ? I_CLOSE : I_MENU;
  }
  toggle.addEventListener("click", function(ev){ ev.stopPropagation(); setMenu(!panel.classList.contains("open")); });
  back.addEventListener("click", function(){ setMenu(false); });
  all("a", panel).forEach(function(a){ a.addEventListener("click", function(){ setMenu(false); }); });
  all(".mobile-drop-btn", panel).forEach(function(btn){
    var target = $(btn.getAttribute("aria-controls")), mark = btn.querySelector("span");
    btn.addEventListener("click", function(){
      var show = target.hasAttribute("hidden");
      target.toggleAttribute("hidden", !show); btn.setAttribute("aria-expanded", String(show)); mark.textContent = show ? "\u2212" : "\uFF0B";
    });
  });
  window.addEventListener("resize", function(){ if(window.innerWidth > 820 && panel.classList.contains("open")) setMenu(false); });

  /* article search (desktop header box + mobile box on the blog home) */
  var index = null, loading = false, waiting = [], searches = [];
  function loadIndex(cb){
    if(index){ cb(); return; }
    waiting.push(cb);
    if(loading) return;
    loading = true;
    fetch("/phones/search.json").then(function(r){ return r.json(); }).then(function(j){ index = j; })
      .catch(function(){ index = []; })
      .then(function(){ loading = false; var w = waiting; waiting = []; w.forEach(function(f){ f(); }); });
  }
  var STOP = {}; "a an the of to in on for and or is are new with from by at as it its".split(" ").forEach(function(w){ STOP[w] = 1; });
  function words(t){ return String(t).toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
  function hit(list, t){ return list.some(function(w){ return w.indexOf(t) === 0; }); }
  function find(q, limit){
    var tokens = words(q).filter(function(t){ return !STOP[t]; });
    if(!tokens.length) return [];
    var out = [];
    index.forEach(function(p, i){
      var tw = words(p.t), cw = words(p.c), ew = words(p.e), score = 0, hits = 0;
      tokens.forEach(function(t){
        if(hit(tw, t)){ score += 10; hits++; } else if(hit(cw, t)){ score += 5; hits++; } else if(hit(ew, t)){ score += 2; hits++; }
      });
      if(hits === tokens.length || (tokens.length > 2 && hits >= tokens.length - 1)) out.push({p:p, s:score + hits * 3, i:i});
    });
    out.sort(function(a, b){ return b.s - a.s || a.i - b.i; });
    return out.slice(0, limit).map(function(x){ return x.p; });
  }
  function closeAllSearch(){ searches.forEach(function(s){ s.close(); }); }
  function bindSearch(inputId, resultsId){
    var input = $(inputId), res = $(resultsId), skip = false;
    if(!input || !res) return;
    function close(){ res.classList.remove("open"); }
    function render(){
      var q = input.value.trim();
      res.textContent = "";
      if(!q){ close(); return; }
      loadIndex(function(){
        if(input.value.trim() !== q) return;
        var m = find(q, 6);
        res.textContent = "";
        if(!m.length){
          var empty = make("div", "nav-no-result", "No articles found for ");
          empty.appendChild(make("strong", "", q)); res.appendChild(empty);
        }else{
          m.forEach(function(p){
            var a = make("a", "nav-result"); a.href = p.u;
            var c = make("span", "nav-result-copy");
            c.appendChild(make("strong", "", p.t)); c.appendChild(make("small", "", p.c + " \u00B7 " + p.d));
            a.appendChild(make("span", "nav-result-icon", "\u2197")); a.appendChild(c); res.appendChild(a);
          });
        }
        res.classList.add("open");
      });
    }
    input.addEventListener("input", render);
    input.addEventListener("focus", function(){ if(skip){ skip = false; return; } if(input.value.trim()) render(); else loadIndex(function(){}); });
    input.addEventListener("keydown", function(ev){
      var first = res.querySelector(".nav-result");
      if(ev.key === "Enter" && first){ ev.preventDefault(); window.location.href = first.href; }
      else if(ev.key === "ArrowDown" && first){ ev.preventDefault(); first.focus(); }
      else if(ev.key === "Escape"){ close(); input.blur(); }
    });
    res.addEventListener("keydown", function(ev){
      var list = all(".nav-result", res), i = list.indexOf(doc.activeElement);
      if(ev.key === "ArrowDown"){ ev.preventDefault(); if(i < list.length - 1) list[i + 1].focus(); }
      else if(ev.key === "ArrowUp"){ ev.preventDefault(); if(i > 0) list[i - 1].focus(); else { skip = true; input.focus(); } }
      else if(ev.key === "Escape"){ close(); skip = true; input.focus(); }
    });
    searches.push({close:close, root:input.closest(".nav-search-wrap, .hero-search")});
  }
  bindSearch("navSearch", "navSearchResults");
  bindSearch("heroSearch", "heroSearchResults");

  doc.addEventListener("click", function(ev){
    if(!ev.target.closest(".nav-drop")) closeDrops();
    searches.forEach(function(s){ if(!s.root || !s.root.contains(ev.target)) s.close(); });
  });
  doc.addEventListener("keydown", function(ev){
    if(ev.key !== "Escape") return;
    closeDrops();
    if(panel.classList.contains("open")){ setMenu(false); toggle.focus(); }
  });

  /* copy link */
  var toast = $("toast"), tt;
  function say(msg){ if(!toast) return; toast.textContent = msg; toast.classList.add("show"); clearTimeout(tt); tt = setTimeout(function(){ toast.classList.remove("show"); }, 2200); }
  all("[data-copy]").forEach(function(b){
    b.addEventListener("click", function(){
      var url = b.getAttribute("data-copy");
      if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(url).then(function(){ say("Link copied"); }, function(){ window.prompt("Copy this link:", url); }); }
      else{ window.prompt("Copy this link:", url); }
    });
  });
})();


/* ===================== Clickdy Phones ===================== */
(function(){
  "use strict";
  var doc = document;
  function $(id){ return doc.getElementById(id); }
  function all(s, c){ return Array.prototype.slice.call((c || doc).querySelectorAll(s)); }
  function make(tag, cls, text){ var n = doc.createElement(tag); if(cls) n.className = cls; if(text != null) n.textContent = text; return n; }
  function num(v){ return (v === null || v === undefined || v === "") ? null : +v; }

  /* gallery */
  var gm = $("gMain");
  all(".g-thumb").forEach(function(b){
    b.addEventListener("click", function(){
      var img = gm.querySelector("img"); if(img){ img.src = b.getAttribute("data-full"); img.alt = b.getAttribute("data-alt") || ""; }
      all(".g-thumb").forEach(function(x){ x.classList.toggle("active", x === b); });
    });
  });
  /* sub navigation highlight */
  var sn = all(".subnav a");
  if(sn.length && "IntersectionObserver" in window){
    var map = {}; sn.forEach(function(a){ map[a.getAttribute("href").slice(1)] = a; });
    var io = new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting){ sn.forEach(function(a){ a.classList.toggle("on", a === map[e.target.id]); }); } }); }, {rootMargin:"-30% 0px -60% 0px"});
    Object.keys(map).forEach(function(id){ var el = $(id); if(el) io.observe(el); });
  }

  var dataP = null;
  function loadData(){ if(!dataP) dataP = fetch("/phones/data.json").then(function(r){ return r.json(); }); return dataP; }
  function money(p){ var o = []; if(p.p) o.push("$" + p.p.toLocaleString("en-US")); if(p.pk) o.push("Rs " + p.pk.toLocaleString("en-US")); return o.join(" / "); }
  function scoreCls(s){ return s >= 85 ? "s-hi" : s >= 70 ? "s-mid" : "s-lo"; }
  function cardEl(p){
    var a = make("a", "ph-card"); a.href = "/phones/" + p.s + "/";
    var im = make("div", "ph-img");
    if(p.i){ var img = make("img"); img.src = p.i; img.alt = p.b + " " + p.n; img.loading = "lazy"; img.width = 200; img.height = 250; im.appendChild(img); }
    else{ var ph = make("div", "ph-ph"); ph.innerHTML = '<svg viewBox="0 0 60 110" fill="none" stroke="#5db7ff" stroke-width="3"><rect x="4" y="4" width="52" height="102" rx="10"/><circle cx="30" cy="14" r="3"/></svg>'; im.appendChild(ph); }
    var info = make("div", "ph-info");
    info.appendChild(make("span", "ph-brand", p.b)); info.appendChild(make("h3", "", p.n));
    var k = p.k, bits = [];
    if(k.display_in) bits.push(k.display_in + "\u2033"); if(k.ram) bits.push(k.ram + " GB"); if(k.battery_mah) bits.push(k.battery_mah + " mAh");
    info.appendChild(make("p", "ph-meta", bits.join(" \u00B7 ")));
    var foot = make("div", "ph-foot");
    if(p.sc != null){ foot.appendChild(make("span", "score-pill " + scoreCls(p.sc), String(p.sc))); } else foot.appendChild(make("span"));
    foot.appendChild(make("span", "ph-price", money(p) ? money(p).split(" / ")[0] : ""));
    info.appendChild(foot); a.appendChild(im); a.appendChild(info);
    return a;
  }

  /* ---------------- finder ---------------- */
  var app = $("finderApp");
  if(app){
    var F = {q:"", brand:"", price:0, ram:0, sto:0, bat:0, hz:0, size:"", mp:0, year:0, g5:0, nfc:0, wl:0, ip:0, sort:"score"};
    var NUM = {price:1, ram:1, sto:1, bat:1, hz:1, mp:1, year:1, g5:1, nfc:1, wl:1, ip:1};
    var shown = 24, list = [];
    var els = {};
    all("[data-f]", app).forEach(function(el){ els[el.getAttribute("data-f")] = el; });
    function readURL(){
      var q = new URLSearchParams(location.search);
      Object.keys(F).forEach(function(k){ if(q.has(k)) F[k] = NUM[k] ? +q.get(k) : q.get(k); });
    }
    function writeURL(){
      var q = new URLSearchParams();
      Object.keys(F).forEach(function(k){ if(F[k] && !(k === "sort" && F[k] === "score")) q.set(k, F[k]); });
      history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q.toString() : ""));
    }
    function syncUI(){
      Object.keys(els).forEach(function(k){ var el = els[k]; if(el.type === "checkbox") el.checked = !!F[k]; else el.value = F[k] || (el.tagName === "SELECT" && !NUM[k] && k !== "sort" ? "" : (F[k] || "")); });
    }
    function pass(p){
      var k = p.k;
      if(F.q){ var s = (p.b + " " + p.n).toLowerCase(); if(F.q.toLowerCase().split(/\s+/).some(function(t){ return s.indexOf(t) < 0; })) return false; }
      if(F.brand && p.bs !== F.brand) return false;
      if(F.price && !(p.p != null && p.p <= F.price)) return false;
      if(F.ram && !(k.ram >= F.ram)) return false;
      if(F.sto && !(k.sto >= F.sto)) return false;
      if(F.bat && !(k.battery_mah >= F.bat)) return false;
      if(F.hz && !(k.refresh_hz >= F.hz)) return false;
      if(F.size === "compact" && !(k.display_in && k.display_in <= 6.3)) return false;
      if(F.size === "standard" && !(k.display_in > 6.3 && k.display_in < 6.7)) return false;
      if(F.size === "large" && !(k.display_in >= 6.7)) return false;
      if(F.mp && !(k.main_mp >= F.mp)) return false;
      if(F.year && p.y !== F.year) return false;
      if(F.g5 && !k.five_g) return false;
      if(F.nfc && !k.nfc) return false;
      if(F.wl && !(k.wireless_w > 0)) return false;
      if(F.ip && !/ip6[78]/i.test(k.ip || "")) return false;
      return true;
    }
    var SORT = {
      score: function(a, b){ return (b.sc || 0) - (a.sc || 0); },
      new: function(a, b){ return (b.d || "").localeCompare(a.d || ""); },
      pricelow: function(a, b){ return (a.p == null ? 1e9 : a.p) - (b.p == null ? 1e9 : b.p); },
      pricehigh: function(a, b){ return (b.p || 0) - (a.p || 0); },
      battery: function(a, b){ return (b.k.battery_mah || 0) - (a.k.battery_mah || 0); },
      camera: function(a, b){ return ((b.sub && b.sub[1]) || 0) - ((a.sub && a.sub[1]) || 0); }
    };
    var DATA = [];
    function render(){
      list = DATA.filter(pass).sort(SORT[F.sort] || SORT.score);
      var box = $("fResults"); box.textContent = "";
      $("fCount").innerHTML = "<b>" + list.length + "</b> phone" + (list.length === 1 ? "" : "s") + " found";
      if(!list.length){ box.appendChild(make("div", "empty-state", "No phones match these filters. Try removing one or two.")); $("fMore").hidden = true; return; }
      list.slice(0, shown).forEach(function(p){ box.appendChild(cardEl(p)); });
      $("fMore").hidden = list.length <= shown;
      writeURL();
    }
    function onChange(){
      Object.keys(els).forEach(function(k){ var el = els[k]; F[k] = el.type === "checkbox" ? (el.checked ? 1 : 0) : (NUM[k] ? +el.value || 0 : el.value); });
      shown = 24; render();
    }
    loadData().then(function(d){
      DATA = d;
      var bs = {}; d.forEach(function(p){ bs[p.bs] = p.b; });
      Object.keys(bs).sort(function(a, b){ return bs[a].localeCompare(bs[b]); }).forEach(function(k){ var o = make("option", "", bs[k]); o.value = k; els.brand.appendChild(o); });
      var ys = {}; d.forEach(function(p){ if(p.y) ys[p.y] = 1; });
      Object.keys(ys).sort().reverse().forEach(function(y){ var o = make("option", "", y); o.value = y; els.year.appendChild(o); });
      readURL(); syncUI(); render();
      Object.keys(els).forEach(function(k){ els[k].addEventListener(els[k].type === "search" ? "input" : "change", onChange); });
      $("fMoreBtn").addEventListener("click", function(){ shown += 24; render(); });
      $("fReset").addEventListener("click", function(){ Object.keys(F).forEach(function(k){ F[k] = (k === "sort") ? "score" : (NUM[k] ? 0 : ""); }); syncUI(); shown = 24; render(); });
    });
    if(window.matchMedia("(min-width:901px)").matches){ var fp = $("fPanel"); if(fp) fp.setAttribute("open", ""); }
  }

  /* ---------------- compare ---------------- */
  var cmp = $("compareApp");
  if(cmp){
    var picked = [], DB = [], bySlug = {};
    var ROWS = [
      ["Clickdy Score", function(p){ return p.sc; }, "high", null],
      ["Performance", function(p){ return p.sub && p.sub[0]; }, "high", null],
      ["Camera", function(p){ return p.sub && p.sub[1]; }, "high", null],
      ["Display score", function(p){ return p.sub && p.sub[2]; }, "high", null],
      ["Battery score", function(p){ return p.sub && p.sub[3]; }, "high", null],
      ["Price", function(p){ return p.p; }, "low", function(v, p){ return money(p); }],
      ["Release date", function(p){ return p.d; }, null, null],
      ["Display size", function(p){ return p.k.display_in; }, null, function(v){ return v + " inches"; }],
      ["Display type", function(p){ return p.k.display_type; }, null, null],
      ["Refresh rate", function(p){ return p.k.refresh_hz; }, "high", function(v){ return v + " Hz"; }],
      ["Peak brightness", function(p){ return p.k.peak_nits; }, "high", function(v){ return v + " nits"; }],
      ["Chipset", function(p){ return p.k.chipset; }, null, null],
      ["RAM (max)", function(p){ return p.k.ram; }, "high", function(v){ return v + " GB"; }],
      ["Storage (max)", function(p){ return p.k.sto; }, "high", function(v){ return v >= 1024 ? (v / 1024) + " TB" : v + " GB"; }],
      ["Main camera", function(p){ return p.k.main_mp; }, "high", function(v){ return v + " MP"; }],
      ["Battery", function(p){ return p.k.battery_mah; }, "high", function(v){ return v.toLocaleString("en-US") + " mAh"; }],
      ["Wired charging", function(p){ return p.k.wired_w; }, "high", function(v){ return v + " W"; }],
      ["Wireless charging", function(p){ return p.k.wireless_w == null ? null : p.k.wireless_w; }, "high", function(v){ return v ? v + " W" : "No"; }],
      ["Weight", function(p){ return p.k.weight_g; }, "low", function(v){ return v + " g"; }],
      ["Thickness", function(p){ return p.k.thickness_mm; }, "low", function(v){ return v + " mm"; }],
      ["5G", function(p){ return p.k.five_g == null ? null : (p.k.five_g ? "Yes" : "No"); }, null, null],
      ["NFC", function(p){ return p.k.nfc == null ? null : (p.k.nfc ? "Yes" : "No"); }, null, null],
      ["Water resistance", function(p){ return p.k.ip; }, null, null],
      ["Operating system", function(p){ return p.k.os; }, null, null]
    ];
    function save(){
      var q = picked.length ? "?p=" + picked.map(function(p){ return p.s; }).join(",") : "";
      history.replaceState(null, "", location.pathname + q);
    }
    function slots(){
      var box = $("cmpSlots"); box.textContent = "";
      picked.forEach(function(p, i){
        var s = make("div", "cmp-slot filled");
        var x = make("button", "x", "\u00D7"); x.type = "button"; x.setAttribute("aria-label", "Remove " + p.n);
        x.addEventListener("click", function(){ picked.splice(i, 1); redraw(); });
        if(p.i){ var im = make("img"); im.src = p.i; im.alt = ""; s.appendChild(im); }
        s.appendChild(make("strong", "", p.b + " " + p.n)); s.appendChild(x); box.appendChild(s);
      });
      if(picked.length < 4){
        var a = make("div", "cmp-slot"); a.appendChild(make("strong", "", picked.length ? "Add another phone" : "Add a phone to compare"));
        var w = make("div", "cmp-add"); var inp = make("input"); inp.type = "search"; inp.placeholder = "Search phones..."; inp.autocomplete = "off";
        var res = make("div", "cmp-results"); w.appendChild(inp); w.appendChild(res); a.appendChild(w); box.appendChild(a);
        inp.addEventListener("input", function(){
          var t = inp.value.trim().toLowerCase().split(/\s+/).filter(Boolean); res.textContent = "";
          if(!t.length){ res.classList.remove("open"); return; }
          var m = DB.filter(function(p){ var s = (p.b + " " + p.n).toLowerCase(); return t.every(function(x){ return s.indexOf(x) > -1; }) && !picked.some(function(q){ return q.s === p.s; }); }).slice(0, 8);
          m.forEach(function(p){ var b = make("button", "", p.b + " " + p.n); b.type = "button"; b.addEventListener("click", function(){ picked.push(p); redraw(); }); res.appendChild(b); });
          if(!m.length) res.appendChild(make("div", "cmp-empty", "No phones found"));
          res.classList.add("open");
        });
      }
    }
    function table(){
      var box = $("cmpTable"); box.textContent = "";
      if(picked.length < 2){ box.appendChild(make("div", "cmp-empty", "Pick at least two phones to see the comparison.")); return; }
      var wrap = make("div", "cmp-wrap"), t = make("table", "cmp-table"), head = make("tr");
      head.appendChild(make("th", "", "")); picked.forEach(function(p){ var td = make("td"); var a = make("a", "", p.b + " " + p.n); a.href = "/phones/" + p.s + "/"; a.style.fontWeight = "800"; td.appendChild(a); head.appendChild(td); }); t.appendChild(head);
      ROWS.forEach(function(r){
        var vals = picked.map(function(p){ var v; try{ v = r[1](p); }catch(e){ v = null; } return (v === undefined || v === "") ? null : v; });
        if(vals.every(function(v){ return v == null; })) return;
        var best = null;
        if(r[2] && vals.filter(function(v){ return v != null; }).length > 1){
          var nums = vals.filter(function(v){ return typeof v === "number"; });
          if(nums.length > 1){ best = r[2] === "high" ? Math.max.apply(null, nums) : Math.min.apply(null, nums); if(nums.every(function(n){ return n === best; })) best = null; }
        }
        var tr = make("tr"); tr.appendChild(make("th", "", r[0]));
        vals.forEach(function(v, i){
          var txt = v == null ? "\u2014" : (r[3] ? r[3](v, picked[i]) : String(v));
          var td = make("td", best != null && v === best ? "best" : "", txt); tr.appendChild(td);
        });
        t.appendChild(tr);
      });
      wrap.appendChild(t); box.appendChild(wrap);
    }
    function redraw(){ slots(); table(); save(); }
    loadData().then(function(d){
      DB = d; d.forEach(function(p){ bySlug[p.s] = p; });
      var q = new URLSearchParams(location.search).get("p");
      if(q) q.split(",").slice(0, 4).forEach(function(s){ if(bySlug[s]) picked.push(bySlug[s]); });
      redraw();
    });
    doc.addEventListener("click", function(e){ if(!e.target.closest(".cmp-add")) all(".cmp-results").forEach(function(r){ r.classList.remove("open"); }); });
  }
})();
