/* KLineAPI v3.0 前端交互 */
(function () {
  'use strict';

  /* 移动端导航 */
  var navToggle = document.getElementById('navToggle');
  var siteNav = document.getElementById('siteNav');
  if (navToggle && siteNav) {
    navToggle.addEventListener('click', function () {
      var open = siteNav.classList.toggle('open');
      navToggle.classList.toggle('open', open);
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* 复制按钮 */
  document.querySelectorAll('.copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      if (!text) return;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = '已复制';
        setTimeout(function () { btn.textContent = old; }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
      } else {
        fallbackCopy(text, done);
      }
    });
  });

  function fallbackCopy(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* noop */ }
    document.body.removeChild(ta);
    done();
  }

  /* 首页终端打字效果 */
  var cursor = document.getElementById('termCursor');
  var termBody = document.querySelector('.term-body');
  if (cursor && termBody) {
    var original = termBody.innerHTML;
    var lines = original.split('\n');
    var current = 0;
    var pos = 0;
    termBody.innerHTML = '';
    var timer = setInterval(function () {
      if (current >= lines.length) {
        clearInterval(timer);
        cursor.style.display = 'none';
        return;
      }
      var line = lines[current];
      pos += 2;
      if (pos >= line.length) {
        pos = 0;
        current += 1;
      }
      termBody.innerHTML = lines.slice(0, current).join('\n') + '\n' + line.slice(0, pos);
      if (current < lines.length) {
        var el = document.createElement('span');
        el.className = 'term-cursor-inline';
        cursor.style.display = 'none';
      }
    }, 12);
    /* 保证最终恢复完整内容 */
    setTimeout(function () {
      clearInterval(timer);
      termBody.innerHTML = original;
      cursor.style.display = 'none';
    }, lines.length * lines.length);
  }

  /* 页脚时钟 */
  var clock = document.getElementById('footerClock');
  if (clock) {
    function tick() {
      var now = new Date();
      var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
      clock.textContent = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) +
        ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
    }
    tick();
    setInterval(tick, 1000);
  }
})();
