function set_dismissible_message(result_data){
  success = result_data.success;
  message_list = $('#message_list').html();
  message_list += "<div class=\"alert alert-" + (success ? "success" : "danger")+ " alert-dismissible fade show\" role=\"alert\">";
  message_list += "<strong>" + (success ? "Success" : "Error") + "</strong>: " + (success ? "Link added to the list" : result_data.error) +".";
  message_list += "<button type=\"button\" class=\"close\" data-dismiss=\"alert\" aria-label=\"Close\"><span aria-hidden=\"true\">&times;</span></button>";
  message_list += "</div>";
  $("#message_list").html(message_list);
}

function submit_video(){
  data = {url: $("#url").val(),format: $("#format").val()};
  $.post("/downloads", data)
    .done(function (data) {
      set_dismissible_message(data);
    })
    .fail(function() {
      set_dismissible_message({'success': false, 'error': 'Could not add the url to the queue'});
  });
}

$('#url').keypress(function (e) {
  if (e.which == 13) {
    submit_video();
    return false;
  }
});
