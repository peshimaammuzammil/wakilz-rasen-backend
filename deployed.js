<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Wakilz</title>
    <script>
      // Single Page App — GitHub Pages redirect trick (rafgraph/spa-github-pages)
      // When GitHub Pages serves a 404 for a sub-path, this script redirects
      // back to the root with the path encoded in the query string.
      // The main index.html then decodes it and restores the correct path.
      var segmentCount = 0; // 0 for custom domain (wakilz.com), 1 for github.io/<repo>
      var l = window.location;
      l.replace(
        l.protocol + '//' + l.hostname + (l.port ? ':' + l.port : '') +
        l.pathname.split('/').slice(0, 1 + segmentCount).join('/') + '/?p=/' +
        l.pathname.slice(1).split('/').slice(segmentCount).join('/').replace(/&/g, '~and~') +
        (l.search ? '&q=' + l.search.slice(1).replace(/&/g, '~and~') : '') +
        l.hash
      );
    </script>
  </head>
  <body></body>
</html>
