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

function set_dismissible_message(result_data){
  success = result_data.success;
  message_list = "<div class=\"alert alert-" + (success ? "success" : "danger")+ " alert-dismissible fade show\" role=\"alert\">";
  message_list += "<strong>" + (success ? "Success" : "Error") + "</strong>: " + (success ? (escapeHtml($("#url").val()) + " added to the list") : result_data.error) +".";
  message_list += "<button type=\"button\" class=\"close\" data-dismiss=\"alert\" aria-label=\"Close\"><span aria-hidden=\"true\">&times;</span></button>";
  message_list += "</div>";
  message_list += $('#message_list').html();
  $("#message_list").html(message_list);
}

function submit_video(){
  data = {url: $("#url").val(),format: $("#format").val()};
  $.post("/api/downloads", data)
    .done(function (data) {
      set_dismissible_message(data);
      $("#url").val("");
    })
    .fail(function() {
      set_dismissible_message({'success': false, 'error': 'Could not add the url to the queue'});
  });
}

function update_queue_size(){
  $.getJSON("/api/downloads/count", function (data) {
    $("#queue_size").html(data.size);
  });
}


$('#url').keypress(function (e) {
  if (e.which == 13) {
    submit_video();
    update_queue_size();
    return false;
  }
});
