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
    src: url, currentSrc: url, loading: options.loading || 'lazy',
    complete: !!options.complete, naturalWidth: options.naturalWidth || 0,
    addEventListener(name, callback) {
      const list = handlers.get(name) || [];
      list.push(callback);
      handlers.set(name, list);
    },
    getAttribute(name) { return name === 'src' ? this.src : null; },
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
  image(`${origin}/image_proxy?url=already-loaded`, { complete: true, naturalWidth: 4 }),
];
const ui = run([...eligible, ...ignored]);
ui.click();
assert.equal(ui.button.disabled, true);
assert.equal(eligible.filter((item) => item.loading === 'eager').length, 4,
  'only four signed proxy loads should run in the first batch');
assert(ignored.every((item) => item.loading === 'lazy'),
  'never upgrade external, wrong-route or previously completed image loads');
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

const prebroken = image(`${origin}/image_proxy?already-broken`, { complete: true });
const empty = run([prebroken]);
assert(prebroken.card.classList.contains('goreecloud-thumbnail-unavailable'),
  'an already-broken image must receive the accessible unavailable placeholder');
empty.click();
assert.equal(empty.status.textContent,
  '0 of 0 additional previews checked (0 loaded, 0 unavailable).');
console.log('PASS image gallery bounded queue, no cross-origin auto-load, timeout abort, truthful status');
