$(document).ready(function() {
    $(".renew-btn").each(function() {
        $(this).one("click", function(event) {
            var badge = $("<span></span>").attr({
                "class": "spinner-border spinner-border-sm",
                "role": "status",
                "aria-hidden": true
            });
            $(this).empty().attr({
                "class": "btn btn-secondary renew-btn",
                "disabled": true
            }).append(badge);
            var renew_link = $(this).attr("data-renew-url");
            var self = $(this)
            $.ajax({
                type: "get",
                url: renew_link
            }).done(function(responseData) {
                self.removeClass("btn-warning").addClass("btn-success").attr({
                    "disabled": false
                }).text("Renew Success").popover({
                    trigger: "focus",
                    container: "body",
                    placement: "bottom",
                    html: true,
                    content: $("<pre></pre>").text(JSON.stringify(responseData, undefined, 2))
                });
            }).fail(function(responseData, self) {
                self.parent().empty().text(responseData);
            });
        });
    });

    $("#renew-all-btn").one("click", function(){
        $(".renew-btn").click();
    });

    $('.unsubscribe-btn').on('click', function(event) {
        let unsubscribe_btn = $(this);
        let loaded_div = $('<div>').load('static/component/channel_unsubscribe.html', function() {
            let channel_name = unsubscribe_btn.data('channel-name');
            let api_endpoint = unsubscribe_btn.data('api-endpoint');
            $('.modal-body').text(`Are you sure you want to unsubscribe to ${channel_name}?`);
            $('#unsubscribe-modal').modal('show').on('hidden.bs.modal', function(event) {
                loaded_div.remove();
            });
            $('#confirm-btn').on('click', function() {
                $.get(api_endpoint).done(function(data) {
                    if (Boolean(data)) {
                        location.reload();
                    } else {
                        alert('Unsubscribe Failed, Try Again');
                    }
                });
            });
        });
        $('#content-container').append(loaded_div);
    });
});
