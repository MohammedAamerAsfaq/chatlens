'use strict';

let modulePromise = null;

function loadBaileys() {
  if (!modulePromise) modulePromise = import('baileys');
  return modulePromise;
}

module.exports = { loadBaileys };
