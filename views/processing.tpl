<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="utf-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <meta name="description" content="">
  <meta name="author" content="">
  <link rel="icon" href="../../favicon.ico">

  <title>youtube-dl</title>

  <link href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css" rel="stylesheet">
  <link href="static/style.css" rel="stylesheet">
</head>

<body>

  <div class="site-wrapper">
    <div class="site-wrapper-inner">
      <div class="cover-container">

        <div class="inner cover">
          <h1 class="cover-heading">youtube-dl</h1>
          <div id="initial">
            <img class="loader" src="static/loader.gif">
            <p class="lead">Your video / song is being downloaded</p>
          </div>
          <p id="success" class="lead" style="display: none">Your video / song can be downloaded:
            <a href="static/{{generated_file}}" download={{generated_file}}>{{generated_file}}</a>
          </p>
          <a style="font-size: 5rem" href="../youtube-dl">🔙</a>
        </div>

      </div>
    </div>
  </div>

  <script>
  function fetchUntilDone() {
    fetch('q_pop_processed?url={{url}}').then(resp => resp.json()).then(resp => {
      if (!resp.complete) {
        setTimeout(fetchUntilDone, 2000);
        return;
      }
      document.getElementById('initial').style.display = 'none';
      document.getElementById('success').style.display = 'block';
    }).catch(error => console.error(error));
  }
  fetchUntilDone();
  </script>

</body>

</html>
