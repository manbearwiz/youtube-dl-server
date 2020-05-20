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
  message_list = "<div class=\"alert alert-" + (success ? "success" : "danger")+ " alert-dismissible fade show\" role=\"alert\">";
  message_list += "<strong>" + (success ? "Success" : "Error") + "</strong>: " + message;
  message_list += "<button type=\"button\" class=\"close\" data-dismiss=\"alert\" aria-label=\"Close\"><span aria-hidden=\"true\">&times;</span></button>";
  message_list += "</div>";
  message_list += $('#message_list').html();
  $("#message_list").html(message_list);
}

function retry_download(url, format){
  data = {url: url,format: format};
  $.post("api/downloads", data)
    .done(function (data) {
      get_download_logs();
      update_stats();
    });
}

function submit_video(){
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
  Failed: 'badge badge-danger',
  Running: 'badge badge-info',
  Completed: 'badge badge-success'
}

function get_download_logs(){
  $.getJSON("api/downloads", function (data) {
    var download_logs = "";
    $.each(data, function(key, row) {
      download_logs += "<tr>";
      download_logs += "<td>" + row.last_update + "</td>";
      download_logs += "<td>" + row.name + "</td>";
      download_logs += "<td>" + (row.format ? row.format : "") + "</td>";
      if (row.status == 'Failed' && row.type != 1)
        download_logs += "<td> <a href=\"#\" onclick=\"retry_download('" + row.name + "','" + row.format + "')\" class='" + statusToTrClass[row.status] + "'>" + row.status + " / Retry</a></td>";
      else
        download_logs += "<td> <span class='" + statusToTrClass[row.status] + "'>" + row.status + "</span></td>";
      download_logs += "<td style='text-align: left;'>" + row.log.replace(/\n|\r/g, '<br/>') + "</td>";
      download_logs += "</tr>";
    });
    var visible = $("td:nth-child(5)").is(":visible");
    $("#job_logs").html(download_logs);
    if (!visible) {
      hide_logs_detail();
    }
  });
}

function get_finished_files(){
  $.getJSON("api/finished", function (data) {
    let finished_files = "";
    $.each(data.files, function(key, file) {
      finished_files += "<tr>";
      if (file.children.length > 0) {
        finished_files += "<td><a role=\"button\" href=\"#dir" + key + "\" data-toggle=\"collapse\" aria-expanded=\"false\" aria-controls=\"dir" + key + "\">" + file.name + "</a>";
        finished_files += "<div class=\"collapse\" id=\"dir" + key + "\"><table class=\"col-md-16 table table-stripped table-md table-dark text-left\">";
        $.each(file.children, function(child_key, child_file) {
          finished_files += "<tr><td><a href=\"api/finished/" + encodeURIComponent(file.name + "/" + child_file.name)+ "\" >" + child_file.name + "</a></td><td>" + (new Date(child_file.modified)).toISOString() + "</td></tr>";
        });
        finished_files += "</table></div></td>";
      }
      else {
        finished_files += "<td><a href=\"api/finished/" + encodeURIComponent(file.name) + "\">" + file.name + "</a></td>";
      }
      finished_files += "<td>" + (new Date(file.modified)).toISOString() + "</td>";
      finished_files += "</tr>";
    });
    $("#finished_files").html(finished_files);
  });
}

function ydl_update(){
  $.get("api/youtube-dl/update");
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
  }
  else {
    show_logs_detail();
  }
}

$('#url').keypress(function (e) {
  if (e.which == 13) {
    submit_video();
    update_stats();
    return false;
  }
});
