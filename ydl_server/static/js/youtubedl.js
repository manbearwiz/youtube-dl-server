var entityMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;'
};

function escapeHtml(string) {
  return String(string).replace(/[&<>"'`=\/]/g, function (s) {
    return entityMap[s];
  });
}

function set_dismissible_message(success, message){
  message_list = "<div class=\"alert alert-dismissible alert-" + (success ? "success" : "danger")+ " alert-dismissible fade show\" role=\"alert\">";
  message_list += "<strong>" + (success ? "Success" : "Error") + "</strong>: " + message;
  message_list += "<button type=\"button\" class=\"btn-close\" data-dismiss=\"alert\" aria-label=\"Close\" data-bs-dismiss=\"alert\"></button>";
  message_list += "</div>";
  message_list += $('#message_list').html();
  $("#message_list").html(message_list);
}

function retry_download(url, format){
  data = format != null ? {url: url, format: format} : {url: url};
  $.post("api/downloads", data)
    .done(function (data) {
      get_download_logs();
      update_stats();
    });
}

function terminate_job(job_id){
  $.post(`api/jobs/${job_id}/stop`, {})
    .done(function (data) {
    });
}

function pretty_size(size_b) {
  if (size_b == null) {
    return "NaN";
  }
  var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  var i = 0;
  for (i = 0; i < sizes.length; i++) {
    if (size_b < 1024) {
      i++;
      break
    }
    size_b = size_b / 1024;
  }
  return Number((size_b).toFixed(2)) + ' ' + sizes[i - 1];
}

function extractors_show() {
  $.getJSON("api/extractors", function (data) {
    var items = '<ul>';
    $('#extractors_title').text('Available extrators');
    for (var i = 0; i < data.length; i++) {
      items += '<li>' + data[i] + '</li>';
    }
    items += '</ul>';
    $('#extractors_items').html(items);
    $('#extractors_modal').modal('show');
  });
}

function metadata_show(metadata) {
  var items = "";
  $('#metadata_title').text(metadata['title']);
  $('#md_title').text(metadata['title']);
  $('#md_uploader').text(metadata['uploader']);
  $('#md_webpage_url').text(metadata['webpage_url']);
  $('#md_webpage_url').attr('href', metadata['webpage_url']);
  if ('_type' in metadata && metadata['_type'] === 'playlist') {
    $('#md_dialog').attr('class', 'modal-dialog modal-lg')
    $('#md_items_title').text("Playlist items:");
    items = '<ul class="list-group">';
    for (var i = 0; i < metadata['entries'].length; i++) {
      items += '<li class="list-group-item">' + metadata['entries'][i]['title'] + '</li>';
    }
    items += '</ul>';
  }
  else {
    $('#md_dialog').attr('class', 'modal-dialog')
    $('#md_items_title').text("Available formats:");
    for (var i = 0; i < metadata['formats'].length; i++) {
      fmt = metadata['formats'][i];
      items += '<a target="_blank" href="' + fmt['url'] + '">' + fmt['ext'] + ' ' + fmt['format'] + ' - (' + pretty_size(fmt['filesize']) + ')</a><br/>';
    }
  }
  $('#md_items').html(items);
  $('#metadata_modal').modal('show');
}

function submit_video(){
  if ($('#format').val() != 'metadata'){
    data = {url: $("#url").val(),format: $("#format").val()};
    $.post("api/downloads", data)
      .done(function (data) {
        set_dismissible_message(data.success, data.success ? (escapeHtml($("#url").val()) + " added to the list.") : data.error);
        $("#url").val("");
        update_stats();
      })
      .fail(function() {
        set_dismissible_message(false, 'Could not add the url to the queue.');
      });
  }
  else {
    data = {url: $("#url").val()};
    $.post("api/metadata", data)
      .done(function (data) {
        metadata_show(data);
      })
      .fail(function() {
        set_dismissible_message(false, 'Could not gather metadata for this video.');
      });
  }
}

function update_stats(){
  $.getJSON("api/downloads/stats", function (data) {
    var stats = data.stats;
    var queue_pending_val = stats.queue === stats.pending ? stats.queue : stats.queue + '|' + stats.pending;

    $("#queue_pending_size").html(queue_pending_val);
    $("#running_size").html(stats.running);
    $("#completed_size").html(stats.completed);
    $("#failed_size").html(stats.failed);
  });
}

function purge_download_logs(){
  $.ajax({
    url: 'api/downloads',
    type: 'DELETE',
    success: function(data) {
      get_download_logs();
      update_stats();
    }
  });
}

var statusToTrClass = {
  Pending: 'badge',
  Failed: 'badge bg-danger',
  Aborted: 'badge bg-warning',
  Running: 'badge bg-info',
  Completed: 'badge bg-success'
}

function get_download_logs(){
  $.getJSON("api/downloads", function (data) {
    var download_logs = "";
    $.each(data, function(key, row) {
      download_logs += "<tr>";
      download_logs += "<td>" + row.last_update + "</td>";
      download_logs += "<td>" + row.name + "</td>";
      download_logs += "<td>" + (row.format != null ? row.format : "") + "</td>";
      if ((row.status === 'Failed' || row.status === 'Aborted') && row.type != 1) {
        format = row.format != null ? "'" + row.format +"'" : "null";
        download_logs += "<td> <a href=\"#\" onclick=\"retry_download('" + row.url + "'," + format + ")\" class='" + statusToTrClass[row.status] + "'>" + row.status + " / Retry</a></td>";
      } else if ((row.status === 'Running' || row.status === 'Pending') && row.type != 1) {
        download_logs += "<td> <span class='" + statusToTrClass[row.status] + "'>" + row.status + ` <a role="button" aria-label="Abort" onclick="terminate_job(${row.id})">&times;</a></span></td>`;
      } else {
        download_logs += "<td> <span class='" + statusToTrClass[row.status] + "'>" + row.status + "</span></td>";
      }
      download_logs += "<td style='text-align: left;'>" + row.log.replace(/\n|\r/g, '<br/>') + "</td>";
      download_logs += "</tr>";
    });
    $("#job_logs").html(download_logs);
    var visible = $("th:nth-child(5)").is(":visible");
    if (!visible) {
      hide_logs_detail();
    }
  });
}

function hide_logs_detail(){
  $('td:nth-child(5),th:nth-child(5)').hide();
}

function show_logs_detail(){
  $('td:nth-child(5),th:nth-child(5)').show();
}

function toggle_hide_logs_detail(){
  if ($("th:nth-child(5)").is(":visible")) {
    hide_logs_detail();
    $("#toggle_log_button").text("Show Logs");
  }
  else {
    show_logs_detail();
    $("#toggle_log_button").text("Hide Logs");
  }
}

function bookmarklet(){
  url = window.location.protocol + '//' + window.location.hostname
  if (window.location.port != '') {
    url = url + ':' + window.location.port;
  }
  if (window.location.protocol == 'https:') {
    $("#bookmarklet").attr("href", "javascript:fetch(\"" + url
      + "/api/downloads\",{body:new URLSearchParams({url:window.location.href}),method:\"POST\"});");
  }
  else {
    $("#bookmarklet").attr("href", "javascript:(function(){document.body.innerHTML += '<form name=\"ydl_form\" method=\"POST\" action=\""
      + url
      + "/api/downloads\"><input name=\"url\" type=\"url\" value=\"'+window.location.href+'\"/></form>';document.ydl_form.submit()})();");
  }
}

$('#url').keypress(function (e) {
  if (e.which == 13) {
    submit_video();
    update_stats();
    return false;
  }
});

function delete_finished_file(fname){
  $.ajax({
    url: 'api/finished/' + fname,
    type: 'DELETE',
    success: function(data) {
      location.reload(); 
    }
  });
}

bookmarklet();
