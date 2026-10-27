#!/usr/bin/env python3
"""
Clickdy Phones - builds the phone specifications section of the website.

Reads  phones-data/*.json  and writes:
  phones/index.html                    hub (search, latest, top scored, brands, best lists)
  phones/<slug>/index.html             one SEO page per phone
  phones/brand/<brand>/...             brand listings (paginated)   phones/brands/  all brands
  phones/finder/                       filter-and-find tool (runs in the browser)
  phones/compare/                      side-by-side compare (runs in the browser)
  phones/best/<list>/                  automatic "best phones" lists
  phones/data.json, phones/search.json small indexes used by the finder/compare/search
  assets/phones.css, assets/phones.js  shared styles/scripts (cached by the browser)
  sitemap-phones.xml
"""
import html
import json
import os
import re
import sys
import hashlib
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_blog as bb  # noqa: E402  (re-uses the site header/footer/template)
from common import ROOT, slugify, write_json  # noqa: E402
import phones_lib as pl  # noqa: E402

SITE = bb.SITE
SITE_NAME = bb.SITE_NAME
PHONES_DIR = os.path.join(ROOT, "phones")
ASSETS_DIR = os.path.join(ROOT, "assets")
MARK = bb.MARK
BRAND_PAGE_SIZE = int(bb.CFG.get("phones_per_page", 48))
E = html.escape

PHONE_CSS = r"""
/* ===================== Clickdy Phones ===================== */
.s-hi{--sc:#29d69a;--scbg:rgba(41,214,154,.14);--scbd:rgba(41,214,154,.36)}
.s-mid{--sc:#38a5ff;--scbg:rgba(56,165,255,.14);--scbd:rgba(56,165,255,.36)}
.s-lo{--sc:#ffad57;--scbg:rgba(255,173,87,.14);--scbd:rgba(255,173,87,.36)}
.score-pill{min-width:40px;height:28px;padding:0 10px;border-radius:999px;display:inline-grid;place-items:center;font-size:12.5px;font-weight:800;color:var(--sc);background:var(--scbg);border:1px solid var(--scbd)}
.ph-section{padding:34px 0}
.sec-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:22px}
.sec-head h2{font-family:"Plus Jakarta Sans",sans-serif;font-size:clamp(22px,2.6vw,30px);letter-spacing:-.04em;color:#f2f7ff}
.sec-head p{color:var(--soft);font-size:14px;margin-top:6px;line-height:1.6;max-width:560px}
.sec-link{color:#5cb5ff;font-weight:700;font-size:13.5px;white-space:nowrap}
.sec-link:hover{text-decoration:underline}
.ph-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.ph-card{position:relative;overflow:hidden;display:flex;flex-direction:column;background:linear-gradient(145deg,#0d1726,#0a1320);border:1px solid #1e324a;border-radius:20px;box-shadow:0 12px 30px rgba(0,0,0,.18);transition:transform .35s cubic-bezier(.2,.8,.2,1),border-color .35s ease,box-shadow .35s ease}
.ph-card:hover{transform:translateY(-7px);border-color:#315a7b;box-shadow:0 24px 55px rgba(0,0,0,.34)}
.js .ph-card.reveal{transition:opacity .7s var(--ease) var(--rd,0s),translate .7s var(--ease) var(--rd,0s),scale .7s var(--ease) var(--rd,0s),filter .7s ease var(--rd,0s),transform .35s cubic-bezier(.2,.8,.2,1),border-color .35s ease,box-shadow .35s ease}
.ph-img{aspect-ratio:4/5;display:grid;place-items:center;padding:16px;background:radial-gradient(circle at 50% 42%,rgba(56,165,255,.16),transparent 66%),#0b1421}
.ph-img img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;transition:transform .45s ease}
.ph-card:hover .ph-img img{transform:scale(1.07) rotate(-1deg)}
.ph-ph{width:46%;max-width:110px;opacity:.55}
.ph-info{padding:14px 16px 16px;display:flex;flex-direction:column;gap:5px;flex:1}
.ph-brand{font-size:10.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#64baff}
.ph-card h3{font-family:"Plus Jakarta Sans",sans-serif;font-size:15px;line-height:1.3;letter-spacing:-.02em;color:#f2f7ff}
.ph-meta{font-size:12px;color:#7f94ab;line-height:1.5}
.ph-foot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:auto;padding-top:9px}
.ph-price{font-size:12.5px;font-weight:700;color:#cfe0f2}
.ph-hub-hero{position:relative;padding:62px 0 18px;overflow:hidden}
.ph-hub-hero::before{content:"";position:absolute;width:520px;height:520px;background:radial-gradient(circle closest-side,rgba(38,174,255,.17),transparent);left:-220px;top:-230px;pointer-events:none;animation:orbFloat 8s ease-in-out infinite}
.ph-hub-hero::after{content:"";position:absolute;width:480px;height:480px;background:radial-gradient(circle closest-side,rgba(125,95,255,.16),transparent);right:-200px;top:-210px;pointer-events:none;animation:orbFloat 10s ease-in-out infinite reverse}
.ph-hub-hero .container{position:relative;z-index:1}
.hub-title{font-family:"Plus Jakarta Sans",sans-serif;font-size:clamp(34px,5vw,58px);line-height:1.05;letter-spacing:-.05em;margin:18px 0 14px;color:#f7fbff;text-wrap:balance}
.hub-title span{color:#63c7ff}
.hub-sub{max-width:640px;font-size:17px;line-height:1.7;color:var(--soft)}
.ph-hub-hero .hero-search{display:block;max-width:640px;margin-top:26px}
.ph-hub-hero .nav-search{height:56px;border-radius:18px;padding:0 18px;font-size:15px}
.ph-hub-hero .nav-search input{font-size:15px}
.quick-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.quick-card{display:flex;gap:14px;align-items:center;padding:20px;border-radius:18px;background:#0c1625;border:1px solid #20354d;transition:transform .3s ease,border-color .3s ease}
.quick-card:hover{transform:translateY(-5px);border-color:#315b7e}
.quick-card .qi{width:44px;height:44px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#123252,#1a2147);color:#72c4ff;font-size:19px;flex:0 0 auto}
.quick-card strong{display:block;font-family:"Plus Jakarta Sans",sans-serif;font-size:15px;color:#f2f7ff}
.quick-card span{display:block;font-size:12.5px;color:var(--soft);margin-top:3px;line-height:1.5}
.brand-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}
.brand-tile{padding:14px 16px;border-radius:14px;background:#0c1625;border:1px solid #20354d;font-weight:700;font-size:14px;color:#dbe7f4;transition:all .25s ease;display:flex;justify-content:space-between;gap:8px}
.brand-tile small{color:#71869f;font-weight:600;font-size:12px}
.brand-tile:hover{border-color:#3d6e96;color:#69bbff;transform:translateY(-3px)}
.list-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.list-tile{padding:16px 18px;border-radius:14px;background:#0c1625;border:1px solid #20354d;font-weight:700;font-size:14px;color:#dbe7f4;transition:all .25s ease}
.list-tile:hover{border-color:#3d6e96;color:#69bbff;transform:translateY(-3px)}
.empty-state{padding:60px 24px;text-align:center;border:1px dashed #27415c;border-radius:22px;color:var(--soft);line-height:1.7;background:rgba(14,24,39,.5)}
/* phone page */
.ph-wrap{padding:30px 0 10px}
.ph-hero{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.15fr);gap:38px;align-items:start}
.gallery{position:sticky;top:calc(var(--header-h) + 20px)}
.g-main{aspect-ratio:4/5;display:grid;place-items:center;padding:24px;border-radius:26px;background:radial-gradient(circle at 50% 40%,rgba(56,165,255,.2),transparent 66%),linear-gradient(145deg,#0d1726,#0a1320);border:1px solid #20354d;box-shadow:var(--shadow)}
.g-main img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;filter:drop-shadow(0 22px 30px rgba(0,0,0,.45))}
.g-main .ph-ph{width:34%;max-width:160px}
.g-thumbs{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.g-thumb{width:64px;height:76px;padding:6px;border-radius:14px;border:1px solid #20354d;background:#0c1625;display:grid;place-items:center;transition:border-color .2s ease}
.g-thumb img{max-width:100%;max-height:100%;object-fit:contain}
.g-thumb.active,.g-thumb:hover{border-color:#3d9ee1}
.g-credit{font-size:11.5px;color:#71869f;margin-top:10px;line-height:1.5}
.ph-title{font-family:"Plus Jakarta Sans",sans-serif;font-size:clamp(30px,4vw,46px);line-height:1.08;letter-spacing:-.05em;color:#f7fbff;margin:12px 0 8px}
.ph-status{font-size:13.5px;color:#8fa4bd;line-height:1.6}
.tag-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.tag-row .tag{display:inline-flex;padding:6px 11px;border-radius:999px;font-size:11.5px;font-weight:800;letter-spacing:.04em;background:rgba(125,107,255,.14);color:#a99aff;border:1px solid rgba(125,107,255,.3)}
.chip-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:20px}
.chip{padding:13px 14px;border-radius:15px;background:#0c1625;border:1px solid #20354d}
.chip small{display:block;font-size:10.5px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:#71869f}
.chip strong{display:block;font-size:14px;color:#eef6ff;margin-top:5px;line-height:1.35}
.score-box{display:grid;grid-template-columns:130px 1fr;gap:22px;align-items:center;margin-top:20px;padding:22px;border-radius:22px;background:linear-gradient(145deg,#0d1726,#0a1320);border:1px solid #20354d}
.ring{position:relative;width:118px;height:118px}
.ring svg{width:100%;height:100%;transform:rotate(-90deg)}
.ring .bg{stroke:#17263a}
.ring .fg{stroke:var(--sc);stroke-linecap:round}
.ring b{position:absolute;inset:0;display:grid;place-items:center;font-family:"Plus Jakarta Sans",sans-serif;font-size:34px;letter-spacing:-.04em;color:#f7fbff}
.ring b small{display:block;font-size:11px;font-weight:700;color:#7f94ab;letter-spacing:0;text-align:center;margin-top:-4px}
.bars{display:grid;gap:9px}
.bar{display:grid;grid-template-columns:96px 1fr 30px;gap:10px;align-items:center;font-size:12.5px;color:#a9b8cc}
.bar i{display:block;height:7px;border-radius:99px;background:#17263a;overflow:hidden}
.bar i b{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#168ce9,#665df3)}
.bar em{font-style:normal;font-weight:800;color:#e8f1fa;text-align:right}
.score-note{grid-column:1/-1;font-size:12px;color:#71869f;line-height:1.6}
.price-box{display:flex;flex-wrap:wrap;align-items:center;gap:14px 24px;margin-top:14px;padding:18px 22px;border-radius:18px;background:#0c1625;border:1px solid #20354d}
.price-box .pv{font-family:"Plus Jakarta Sans",sans-serif;font-size:24px;font-weight:800;letter-spacing:-.03em;color:#f7fbff}
.price-box small{display:block;font-size:11.5px;color:#71869f;margin-top:2px}
.value-chip{margin-left:auto;font-size:12.5px;color:#a9b8cc}
.value-chip b{color:var(--sc)}
.hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.subnav{position:sticky;top:var(--header-h);z-index:50;background:rgba(7,11,20,.9);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border-bottom:1px solid #16253a;margin-top:30px}
.subnav .container{display:flex;gap:6px;overflow-x:auto;padding:10px 0;scrollbar-width:none}
.subnav a{padding:8px 14px;border-radius:999px;font-size:13px;font-weight:700;color:#9fb2c8;white-space:nowrap;border:1px solid transparent}
.subnav a:hover,.subnav a.on{color:#fff;background:#101f34;border-color:#21354e}
.ph-block{padding:36px 0 6px;scroll-margin-top:calc(var(--header-h) + 60px)}
.ph-block>h2{font-family:"Plus Jakarta Sans",sans-serif;font-size:clamp(22px,2.6vw,28px);letter-spacing:-.04em;color:#f2f7ff;margin-bottom:18px}
.analysis p{font-size:16px;line-height:1.85;color:#cdd9e6;margin-bottom:14px;max-width:820px}
.radar-grid{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:26px;align-items:center;margin-top:22px}
.radar{padding:14px;border-radius:22px;background:#0c1625;border:1px solid #20354d}
.radar svg{width:100%;height:auto;display:block}
.pc-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.pc-card{padding:20px 22px;border-radius:18px;background:#0c1625;border:1px solid #20354d}
.pc-card h3{font-family:"Plus Jakarta Sans",sans-serif;font-size:15px;margin-bottom:12px;color:#f2f7ff}
.pc-card ul{list-style:none;display:grid;gap:9px}
.pc-card li{position:relative;padding-left:24px;font-size:14px;line-height:1.55;color:#cdd9e6}
.pc-card li::before{position:absolute;left:0;top:1px;width:17px;height:17px;border-radius:50%;display:grid;place-items:center;font-size:10px;font-weight:900}
.pc-pros li::before{content:"\2713";background:rgba(41,214,154,.16);color:#5ee0b0}
.pc-cons li::before{content:"\2715";background:rgba(255,102,118,.14);color:#ff8796}
.spec-grid{column-count:2;column-gap:16px}
.spec-group{break-inside:avoid;margin-bottom:16px;border-radius:18px;background:#0c1625;border:1px solid #20354d;overflow:hidden}
.spec-group h3{padding:13px 18px;font-family:"Plus Jakarta Sans",sans-serif;font-size:13px;letter-spacing:.07em;text-transform:uppercase;color:#5db7ff;background:#0e1a2a;border-bottom:1px solid #20354d}
.spec-table{width:100%;border-collapse:collapse}
.spec-table th,.spec-table td{padding:11px 18px;text-align:left;vertical-align:top;font-size:13.5px;line-height:1.55}
.spec-table tr+tr th,.spec-table tr+tr td{border-top:1px solid #16253a}
.spec-table th{width:36%;font-weight:600;color:#8fa4bd}
.spec-table td{color:#e6eef8}
.review-box{padding:26px;border-radius:22px;background:linear-gradient(145deg,#0d1726,#0a1320);border:1px solid #27415c}
.review-head{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin-bottom:14px}
.rv-rating{font-family:"Plus Jakarta Sans",sans-serif;font-size:34px;font-weight:800;color:#ffd166;letter-spacing:-.04em}
.rv-rating small{font-size:15px;color:#8fa4bd;font-weight:600}
.review-box h3{font-family:"Plus Jakarta Sans",sans-serif;font-size:21px;letter-spacing:-.03em;color:#f2f7ff}
.review-body{font-size:16.5px;line-height:1.85;color:#d3deea;margin-top:14px}
.review-body p{margin-bottom:1em}.review-body h2,.review-body h3{font-family:"Plus Jakarta Sans",sans-serif;color:#f2f7ff;margin:1.4em 0 .5em}
.review-body a{color:#5db5ff;text-decoration:underline}
.verdict{margin-top:16px;padding:16px 18px;border-radius:14px;background:rgba(56,165,255,.08);border:1px solid rgba(56,165,255,.24);font-size:15px;line-height:1.7;color:#cfe0f2}
.faq-list{display:grid;gap:10px;max-width:860px}
.faq-list details{border-radius:16px;background:#0c1625;border:1px solid #20354d;padding:0 20px}
.faq-list summary{cursor:pointer;padding:16px 0;font-weight:700;font-size:15px;color:#eef6ff;list-style:none;display:flex;justify-content:space-between;gap:14px}
.faq-list summary::-webkit-details-marker{display:none}
.faq-list summary::after{content:"+";color:#5db7ff;font-size:20px;line-height:1}
.faq-list details[open] summary::after{content:"\2212"}
.faq-list p{padding:0 0 16px;font-size:14.5px;line-height:1.75;color:#a9b8cc}
.notice{margin-top:30px;padding:16px 18px;border-radius:14px;background:#0c1625;border:1px solid #20354d;font-size:12.5px;line-height:1.7;color:#7f94ab}
.notice a{color:#5db5ff;text-decoration:underline}
/* finder */
.finder-layout{display:grid;grid-template-columns:290px minmax(0,1fr);gap:26px;align-items:start}
.f-panel{position:sticky;top:calc(var(--header-h) + 18px);padding:20px;border-radius:20px;background:#0c1625;border:1px solid #20354d;max-height:calc(100vh - var(--header-h) - 36px);overflow:auto}
.f-panel summary{display:none}
.f-field{display:grid;gap:6px;margin-bottom:14px}
.f-field label,.f-field .lbl{font-size:11.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#71869f}
.f-field input[type=search],.f-field select{width:100%;border:1px solid #29425b;background:#0e1a2a;color:#f1f6fb;border-radius:11px;padding:11px 12px;font-size:13.5px;outline:0;appearance:none;-webkit-appearance:none}
.f-field select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%2393a4bd' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;padding-right:34px}
.f-field select option{background:#0d1422;color:#f4f8ff}
.f-field input:focus,.f-field select:focus{border-color:#3d9ee1;box-shadow:0 0 0 3px rgba(61,158,225,.14)}
.f-checks{display:grid;gap:9px;margin:4px 0 16px}
.f-checks label{display:flex;align-items:center;gap:9px;font-size:13.5px;color:#cdd9e6;cursor:pointer}
.f-checks input{width:17px;height:17px;accent-color:#38a5ff}
.f-reset{width:100%}
.f-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.f-count{font-size:14px;color:#a9b8cc}.f-count b{color:#fff}
.f-sort{display:flex;align-items:center;gap:8px;font-size:12.5px;color:#8fa4bd}
.f-sort select{border:1px solid #29425b;background:#0e1a2a;color:#f1f6fb;border-radius:11px;padding:9px 12px;font-size:13px}
.f-more{display:flex;justify-content:center;margin-top:24px}
/* compare */
.cmp-slots{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.cmp-slot{position:relative;min-height:190px;padding:16px;border-radius:20px;background:#0c1625;border:1px dashed #2b4562;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;text-align:center}
.cmp-slot.filled{border-style:solid;border-color:#20354d;background:linear-gradient(145deg,#0d1726,#0a1320)}
.cmp-slot img{height:96px;width:auto;object-fit:contain}
.cmp-slot strong{font-size:13.5px;color:#f2f7ff;line-height:1.3}
.cmp-slot .x{position:absolute;top:10px;right:10px;width:26px;height:26px;border-radius:50%;border:1px solid #29425b;background:#0e1a2a;color:#9fb2c8}
.cmp-slot .x:hover{color:#ff8796;border-color:#ff8796}
.cmp-add{width:100%;position:relative}
.cmp-add input{width:100%;border:1px solid #29425b;background:#0e1a2a;color:#f1f6fb;border-radius:11px;padding:11px 12px;font-size:13.5px;outline:0}
.cmp-add input:focus{border-color:#3d9ee1}
.cmp-results{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:30;max-height:260px;overflow:auto;border-radius:14px;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow);text-align:left;display:none}
.cmp-results.open{display:block}
.cmp-results button{display:block;width:100%;text-align:left;padding:10px 14px;background:none;border:0;color:#dbe7f4;font-size:13px}
.cmp-results button:hover{background:var(--surface-2)}
.cmp-wrap{overflow-x:auto;border-radius:20px;border:1px solid #20354d;background:#0c1625}
.cmp-table{width:100%;border-collapse:collapse;min-width:620px}
.cmp-table th,.cmp-table td{padding:13px 16px;text-align:left;font-size:13.5px;border-top:1px solid #16253a;vertical-align:top}
.cmp-table tr:first-child th,.cmp-table tr:first-child td{border-top:0}
.cmp-table th{width:190px;color:#8fa4bd;font-weight:600;background:#0e1a2a}
.cmp-table td{color:#e6eef8}
.cmp-table td.best{color:#5ee0b0;font-weight:800;background:rgba(41,214,154,.07)}
.cmp-empty{padding:40px 20px;text-align:center;color:var(--soft)}
/* best lists */
.rank-list{display:grid;gap:12px}
.rank-item{display:grid;grid-template-columns:44px 84px minmax(0,1fr) auto;gap:16px;align-items:center;padding:14px 18px;border-radius:18px;background:linear-gradient(145deg,#0d1726,#0a1320);border:1px solid #1e324a;transition:transform .3s ease,border-color .3s ease}
.rank-item:hover{transform:translateY(-4px);border-color:#315a7b}
.rank-no{font-family:"Plus Jakarta Sans",sans-serif;font-size:26px;font-weight:800;color:#3d6e96;text-align:center}
.rank-img{height:96px;display:grid;place-items:center}
.rank-img img{max-height:100%;max-width:100%;object-fit:contain}
.rank-info h3{font-family:"Plus Jakarta Sans",sans-serif;font-size:17px;color:#f2f7ff;letter-spacing:-.02em}
.rank-info p{font-size:13px;color:#8fa4bd;margin-top:4px;line-height:1.55}
.rank-side{text-align:right;display:grid;gap:6px;justify-items:end}
.crumbs-b{display:flex;flex-wrap:wrap;gap:6px;font-size:12.5px;color:var(--muted);margin-bottom:6px}
.crumbs-b a:hover{color:#5db5ff}.crumbs-b i{font-style:normal;opacity:.5}
@media(max-width:1100px){.ph-grid{grid-template-columns:repeat(3,1fr)}.brand-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:900px){
  .ph-hero,.radar-grid,.finder-layout{grid-template-columns:1fr}
  .gallery{position:static}
  .g-main{aspect-ratio:1/1;max-height:360px}
  .quick-grid,.list-grid{grid-template-columns:1fr 1fr}
  .spec-grid{column-count:1}
  .f-panel{position:static;max-height:none}
  .f-panel summary{display:block;cursor:pointer;font-weight:800;color:#eef6ff;padding:2px 0}
  .f-panel[open] summary{margin-bottom:14px}
  .cmp-slots{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:700px){
  .ph-grid{grid-template-columns:repeat(2,1fr);gap:12px}
  .brand-grid{grid-template-columns:repeat(2,1fr)}
  .quick-grid,.list-grid,.pc-grid{grid-template-columns:1fr}
  .score-box{grid-template-columns:1fr;justify-items:center;text-align:center}
  .bars{width:100%}
  .rank-item{grid-template-columns:34px 64px minmax(0,1fr);padding:12px}
  .rank-side{grid-column:1/-1;justify-items:start;text-align:left;grid-auto-flow:column;justify-content:space-between;width:100%}
  .ph-card h3{font-size:14px}
  .ph-info{padding:12px}
  .price-box .value-chip{margin-left:0}
  .f-field input[type=search],.f-field select,.cmp-add input{font-size:16px}
}
@media(max-width:420px){.hero-actions .btn{width:100%}}
"""

PHONE_JS = r"""
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
"""


# ------------------------------------------------------------------ small renderers
def placeholder_svg():
    return ('<div class="ph-ph" aria-hidden="true"><svg viewBox="0 0 60 110" fill="none" stroke="#5db7ff" stroke-width="3">'
            '<rect x="4" y="4" width="52" height="102" rx="10"/><circle cx="30" cy="14" r="3"/></svg></div>')


def img_thumb(p):
    if not p["images"]:
        return None
    i = p["images"][0]
    return i.get("thumb") or i["file"]


def abs_url(path):
    return path if path.startswith("http") else SITE + path


def card(p, reveal=True):
    t = img_thumb(p)
    img = ('<img src="%s" alt="%s" loading="lazy" width="200" height="250">' % (E(t, True), E(p["full"], True))) if t else placeholder_svg()
    k, bits = p["key"], []
    if pl.disp_in(k):
        bits.append('%s"' % pl.fmt_num(k["display_in"]))
    ram = pl.as_list(k.get("ram_gb"))
    if ram:
        bits.append("%s GB" % pl.fmt_num(max(ram, key=lambda v: pl.num(v) or 0)))
    if k.get("battery_mah"):
        bits.append("%s mAh" % pl.fmt_num(k["battery_mah"]))
    pill = '<span class="score-pill %s">%d</span>' % (pl.score_class(p["score"]), p["score"]) if p["score"] is not None else "<span></span>"
    price = pl.money(p).split(" / ")[0] if pl.money(p) else ""
    return ('<a class="ph-card%s" href="/phones/%s/"><div class="ph-img">%s</div><div class="ph-info"><span class="ph-brand">%s</span><h3>%s</h3>'
            '<p class="ph-meta">%s</p><div class="ph-foot">%s<span class="ph-price">%s</span></div></div></a>'
            % (" reveal" if reveal else "", E(p["slug"]), img, E(p["brand"]), E(p["name"]), E(" · ".join(bits)), pill, E(price)))


def ring_svg(score, cls):
    r, c = 52, 2 * 3.14159265 * 52
    return ('<div class="ring %s"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="bg" cx="60" cy="60" r="%d" fill="none" stroke-width="9"/>'
            '<circle class="fg" cx="60" cy="60" r="%d" fill="none" stroke-width="9" stroke-dasharray="%.1f %.1f"/></svg><b><span>%d<small>/ 100</small></span></b></div>'
            % (cls, r, r, c * score / 100.0, c, score))


def radar_svg(sub):
    import math
    cx, cy, R = 150, 140, 90
    vals = [(v or 0) / 100.0 for v in sub]
    pts, axes, labels, grid = [], [], [], []
    for i, name in enumerate(pl.SUB_NAMES):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        pts.append("%.1f,%.1f" % (cx + R * vals[i] * math.cos(a), cy + R * vals[i] * math.sin(a)))
        axes.append('<line x1="%d" y1="%d" x2="%.1f" y2="%.1f" stroke="#1d3148"/>' % (cx, cy, cx + R * math.cos(a), cy + R * math.sin(a)))
        lx, ly = cx + (R + 22) * math.cos(a), cy + (R + 20) * math.sin(a) + 4
        anchor = "middle" if abs(math.cos(a)) < 0.3 else ("start" if math.cos(a) > 0 else "end")
        labels.append('<text x="%.1f" y="%.1f" text-anchor="%s" fill="#9fb2c8" font-size="11" font-weight="700">%s</text>' % (lx, ly, anchor, name))
    for lvl in (0.25, 0.5, 0.75, 1):
        ring = " ".join("%.1f,%.1f" % (cx + R * lvl * math.cos(-math.pi / 2 + j * 2 * math.pi / 5), cy + R * lvl * math.sin(-math.pi / 2 + j * 2 * math.pi / 5)) for j in range(5))
        grid.append('<polygon points="%s" fill="none" stroke="#1d3148"/>' % ring)
    return ('<svg viewBox="0 0 300 290" role="img" aria-label="Score breakdown chart">%s%s<polygon points="%s" fill="rgba(56,165,255,.22)" stroke="#38a5ff" stroke-width="2"/>%s</svg>'
            % ("".join(grid), "".join(axes), " ".join(pts), "".join(labels)))


def spec_value(v):
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v)
    if isinstance(v, dict):
        return "; ".join("%s: %s" % (a, b) for a, b in v.items())
    if v is True:
        return "Yes"
    if v is False:
        return "No"
    return str(v)


ASSET_V = ""


def page(title, desc, canonical, body, jsonld=None, extra_head="", og_image=None, og_type="website"):
    t = bb.TEMPLATE
    t = t.replace("<style>__CSS__</style>", '<link rel="stylesheet" href="/assets/phones.css?v=%s">' % ASSET_V)
    t = t.replace("<script>__JS__</script>", '<script src="/assets/phones.js?v=%s" defer></script>' % ASSET_V)
    t = t.replace('<a class="nav-link" href="/blog/" aria-current="page">Blog</a>',
                  '<a class="nav-link" href="/phones/" aria-current="page">Phones</a>\n      <a class="nav-link" href="/blog/">Blog</a>')
    t = t.replace('<a href="/blog/" aria-current="page">Blog</a>', '<a href="/phones/" aria-current="page">Phones</a>\n  <a href="/blog/">Blog</a>')
    t = t.replace('<a href="/about.html">About</a><a href="/blog/">Blog</a>', '<a href="/about.html">About</a><a href="/phones/">Phones</a><a href="/blog/">Blog</a>')
    t = t.replace("Search news...", "Search phones...").replace("Search news articles", "Search phones").replace("Article search results", "Phone search results")
    t = t.replace('<link rel="alternate" type="application/rss+xml" title="__SITENAME__ News" href="/blog/feed.xml">\n', "")
    if og_image:
        t = t.replace('<meta property="og:image" content="__SITE__/assets/logo.png">', '<meta property="og:image" content="%s">' % E(og_image, True))
        t = t.replace('<meta name="twitter:card" content="summary">', '<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:image" content="%s">' % E(og_image, True))
    ld = ""
    for obj in ([] if not jsonld else (jsonld if isinstance(jsonld, list) else [jsonld])):
        ld += '<script type="application/ld+json">%s</script>\n' % json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    for key, val in (("__MARK__", MARK), ("__TITLE__", E(title)), ("__DESC__", E(desc, True)), ("__CANON__", E(canonical, True)), ("__OG__", og_type),
                     ("__EXTRA_HEAD__", extra_head), ("__LD__", ld), ("__SITENAME__", E(SITE_NAME)), ("__SITE__", E(SITE)), ("__YEAR__", str(date.today().year))):
        t = t.replace(key, val)
    return t.replace("__BODY__", body)


def write(rel, content):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def clean_generated():
    if not os.path.isdir(PHONES_DIR):
        return
    for dp, _d, files in os.walk(PHONES_DIR):
        if "index.html" in files:
            fp = os.path.join(dp, "index.html")
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    if MARK in f.read(600):
                        os.remove(fp)
            except OSError:
                pass
    for dp, _d, _f in os.walk(PHONES_DIR, topdown=False):
        if dp != PHONES_DIR and not os.listdir(dp):
            os.rmdir(dp)


def crumbs(items):
    out = ['<a href="/">Home</a>']
    for name, url in items:
        out.append("<i>/</i>" + ('<a href="%s">%s</a>' % (url, E(name)) if url else "<span>%s</span>" % E(name)))
    return '<nav class="crumbs-b" aria-label="Breadcrumb">%s</nav>' % "".join(out)


def crumb_ld(items):
    els = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"}]
    for i, (name, url) in enumerate(items, 2):
        els.append({"@type": "ListItem", "position": i, "name": name, "item": SITE + (url or "")})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": els}


def short_specs(p):
    k, bits = p["key"], []
    if pl.disp_in(k):
        bits.append('%s" %s' % (pl.fmt_num(k["display_in"]), k.get("display_type") or "display"))
    if k.get("chipset"):
        bits.append(str(k["chipset"]))
    if k.get("main_mp"):
        bits.append("%s MP camera" % pl.fmt_num(k["main_mp"]))
    if k.get("battery_mah"):
        bits.append("%s mAh battery" % pl.fmt_num(k["battery_mah"]))
    return ", ".join(bits)


# ------------------------------------------------------------------ page builders
def build_phone(p, phones):
    k = p["key"]
    url = "/phones/%s/" % p["slug"]
    canonical = SITE + url
    has_review = bool(p["review"])
    title = "%s %s | Clickdy" % (p["full"], "Review, Specs & Price" if has_review else "Specs, Price & Features")
    desc = ("%s: %s. See full specifications, price, Clickdy Score, pros and cons, and similar phones." % (p["full"], short_specs(p))) if short_specs(p) else \
        "Full specifications, price and features of the %s." % p["full"]
    cls = pl.score_class(p["score"])

    # gallery
    if p["images"]:
        main = p["images"][0]
        g_main = '<div class="g-main" id="gMain"><img src="%s" alt="%s" width="480" height="600" fetchpriority="high"></div>' % (E(main["file"], True), E(main.get("alt") or p["full"], True))
        thumbs = ""
        if len(p["images"]) > 1:
            thumbs = '<div class="g-thumbs">%s</div>' % "".join(
                '<button type="button" class="g-thumb%s" data-full="%s" data-alt="%s" aria-label="Show image %d"><img src="%s" alt="" loading="lazy"></button>' % (
                    " active" if i == 0 else "", E(im["file"], True), E(im.get("alt") or p["full"], True), i + 1, E(im.get("thumb") or im["file"], True))
                for i, im in enumerate(p["images"][:8]))
        seen_c, cr = set(), []
        for im in p["images"]:
            c = str(im.get("credit") or "").strip()
            if c and c not in seen_c:
                seen_c.add(c)
                cr.append('<a href="%s" target="_blank" rel="nofollow noopener noreferrer">%s</a>' % (E(im["source_url"], True), E(c)) if im.get("source_url") else E(c))
        credit = '<p class="g-credit">Image: %s</p>' % ", ".join(cr) if cr else ""
    else:
        g_main, thumbs, credit = '<div class="g-main" id="gMain">%s</div>' % placeholder_svg(), "", '<p class="g-credit">Official image not added yet.</p>'

    status = []
    if p["announced"]:
        status.append("Announced %s" % pl.human_date(p["announced"]))
    if p["released"]:
        status.append("Released %s" % pl.human_date(p["released"], True))
    tags = '<div class="tag-row">%s</div>' % "".join('<span class="tag">%s</span>' % E(t) for t in p["tags"]) if p["tags"] else ""
    chip_html = '<div class="chip-row">%s</div>' % "".join('<div class="chip"><small>%s</small><strong>%s</strong></div>' % (E(a), E(b)) for a, b in pl.chips(p))

    score_html = ""
    if p["score"] is not None:
        bars = "".join('<div class="bar"><span>%s</span><i><b style="width:%d%%"></b></i><em>%s</em></div>' % (n, v or 0, v if v is not None else "–") for n, v in zip(pl.SUB_NAMES, p["sub"]))
        score_html = ('<div class="score-box %s">%s<div class="bars">%s</div><p class="score-note">Clickdy Score is calculated from the specifications only. It is not a lab test or a hands-on review.</p></div>'
                      % (cls, ring_svg(p["score"], cls), bars))
    price_html = ""
    if pl.money(p):
        val = '<div class="value-chip %s">Value score: <b>%d</b>/100</div>' % (cls, p["value"]) if p["value"] is not None else ""
        price_html = '<div class="price-box"><div><div class="pv">%s</div><small>%s</small></div>%s</div>' % (E(pl.money(p)), E(p["price"].get("note") or "Launch price. Prices vary by country and retailer."), val)
    sims = pl.similar(p, phones, 4)
    cmp_links = "".join('<a class="btn btn-secondary" href="/phones/compare/?p=%s,%s">vs %s</a>' % (p["slug"], q["slug"], E(q["full"])) for q in sims[:2])
    hero_actions = '<div class="hero-actions"><a class="btn btn-primary" href="/phones/compare/?p=%s">Compare %s</a>%s</div>' % (p["slug"], E(p["name"]), cmp_links)

    nav = '<a href="#overview">Overview</a><a href="#specs">Full specs</a>%s<a href="#faq">FAQ</a><a href="#similar">Similar phones</a>' % ('<a href="#review">Review</a>' if has_review else "")

    pros = "".join("<li>%s</li>" % E(x) for x in p["pros"])
    cons = "".join("<li>%s</li>" % E(x) for x in p["cons"])
    pc = ""
    if pros or cons:
        pc = '<div class="pc-grid">%s%s</div>' % (
            ('<div class="pc-card pc-pros"><h3>Highlights</h3><ul>%s</ul></div>' % pros) if pros else "",
            ('<div class="pc-card pc-cons"><h3>Things to consider</h3><ul>%s</ul></div>' % cons) if cons else "")
    radar = ""
    if p["score"] is not None:
        radar = '<div class="radar-grid"><div class="radar">%s</div><div>%s</div></div>' % (radar_svg(p["sub"]), pc)
    elif pc:
        radar = '<div style="margin-top:22px">%s</div>' % pc

    groups = []
    for gname, rows in p["specs"].items():
        if isinstance(rows, dict) and rows:
            trs = "".join("<tr><th scope=\"row\">%s</th><td>%s</td></tr>" % (E(str(a)), E(spec_value(b))) for a, b in rows.items() if spec_value(b).strip())
            if trs:
                groups.append('<section class="spec-group"><h3>%s</h3><table class="spec-table">%s</table></section>' % (E(str(gname)), trs))

    review_html = ""
    ld_review = None
    if has_review:
        rv = p["review"]
        rating = pl.num(rv.get("rating"))
        rp = "".join("<li>%s</li>" % E(x) for x in pl.as_list(rv.get("pros")))
        rc = "".join("<li>%s</li>" % E(x) for x in pl.as_list(rv.get("cons")))
        body_html = bb.sanitize_html(rv.get("body_html", ""))
        review_html = ('<section class="ph-block" id="review"><h2>%s review</h2><div class="review-box"><div class="review-head">%s<div><h3>%s</h3><small style="color:#8fa4bd">%s%s</small></div></div>%s'
                       '<div class="review-body">%s</div>%s</div></section>') % (
            E(p["full"]), ('<div class="rv-rating">%s<small> / 5</small></div>' % pl.fmt_num(rating)) if rating else "", E(rv.get("headline") or "Our verdict"),
            ("By %s" % E(rv["author"])) if rv.get("author") else "", (" · %s" % E(pl.human_date(rv.get("date", ""), True))) if rv.get("date") else "",
            ('<div class="pc-grid" style="margin-bottom:6px">%s%s</div>' % (('<div class="pc-card pc-pros"><h3>Pros</h3><ul>%s</ul></div>' % rp) if rp else "", ('<div class="pc-card pc-cons"><h3>Cons</h3><ul>%s</ul></div>' % rc) if rc else "")) if (rp or rc) else "",
            body_html, ('<div class="verdict"><strong>Verdict:</strong> %s</div>' % E(rv["verdict"])) if rv.get("verdict") else "")
        if rating:
            ld_review = {"@type": "Review", "reviewRating": {"@type": "Rating", "ratingValue": rating, "bestRating": 5},
                         "author": {"@type": "Person" if rv.get("author") else "Organization", "name": rv.get("author") or SITE_NAME},
                         "datePublished": rv.get("date") or p["updated"] or p["date"] or None}

    faqs = pl.faq(p)
    faq_html = ""
    if faqs:
        faq_html = '<section class="ph-block" id="faq"><h2>%s FAQ</h2><div class="faq-list">%s</div></section>' % (
            E(p["full"]), "".join("<details><summary>%s</summary><p>%s</p></details>" % (E(q), E(a)) for q, a in faqs))
    sim_html = ""
    if sims:
        sim_html = '<section class="ph-block" id="similar"><h2>Similar phones</h2><div class="ph-grid">%s</div></section>' % "".join(card(q) for q in sims)
    srcs = "".join('<li>%s</li>' % ('<a href="%s" target="_blank" rel="nofollow noopener noreferrer">%s</a>' % (E(s["url"], True), E(s.get("name") or "Source")) if s.get("url") else E(s.get("name") or "Source")) for s in p["sources"])
    notice = ('<div class="notice">Specifications are collected from public sources and can vary by region, carrier and model variant. Clickdy Score is spec-based and is not a lab test. '
              '%s%s%s Spotted a mistake? <a href="/contact.html">Tell us</a> and we will fix it.</div>') % (
        ("<br>%s <a href=\"https://creativecommons.org/licenses/by-sa/4.0/\" target=\"_blank\" rel=\"noopener noreferrer\">CC BY-SA 4.0</a>" % E(p["attribution"].replace(" (CC BY-SA 4.0)", ""))) if p["attribution"] else "",
        ("<br>Sources: <ul style='margin:6px 0 6px 18px'>%s</ul>" % srcs) if srcs else "", ("Last updated: %s." % pl.human_date(p["updated"], True)) if p["updated"] else "")

    body = ('<div class="container ph-wrap">%s<div class="ph-hero" id="overview"><div class="gallery">%s%s%s</div><div><span class="ph-brand">%s</span><h1 class="ph-title">%s</h1><p class="ph-status">%s</p>%s%s%s%s%s</div></div></div>'
            '<div class="subnav"><div class="container">%s</div></div>'
            '<div class="container"><section class="ph-block analysis"><h2>%s at a glance</h2>%s%s</section>%s<section class="ph-block" id="specs"><h2>Full specifications</h2>%s<div class="spec-grid">%s</div></section>%s%s%s%s</div>') % (
        crumbs([("Phones", "/phones/"), (p["brand"], "/phones/brand/%s/" % p["brand_slug"]), (p["name"], None)]), g_main, thumbs, credit,
        E(p["brand"]), E(p["full"]), E(" · ".join(status)), tags, chip_html, score_html, price_html, hero_actions,
        nav, E(p["full"]), "".join("<p>%s</p>" % E(x) for x in pl.analysis(p)), radar, "", ('<div class="notice" style="margin:0 0 16px">This article covers a family of models, so the options below can list several versions. The summary at the top uses the first model listed.</div>' if p["variants_note"] else ""), "".join(groups), review_html, faq_html, sim_html, notice)

    image_urls = [abs_url(i["file"]) for i in p["images"]]
    product = {"@context": "https://schema.org", "@type": "Product", "name": p["full"], "brand": {"@type": "Brand", "name": p["brand"]},
               "category": "Smartphone", "description": desc, "url": canonical}
    if image_urls:
        product["image"] = image_urls
    if p["usd"]:
        product["offers"] = {"@type": "Offer", "priceCurrency": "USD", "price": str(int(p["usd"])), "url": canonical}
    if ld_review:
        product["review"] = {kk: vv for kk, vv in ld_review.items() if vv}
    lds = [product, crumb_ld([("Phones", "/phones/"), (p["brand"], "/phones/brand/%s/" % p["brand_slug"]), (p["full"], url)])]
    if faqs:
        lds.append({"@context": "https://schema.org", "@type": "FAQPage",
                    "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]})
    write("phones/%s/index.html" % p["slug"], page(title, desc, canonical, body, jsonld=lds, og_image=image_urls[0] if image_urls else None))
    return url


def listing_hero(kicker, h1_a, h1_b, sub, search=False):
    s = ('<div class="hero-search"><label class="nav-search" aria-label="Search phones"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>'
         '<input id="heroSearch" type="search" placeholder="Search any phone, e.g. iPhone, Galaxy, Redmi..." autocomplete="off"></label><div class="nav-search-results" id="heroSearchResults"></div></div>') if search else ""
    return ('<section class="ph-hub-hero"><div class="container"><span class="section-kicker"><span class="dot"></span> %s</span><h1 class="hub-title">%s <span>%s</span></h1><p class="hub-sub">%s</p>%s</div></section>'
            % (E(kicker), E(h1_a), E(h1_b), E(sub), s))


def build_hub(phones, brands, lists):
    if not phones:
        body = (listing_hero("Clickdy Phones", "Phone specs, scores &", "comparisons.", "Full specifications, honest spec-based scores and side-by-side comparisons for the phones people search for.", True) +
                '<div class="container ph-section"><div class="empty-state">Phones are being added. Check back very soon.<br><a class="btn btn-primary" style="margin-top:18px" href="/">Back to home</a></div></div>')
    else:
        latest = "".join(card(p) for p in phones[:12])
        top = "".join(card(p) for p in sorted([p for p in phones if p["score"] is not None], key=lambda p: -p["score"])[:8])
        qg = ('<div class="quick-grid"><a class="quick-card" href="/phones/finder/"><span class="qi">⌕</span><div><strong>Phone Finder</strong><span>Filter by budget, battery, camera, RAM and more.</span></div></a>'
              '<a class="quick-card" href="/phones/compare/"><span class="qi">⇄</span><div><strong>Compare phones</strong><span>Put up to 4 phones side by side.</span></div></a>'
              '<a class="quick-card" href="%s"><span class="qi">★</span><div><strong>Best phones</strong><span>Automatic top lists by camera, battery, price and more.</span></div></a></div>'
              % ("/phones/best/%s/" % lists[0]["slug"] if lists else "/phones/finder/"))
        bl = ""
        if lists:
            bl = '<section class="ph-section"><div class="sec-head"><div><h2>Best phones</h2><p>Lists that update themselves as new phones are added.</p></div></div><div class="list-grid">%s</div></section>' % "".join(
                '<a class="list-tile" href="/phones/best/%s/">%s</a>' % (l["slug"], E(l["title"])) for l in lists)
        top_brands = sorted(brands.items(), key=lambda kv: -len(kv[1]))[:18]
        bt = '<section class="ph-section"><div class="sec-head"><div><h2>Browse by brand</h2></div><a class="sec-link" href="/phones/brands/">All brands →</a></div><div class="brand-grid">%s</div></section>' % "".join(
            '<a class="brand-tile" href="/phones/brand/%s/"><span>%s</span><small>%d</small></a>' % (bs, E(v[0]["brand"]), len(v)) for bs, v in top_brands)
        body = (listing_hero("Clickdy Phones", "Find the right phone,", "faster.", "Full specifications, spec-based Clickdy Scores and side-by-side comparisons for %d phones and growing." % len(phones), True) +
                '<div class="container"><section class="ph-section">%s</section>'
                '<section class="ph-section"><div class="sec-head"><div><h2>Latest phones</h2></div><a class="sec-link" href="/phones/finder/?sort=new">See all →</a></div><div class="ph-grid">%s</div></section>'
                '<section class="ph-section"><div class="sec-head"><div><h2>Top rated by Clickdy Score</h2><p>Ranked by the spec-based score. It is not a hands-on review.</p></div></div><div class="ph-grid">%s</div></section>%s%s</div>' % (qg, latest, top, bl, bt))
    desc = "Phone specifications, prices, Clickdy Scores and comparisons. Search any phone, compare models side by side and find the best phone for your budget."
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "%s Phones" % SITE_NAME, "url": SITE + "/phones/",
          "potentialAction": {"@type": "SearchAction", "target": SITE + "/phones/finder/?q={search_term_string}", "query-input": "required name=search_term_string"}}
    write("phones/index.html", page("Phone Specifications, Prices & Comparisons | Clickdy", desc, SITE + "/phones/", body, jsonld=ld))
    return ["/phones/"]


def build_brands(brands):
    urls = ["/phones/brands/"]
    az = sorted(brands.items(), key=lambda kv: kv[1][0]["brand"].lower())
    tiles = "".join('<a class="brand-tile" href="/phones/brand/%s/"><span>%s</span><small>%d</small></a>' % (bs, E(v[0]["brand"]), len(v)) for bs, v in az)
    body = ('<div class="container ph-wrap">%s<h1 class="hub-title" style="font-size:clamp(30px,4vw,44px)">All phone <span>brands</span></h1><div class="brand-grid" style="margin-top:22px">%s</div></div>'
            % (crumbs([("Phones", "/phones/"), ("Brands", None)]), tiles or '<div class="empty-state">No brands yet.</div>'))
    write("phones/brands/index.html", page("All Phone Brands | Clickdy", "Browse phone specifications by brand.", SITE + "/phones/brands/", body,
                                           jsonld=crumb_ld([("Phones", "/phones/"), ("Brands", "/phones/brands/")])))
    for bs, items in brands.items():
        brand = items[0]["brand"]
        pages = [items[i:i + BRAND_PAGE_SIZE] for i in range(0, len(items), BRAND_PAGE_SIZE)] or [[]]
        for n, chunk in enumerate(pages, 1):
            base = "/phones/brand/%s/" % bs
            url = base if n == 1 else "%spage/%d/" % (base, n)
            pager = ""
            if len(pages) > 1:
                prev = ('<a href="%s" rel="prev">← Newer</a>' % (base if n == 2 else "%spage/%d/" % (base, n - 1))) if n > 1 else ""
                nxt = ('<a href="%spage/%d/" rel="next">Older →</a>' % (base, n + 1)) if n < len(pages) else ""
                pager = '<div class="pager">%s<span>Page %d of %d</span>%s</div>' % (prev, n, len(pages), nxt)
            body = ('<div class="container ph-wrap">%s<h1 class="hub-title" style="font-size:clamp(30px,4vw,48px)">%s <span>phones</span></h1><p class="hub-sub" style="margin-bottom:24px">%d %s phones with full specifications and Clickdy Scores.</p><div class="ph-grid">%s</div>%s</div>'
                    % (crumbs([("Phones", "/phones/"), (brand, None)]), E(brand), len(items), E(brand), "".join(card(p) for p in chunk), pager))
            extra = ""
            if n > 1:
                extra += '<link rel="prev" href="%s%s">\n' % (SITE, base if n == 2 else "%spage/%d/" % (base, n - 1))
            if n < len(pages):
                extra += '<link rel="next" href="%s%spage/%d/">\n' % (SITE, base, n + 1)
            t = "%s Phones: Specs, Prices & Scores%s | Clickdy" % (brand, " (Page %d)" % n if n > 1 else "")
            write(url.strip("/") + "/index.html", page(t, "All %s phones with full specifications, prices and Clickdy Scores." % brand, SITE + url, body, extra_head=extra,
                                                       jsonld=crumb_ld([("Phones", "/phones/"), (brand, base)])))
            urls.append(url)
    return urls


def sel(attr, label, options):
    return '<div class="f-field"><label>%s</label><select data-f="%s">%s</select></div>' % (label, attr, "".join('<option value="%s">%s</option>' % (v, t) for v, t in options))


def build_finder():
    panel = ('<details class="f-panel" id="fPanel"><summary>Filters</summary>'
             '<div class="f-field"><label for="fq">Search</label><input id="fq" type="search" data-f="q" placeholder="Name or brand" autocomplete="off"></div>'
             + '<div class="f-field"><label>Brand</label><select data-f="brand"><option value="">All brands</option></select></div>'
             + sel("price", "Max price (USD)", [("0", "Any price"), ("150", "$150"), ("250", "$250"), ("400", "$400"), ("600", "$600"), ("900", "$900"), ("1300", "$1300")])
             + sel("ram", "RAM", [("0", "Any"), ("4", "4 GB or more"), ("6", "6 GB or more"), ("8", "8 GB or more"), ("12", "12 GB or more"), ("16", "16 GB or more")])
             + sel("sto", "Storage", [("0", "Any"), ("128", "128 GB or more"), ("256", "256 GB or more"), ("512", "512 GB or more"), ("1024", "1 TB or more")])
             + sel("bat", "Battery", [("0", "Any"), ("4000", "4000 mAh or more"), ("5000", "5000 mAh or more"), ("6000", "6000 mAh or more")])
             + sel("hz", "Refresh rate", [("0", "Any"), ("90", "90 Hz or more"), ("120", "120 Hz or more"), ("144", "144 Hz or more")])
             + sel("size", "Screen size", [("", "Any"), ("compact", "Compact (6.3\" or less)"), ("standard", "Standard (6.3 - 6.7\")"), ("large", "Large (6.7\" or more)")])
             + sel("mp", "Main camera", [("0", "Any"), ("48", "48 MP or more"), ("108", "108 MP or more"), ("200", "200 MP")])
             + '<div class="f-field"><label>Release year</label><select data-f="year"><option value="0">Any year</option></select></div>'
             + '<div class="f-checks"><label><input type="checkbox" data-f="g5"> 5G</label><label><input type="checkbox" data-f="nfc"> NFC</label>'
               '<label><input type="checkbox" data-f="wl"> Wireless charging</label><label><input type="checkbox" data-f="ip"> Water resistant (IP67+)</label></div>'
             + '<button class="btn btn-secondary f-reset" type="button" id="fReset">Reset filters</button></details>')
    results = ('<div><div class="f-top"><div class="f-count" id="fCount">Loading phones…</div><label class="f-sort">Sort by <select data-f="sort">'
               '<option value="score">Clickdy Score</option><option value="new">Newest</option><option value="pricelow">Price: low to high</option><option value="pricehigh">Price: high to low</option>'
               '<option value="battery">Battery</option><option value="camera">Camera</option></select></label></div><div class="ph-grid" id="fResults"></div>'
               '<div class="f-more" id="fMore" hidden><button class="btn btn-secondary" type="button" id="fMoreBtn">Show more phones</button></div></div>')
    body = ('<div class="container ph-wrap">%s<h1 class="hub-title" style="font-size:clamp(30px,4vw,46px)">Phone <span>Finder</span></h1><p class="hub-sub" style="margin-bottom:26px">Narrow down by budget, battery, camera and more. Your filters are saved in the link, so you can share a search.</p>'
            '<div class="finder-layout" id="finderApp">%s%s</div></div>') % (crumbs([("Phones", "/phones/"), ("Finder", None)]), panel, results)
    write("phones/finder/index.html", page("Phone Finder: Filter by Price, Battery, Camera & More | Clickdy", "Find the right phone by price, RAM, storage, battery, camera, screen size and features.", SITE + "/phones/finder/", body,
                                           jsonld=crumb_ld([("Phones", "/phones/"), ("Finder", "/phones/finder/")])))
    return ["/phones/finder/"]


def build_compare():
    body = ('<div class="container ph-wrap">%s<h1 class="hub-title" style="font-size:clamp(30px,4vw,46px)">Compare <span>phones</span></h1><p class="hub-sub" style="margin-bottom:26px">Pick up to four phones. The best value in each row is highlighted.</p>'
            '<div id="compareApp"><div class="cmp-slots" id="cmpSlots"></div><div id="cmpTable"></div></div></div>') % crumbs([("Phones", "/phones/"), ("Compare", None)])
    write("phones/compare/index.html", page("Compare Phones Side by Side | Clickdy", "Compare phone specifications, prices and Clickdy Scores side by side.", SITE + "/phones/compare/", body,
                                            jsonld=crumb_ld([("Phones", "/phones/"), ("Compare", "/phones/compare/")])))
    return ["/phones/compare/"]


def build_lists(lists):
    urls = []
    for l in lists:
        rows = []
        for i, p in enumerate(l["items"], 1):
            t = img_thumb(p)
            im = ('<img src="%s" alt="%s" loading="lazy">' % (E(t, True), E(p["full"], True))) if t else placeholder_svg()
            price = pl.money(p)
            rows.append('<a class="rank-item reveal" href="/phones/%s/"><div class="rank-no">%d</div><div class="rank-img">%s</div><div class="rank-info"><h3>%s</h3><p>%s</p></div>'
                        '<div class="rank-side"><span class="score-pill %s">%s</span><span class="ph-price">%s</span></div></a>' % (
                            p["slug"], i, im, E(p["full"]), E(short_specs(p)), pl.score_class(p["score"]), p["score"] if p["score"] is not None else "–", E(price)))
        body = ('<div class="container ph-wrap">%s<h1 class="hub-title" style="font-size:clamp(28px,4vw,44px)">%s</h1><p class="hub-sub" style="margin-bottom:24px">%s</p><div class="rank-list">%s</div>'
                '<div class="notice">Rankings use the Clickdy Score, which is calculated from specifications only. This page updates automatically as phones are added or their specs change.</div></div>') % (
            crumbs([("Phones", "/phones/"), ("Best phones", None)]), E(l["title"]), E(l["desc"]), "".join(rows))
        url = "/phones/best/%s/" % l["slug"]
        item_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": l["title"],
                   "itemListElement": [{"@type": "ListItem", "position": i, "url": SITE + "/phones/%s/" % p["slug"], "name": p["full"]} for i, p in enumerate(l["items"], 1)]}
        write(url.strip("/") + "/index.html", page("%s | Clickdy" % l["title"], l["desc"], SITE + url, body, jsonld=[item_ld, crumb_ld([("Phones", "/phones/"), (l["title"], url)])]))
        urls.append(url)
    return urls


def compact_index(phones):
    out = []
    for p in phones:
        k = p["key"]
        ram = [pl.num(x) for x in pl.as_list(k.get("ram_gb")) if pl.num(x)]
        sto = [pl.num(x) for x in pl.as_list(k.get("storage_gb")) if pl.num(x)]
        kk = {"display_in": pl.num(k.get("display_in")), "display_type": k.get("display_type"), "refresh_hz": pl.num(k.get("refresh_hz")), "peak_nits": pl.num(k.get("peak_nits")),
              "chipset": k.get("chipset"), "ram": max(ram) if ram else None, "sto": max(sto) if sto else None, "main_mp": pl.num(k.get("main_mp")),
              "battery_mah": pl.num(k.get("battery_mah")), "wired_w": pl.num(k.get("wired_w")), "wireless_w": pl.num(k.get("wireless_w")),
              "weight_g": pl.num(k.get("weight_g")), "thickness_mm": pl.num(k.get("thickness_mm")), "five_g": k.get("five_g"), "nfc": k.get("nfc"),
              "ip": k.get("ip"), "os": k.get("os")}
        kk = {a: (int(b) if isinstance(b, float) and b == int(b) else b) for a, b in kk.items() if b is not None}
        out.append({"s": p["slug"], "b": p["brand"], "bs": p["brand_slug"], "n": p["name"], "i": img_thumb(p) or "", "y": p["year"], "d": p["date"],
                    "sc": p["score"], "sub": p["sub"], "p": int(p["usd"]) if p["usd"] else None, "pk": int(p["pkr"]) if p["pkr"] else None, "k": kk})
    return out


def main():
    global ASSET_V
    css = bb.CSS + "\n" + PHONE_CSS
    js = bb.JS.replace('"/blog/search.json"', '"/phones/search.json"') + "\n" + PHONE_JS
    assert '"/phones/search.json"' in js
    ASSET_V = hashlib.md5((css + js).encode("utf-8")).hexdigest()[:8]
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for name, content in (("phones.css", css), ("phones.js", js)):
        with open(os.path.join(ASSETS_DIR, name), "w", encoding="utf-8") as f:
            f.write(content)

    phones = pl.load_phones()
    clean_generated()
    brands = {}
    for p in phones:
        brands.setdefault(p["brand_slug"], []).append(p)
    year = date.today().year
    lists = pl.best_lists(phones, year)
    urls = [(u, None) for u in build_hub(phones, brands, lists)]
    urls += [(u, None) for u in build_brands(brands)] if brands else []
    urls += [(u, None) for u in build_finder() + build_compare()]
    urls += [(u, None) for u in build_lists(lists)]
    for p in phones:
        urls.append((build_phone(p, phones), p["updated"] or None))

    write_json(os.path.join(PHONES_DIR, "data.json"), compact_index(phones)) if phones else write_json(os.path.join(PHONES_DIR, "data.json"), [])
    write("phones/search.json", json.dumps([{"t": p["full"], "u": "/phones/%s/" % p["slug"], "c": p["brand"], "e": short_specs(p), "d": pl.human_date(p["date"])} for p in phones],
                                           ensure_ascii=False, separators=(",", ":")))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    imgs = {"/phones/%s/" % p["slug"]: p["images"] for p in phones}
    for u, last in urls:
        extra = "".join("<image:image><image:loc>%s</image:loc></image:image>" % E(abs_url(i["file"])) for i in imgs.get(u, [])[:5])
        sm.append("  <url><loc>%s</loc>%s%s</url>" % (E(SITE + u), "<lastmod>%s</lastmod>" % last if last else "", extra))
    sm.append("</urlset>")
    write("sitemap-phones.xml", "\n".join(sm) + "\n")
    print("Built %d phone(s), %d brand(s), %d best-list(s), %d URL(s)." % (len(phones), len(brands), len(lists), len(urls)))


if __name__ == "__main__":
    main()
