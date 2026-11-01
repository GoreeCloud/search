// Offline DOM contract for the private Search appearance -> GC UI Foundations bridge.
// Execute with: node tests/goreecloud/gc_ui_theme_contract.cjs
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.resolve(__dirname, '../../searx/static/themes/simple/goreecloud-theme.js'), 'utf8');

function scenario({ theme = 'theme-auto', systemDark = false, stored = null, storageBlocked = false, withButton = true } = {}) {
  const classes = new Set(['no-js', theme]);
  const attributes = new Map();
  const callbacks = new Map();
  const store = new Map(stored === null ? [] : [['goreecloud-search-theme', stored]]);
  const media = { matches: systemDark, addEventListener(name, fn) { callbacks.set('media:' + name, fn); } };
  const buttonAttributes = new Map();
  const button = withButton ? {
    title: '',
    setAttribute(name, value) { buttonAttributes.set(name, value); },
    addEventListener(name, fn) { callbacks.set('button:' + name, fn); },
  } : null;
  const html = {
    classList: {
      contains(name) { return classes.has(name); },
      remove(...names) { names.forEach((name) => classes.delete(name)); },
      add(name) { classes.add(name); },
    },
    setAttribute(name, value) { attributes.set(name, value); },
  };
  const storage = {
    getItem(name) { if (storageBlocked) throw Error('blocked'); return store.get(name) ?? null; },
    setItem(name, value) { if (storageBlocked) throw Error('blocked'); store.set(name, value); },
  };
  vm.runInNewContext(script, {
    document: { documentElement: html, querySelector(selector) {
      assert.equal(selector, '.goreecloud-theme-toggle');
      return button;
    } },
    window: { matchMedia(query) {
      assert.equal(query, '(prefers-color-scheme: dark)');
      return media;
    } },
    sessionStorage: storage,
  }, { filename: 'goreecloud-theme.js' });
  return {
    classes, attributes, buttonAttributes, callbacks, store, media, button,
    click() { assert.ok(callbacks.has('button:click')); callbacks.get('button:click')(); },
    systemChange(dark) { media.matches = dark; callbacks.get('media:change')(); },
  };
}

const auto = scenario();
assert.equal(auto.attributes.get('data-gc-mode'), 'light');
assert.equal(auto.buttonAttributes.get('aria-pressed'), 'false');
assert.equal(auto.buttonAttributes.get('aria-label'), 'Switch to dark mode');
auto.systemChange(true);
assert.equal(auto.attributes.get('data-gc-mode'), 'dark');
assert.equal(auto.buttonAttributes.get('aria-pressed'), 'true');
assert.equal(auto.store.size, 0, 'OS changes do not create storage writes');
auto.click();
assert.equal(auto.attributes.get('data-gc-mode'), 'light');
assert.ok(auto.classes.has('theme-light'));
assert.equal(auto.store.get('goreecloud-search-theme'), 'light');
auto.systemChange(false);
auto.systemChange(true);
assert.equal(auto.attributes.get('data-gc-mode'), 'light', 'explicit session choice wins over OS');
auto.click();
assert.equal(auto.attributes.get('data-gc-mode'), 'dark');
assert.ok(auto.classes.has('theme-dark'));
assert.equal(auto.store.get('goreecloud-search-theme'), 'dark');

const saved = scenario({ theme: 'theme-black', stored: 'light' });
assert.equal(saved.attributes.get('data-gc-mode'), 'light');
assert.ok(saved.classes.has('theme-light'));
assert.ok(!saved.classes.has('theme-black'));

const forcedDark = scenario({ theme: 'theme-dark', systemDark: false, storageBlocked: true });
assert.equal(forcedDark.attributes.get('data-gc-mode'), 'dark');
forcedDark.click();
assert.equal(forcedDark.attributes.get('data-gc-mode'), 'light', 'blocked storage does not break toggle');

const noButton = scenario({ theme: 'theme-auto', systemDark: true, withButton: false });
assert.equal(noButton.attributes.get('data-gc-mode'), 'dark', 'mode sync does not depend on button');

console.log('PASS GC UI Search theme bridge (auto, OS, override, black, blocked storage, no button)');
