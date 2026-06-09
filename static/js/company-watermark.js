(function () {
  'use strict';

  function makeSeed(value) {
    var hash = 2166136261;
    for (var i = 0; i < value.length; i += 1) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function makeRandom(seed) {
    var value = seed || 1;
    return function () {
      value += 0x6D2B79F5;
      var t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function cleanCompanyName(value) {
    return String(value || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function buildWatermark() {
    var layer = document.querySelector('[data-company-watermark]');
    if (!layer) return;

    var companyName = cleanCompanyName(layer.getAttribute('data-company-name'));
    if (!companyName) {
      layer.innerHTML = '';
      layer.hidden = true;
      return;
    }

    layer.hidden = false;
    layer.innerHTML = '';

    var width = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    var height = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    var isSmallScreen = width < 768;
    var columnWidth = isSmallScreen ? 260 : 340;
    var rowHeight = isSmallScreen ? 190 : 230;
    var columns = Math.max(3, Math.ceil(width / columnWidth) + 2);
    var rows = Math.max(4, Math.ceil(height / rowHeight) + 2);
    var seed = makeSeed(companyName + ':' + columns + ':' + rows + ':' + Math.round(width / 100));
    var random = makeRandom(seed);
    var fragment = document.createDocumentFragment();

    for (var row = -1; row < rows - 1; row += 1) {
      for (var col = -1; col < columns - 1; col += 1) {
        var item = document.createElement('span');
        var variant = random();
        item.className = 'company-watermark-item' + (variant > 0.78 ? ' company-watermark-item--accent' : '');
        item.textContent = companyName;

        var baseLeft = (col + 0.5) * columnWidth;
        var baseTop = (row + 0.5) * rowHeight;
        var offsetLeft = (random() - 0.5) * columnWidth * 0.46;
        var offsetTop = (random() - 0.5) * rowHeight * 0.5;
        var diagonalOffset = row % 2 === 0 ? columnWidth * 0.28 : 0;
        var rotate = -24 + random() * 10;
        var scale = 0.86 + random() * 0.28;

        item.style.left = Math.round(baseLeft + diagonalOffset + offsetLeft) + 'px';
        item.style.top = Math.round(baseTop + offsetTop) + 'px';
        item.style.transform = 'translate(-50%, -50%) rotate(' + rotate.toFixed(2) + 'deg) scale(' + scale.toFixed(3) + ')';
        item.style.animationDelay = (random() * -14).toFixed(2) + 's';
        fragment.appendChild(item);
      }
    }

    layer.appendChild(fragment);
  }

  function debounce(callback, delay) {
    var timer = null;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(callback, delay);
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWatermark, { once: true });
  } else {
    buildWatermark();
  }

  window.addEventListener('resize', debounce(buildWatermark, 180));
  window.addEventListener('orientationchange', debounce(buildWatermark, 260));
})();
