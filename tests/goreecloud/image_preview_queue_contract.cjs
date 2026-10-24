/* Deterministic in-process browser-DOM contract: no network or image fetches. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname,
  '../../searx/static/themes/simple/goreecloud-image-previews.js'), 'utf8');
const origin = 'https://search-dev.goreecloud.com';

function image(url, options = {}) {
  const classes = new Set();
  const handlers = new Map();
  const card = { classList: {
    add: (name) => classes.add(name), remove: (name) => classes.delete(name),
    contains: (name) => classes.has(name),
  } };
  const element = {
    src: url, currentSrc: options.currentSrc || url, srcset: options.srcset || '',
    loading: options.loading || 'lazy',
    complete: !!options.complete, naturalWidth: options.naturalWidth || 0,
    addEventListener(name, callback) {
      const list = handlers.get(name) || [];
      list.push(callback);
      handlers.set(name, list);
    },
    getAttribute(name) { return name === 'src' ? this.src : null; },
    hasAttribute(name) { return name === 'srcset' && !!this.srcset; },
    removeAttribute(name) { if (name === 'src') this.src = ''; },
    closest(selector) { assert.equal(selector, 'article.result-images'); return card; },
    fire(name, width = 4) {
      this.complete = true;
      this.naturalWidth = name === 'load' ? width : 0;
      for (const callback of handlers.get(name) || []) callback();
    },
    card,
  };
  return element;
}

function run(images) {
  let click;
  let nextTimer = 0;
  const timers = new Map();
  const button = { disabled: false, textContent: '', addEventListener(name, callback) {
    assert.equal(name, 'click'); click = callback;
  } };
  const status = { textContent: '' };
  const gallery = { querySelectorAll() { return images; } };
  const document = {
    querySelector(selector) {
      assert.equal(selector, '#urls.goreecloud-image-results');
      return gallery;
    },
    getElementById(id) {
      return id === 'goreecloud-image-load-all' ? button :
        id === 'goreecloud-image-load-status' ? status : null;
    },
  };
  vm.runInNewContext(script, {
    document, location: { origin, href: `${origin}/search` }, URL,
    setTimeout(callback, delay) {
      assert.equal(delay, 20000);
      const id = ++nextTimer;
      timers.set(id, callback);
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
  });
  return { button, status, timers, click() { click(); } };
}

const eligible = Array.from({ length: 8 }, (_, i) =>
  image(`${origin}/image_proxy?url=sealed-${i}&h=signature`));
const ignored = [
  image('https://tracking.invalid/image.png'),
  image(`${origin}/different_route?url=sealed`),
  image(`${origin}/image_proxy?url=sealed-but-unsigned`),
  image('https://tracking.invalid/new.png', {
    currentSrc: `${origin}/image_proxy?url=sealed-old&h=signature`,
  }),
  image(`${origin}/image_proxy?url=sealed&h=signature`, {
    srcset: 'https://tracking.invalid/override.png 2x',
  }),
  image(`${origin}/image_proxy?url=already-loaded`, { complete: true, naturalWidth: 4 }),
];
const ui = run([...eligible, ...ignored]);
ui.click();
assert.equal(ui.button.disabled, true);
assert.equal(eligible.filter((item) => item.loading === 'eager').length, 4,
  'only four signed proxy loads should run in the first batch');
assert(ignored.every((item) => item.loading === 'lazy'),
  'never upgrade external, wrong-route or previously completed image loads');
assert(ignored.every((item) => item.src === '' &&
  item.card.classList.contains('goreecloud-thumbnail-unavailable')),
  'strip untrusted direct/unsigned thumbnail URLs and show an unavailable placeholder');
assert.equal(ui.timers.size, 4);

eligible[0].fire('load');
eligible[1].fire('load');
eligible[2].fire('error');
eligible[3].fire('load');
assert.equal(eligible.filter((item) => item.loading === 'eager').length, 8);
assert.equal(ui.timers.size, 4, 'completed loads must free real slots');
eligible[4].fire('load');
eligible[5].fire('error');
assert.equal(ui.timers.size, 2);
for (const timeout of [...ui.timers.values()]) timeout();
assert.equal(ui.timers.size, 0);
assert.equal(ui.status.textContent,
  '8 of 8 additional previews checked (4 loaded, 4 unavailable).');
assert.equal(ui.button.textContent, 'Previews requested');
for (const item of eligible.slice(6)) {
  assert.equal(item.src, '', 'timed-out image requests must be aborted');
  assert(item.card.classList.contains('goreecloud-thumbnail-unavailable'));
}
eligible[6].fire('load');
assert.equal(ui.status.textContent,
  '8 of 8 additional previews checked (4 loaded, 4 unavailable).',
  'late events must not double-count a timed-out request');
assert(eligible[6].card.classList.contains('goreecloud-thumbnail-unavailable'),
  'late load after abort must not erase the visible unavailable placeholder');

const changing = Array.from({ length: 6 }, (_, i) =>
  image(`${origin}/image_proxy?url=changing-${i}&h=signature`));
const changed = run(changing);
changed.click();
changing[4].src = 'https://tracking.invalid/swapped.png';
changing[0].fire('load');
assert.equal(changing[4].loading, 'lazy',
  'queue must recheck each source before dispatching a previously eligible item');
assert.equal(changing[4].src, '', 'source-swap must be aborted before lazy browser fetch');
assert(changing[4].card.classList.contains('goreecloud-thumbnail-unavailable'),
  'source-swap must keep a visible unavailable placeholder');
assert.equal(changing[5].loading, 'eager',
  'a denied mid-queue source must not block a subsequent signed proxy image');
for (const i of [1, 2, 3, 5]) changing[i].fire('load');
assert.equal(changed.status.textContent,
  '6 of 6 additional previews checked (5 loaded, 1 unavailable).',
  'mutated source must consume one truthful denied slot without browser egress');

const prebroken = image(`${origin}/image_proxy?already-broken`, { complete: true });
const empty = run([prebroken]);
assert(prebroken.card.classList.contains('goreecloud-thumbnail-unavailable'),
  'an already-broken image must receive the accessible unavailable placeholder');
empty.click();
assert.equal(empty.status.textContent,
  '0 of 0 additional previews checked (0 loaded, 0 unavailable).');

const recovering = image(`${origin}/image_proxy?url=valid&h=signature`, { complete: true });
run([recovering]);
assert(recovering.card.classList.contains('goreecloud-thumbnail-unavailable'),
  'a decoded-failure placeholder must be visible before a real recovery');
recovering.fire('load');
assert(!recovering.card.classList.contains('goreecloud-thumbnail-unavailable'),
  'successful signed proxy load must still clear the placeholder');
console.log('PASS image gallery bounded queue, no cross-origin auto-load, timeout abort, truthful status');
