$(document).ready(function () {
    function prepareSiriWave() {
        $("#Oval").attr("hidden", true);
        $("#SiriWave").attr("hidden", false);

        // Hide previous response.
        $("#HoodResponse").attr("hidden", true);

        // Restore the processing UI.
        $("#SiriWave .siri-message").show();
        $("#SiriWave #siri-container").show();
    }

    function ShowSiriWave() {
        prepareSiriWave();
    }

    eel.expose(ShowSiriWave);

    eel.init()()

    $(".text").textillate({
        loop: true,
        sync: true,
        in: {
            effect: "bounceIn",
        },
        out: {
            effect: "bounceOut",
        },
    });

    // Siri Configuration

    var siriWave = new SiriWave({
        container: document.getElementById("siri-container"),
        width: 800,
        height: 200,
        style: "ios9",
        amplitude: 1,
        speed: 0.3,
        autostart: true,
    });

    // Siri Wave Animation
    $('.siri-message').textillate({
        loop: true,
        sync: true,
        in: {
            effect: "fadeInUp",
            sync: true,
        },
        out: {
            effect: "fadeOutUp",
            sync: true,
        },
    });

    // mic button click event

    $("#MicBtn").click(function () {
        eel.playAssistantSound()
        prepareSiriWave();
        eel.allCommands()()
    });

    function doc_keyUp(e) {
        //this would test for whichever key is 40 (down arrow) and the ctrl key at the same time

        if (e.key === 'j' && e.metaKey) {
            eel.playAssistantSound()
            prepareSiriWave();
            eel.allCommands()()
        }
    }
    document.addEventListener('keyup', doc_keyUp, false);

    function PlayAssistant(message) {
        if (message != "") {
            prepareSiriWave();
            eel.allCommands(message);
            $("#chatbox").val("");
            $("#MicBtn").attr("hidden", false);
            $("#SendBtn").attr("hidden", true);
        }
    }

    function ShowHideButton(message) {
        if (message.length == 0) {
            $("#MicBtn").attr("hidden", false);
            $("#SendBtn").attr("hidden", true);
        } else {
            $("#MicBtn").attr("hidden", true);
            $("#SendBtn").attr("hidden", false);
        }
    }

    $("#chatbox").keyup(function () {
        let message = $("#chatbox").val();
        ShowHideButton(message);
    });

    $("#SendBtn").click(function () {
        let message = $("#chatbox").val();
        PlayAssistant(message);
    });

    $("#chatbox").keypress(function (e) {
        key = e.which;
        if (key == 13) {
            let message = $("#chatbox").val()
            PlayAssistant(message);
        }
    });

});