$(document).ready(function () {

    const chatButton =
        document.getElementById("ChatBtn");

    const historyPeek =
        document.getElementById("HistoryPeek");

    let historyPeekTimer = null;


    function showHistoryPeek() {
        if (
            !historyPeek ||
            document.body.classList.contains(
                "history-open"
            )
        ) {
            return;
        }

        clearTimeout(historyPeekTimer);

        historyPeek.classList.add(
            "is-visible"
        );

        historyPeek.setAttribute(
            "aria-hidden",
            "false"
        );
    }


    function hideHistoryPeekDelayed() {
        clearTimeout(historyPeekTimer);

        historyPeekTimer = setTimeout(
            () => {
                if (
                    historyPeek &&
                    !historyPeek.matches(":hover") &&
                    !chatButton.matches(":hover")
                ) {
                    historyPeek.classList.remove(
                        "is-visible"
                    );

                    historyPeek.setAttribute(
                        "aria-hidden",
                        "true"
                    );
                }
            },
            180
        );
    }


    if (chatButton) {
        chatButton.addEventListener(
            "mouseenter",
            showHistoryPeek
        );

        chatButton.addEventListener(
            "mouseleave",
            hideHistoryPeekDelayed
        );
    }


    if (historyPeek) {
        historyPeek.addEventListener(
            "mouseenter",
            showHistoryPeek
        );

        historyPeek.addEventListener(
            "mouseleave",
            hideHistoryPeekDelayed
        );
    }

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


    /* =========================================================
       HISTORY SIDEBAR
       ========================================================= */

    function openHistorySidebar() {
        const sidebar =
            document.getElementById("HistorySidebar");

        const backdrop =
            document.getElementById("HistoryBackdrop");

        if (!sidebar || !backdrop) {
            return;
        }

        document.body.classList.add("history-open");

        sidebar.classList.add("is-open");
        backdrop.classList.add("is-visible");

        sidebar.setAttribute(
            "aria-hidden",
            "false"
        );

        backdrop.setAttribute(
            "aria-hidden",
            "false"
        );

        if (
            typeof window.refreshConversationHistory ===
            "function"
        ) {
            window.refreshConversationHistory();
        }
    }


    function closeHistorySidebar() {
        const sidebar =
            document.getElementById("HistorySidebar");

        const backdrop =
            document.getElementById("HistoryBackdrop");

        if (!sidebar || !backdrop) {
            return;
        }

        document.body.classList.remove(
            "history-open"
        );

        sidebar.classList.remove("is-open");
        backdrop.classList.remove("is-visible");

        sidebar.setAttribute(
            "aria-hidden",
            "true"
        );

        backdrop.setAttribute(
            "aria-hidden",
            "true"
        );
    }


    function toggleHistorySidebar() {
        const sidebar =
            document.getElementById("HistorySidebar");

        if (
            sidebar &&
            sidebar.classList.contains("is-open")
        ) {
            closeHistorySidebar();
        } else {
            openHistorySidebar();
        }
    }


    window.openHistorySidebar =
        openHistorySidebar;

    window.closeHistorySidebar =
        closeHistorySidebar;


    $("#ChatBtn").on(
        "click",
        function () {
            toggleHistorySidebar();
        }
    );


    $("#HistoryCloseBtn").on(
        "click",
        function () {
            closeHistorySidebar();
        }
    );


    $("#HistoryBackdrop").on(
        "click",
        function () {
            closeHistorySidebar();
        }
    );


    /* =========================================================
       CONVERSATION VIEWER
       ========================================================= */

    function openConversationViewer(title) {
        const viewer =
            document.getElementById(
                "ConversationViewer"
            );

        const titleElement =
            document.getElementById(
                "ConversationViewerTitle"
            );

        if (!viewer) {
            return;
        }

        if (titleElement) {
            titleElement.textContent =
                title || "Conversation";
        }

        const oval =
            document.getElementById("Oval");

        if (oval) {
            oval.classList.add(
                "conversation-mode"
            );
        }

        viewer.classList.add(
            "is-visible"
        );

        viewer.setAttribute(
            "aria-hidden",
            "false"
        );
    }


    function closeConversationViewer() {
        const viewer =
            document.getElementById(
                "ConversationViewer"
            );

        if (!viewer) {
            return;
        }

        const oval =
            document.getElementById("Oval");

        if (oval) {
            oval.classList.remove(
                "conversation-mode"
            );
        }

        viewer.classList.remove(
            "is-visible"
        );

        viewer.setAttribute(
            "aria-hidden",
            "true"
        );
    }


    window.openConversationViewer =
        openConversationViewer;

    window.closeConversationViewer =
        closeConversationViewer;


    $("#ConversationViewerClose").on(
        "click",
        function () {
            closeConversationViewer();
        }
    );


    $(document).on(
        "keydown",
        function (event) {

            if (event.key !== "Escape") {
                return;
            }

            const sidebar =
                document.getElementById(
                    "HistorySidebar"
                );

            if (
                sidebar &&
                sidebar.classList.contains("is-open")
            ) {
                closeHistorySidebar();
                return;
            }

            const viewer =
                document.getElementById(
                    "ConversationViewer"
                );

            if (
                viewer &&
                viewer.classList.contains("is-visible")
            ) {
                closeConversationViewer();
            }
        }
    );


    /* =========================================================
       SIRI WAVE
       ========================================================= */

    eel.init()();


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


    var siriWave = new SiriWave({
        container:
            document.getElementById(
                "siri-container"
            ),
        width: 800,
        height: 200,
        style: "ios9",
        amplitude: 1,
        speed: 0.3,
        autostart: true,
    });


    $(".siri-message").textillate({
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


    /* =========================================================
       MICROPHONE
       ========================================================= */

    $("#MicBtn").click(
        function () {
            eel.playAssistantSound();

            prepareSiriWave();

            eel.allCommands()();
        }
    );


    function doc_keyUp(e) {

        if (
            e.key === "j" &&
            e.metaKey
        ) {
            eel.playAssistantSound();

            prepareSiriWave();

            eel.allCommands()();
        }
    }

    document.addEventListener(
        "keyup",
        doc_keyUp,
        false
    );


    /* =========================================================
       TEXT INPUT
       ========================================================= */

    function PlayAssistant(message) {

        if (message != "") {

            prepareSiriWave();

            eel.allCommands(message);

            $("#chatbox").val("");

            $("#MicBtn").attr(
                "hidden",
                false
            );

            $("#SendBtn").attr(
                "hidden",
                true
            );
        }
    }


    function ShowHideButton(message) {

        if (message.length == 0) {

            $("#MicBtn").attr(
                "hidden",
                false
            );

            $("#SendBtn").attr(
                "hidden",
                true
            );

        } else {

            $("#MicBtn").attr(
                "hidden",
                true
            );

            $("#SendBtn").attr(
                "hidden",
                false
            );
        }
    }


    $("#chatbox").keyup(
        function () {
            let message =
                $("#chatbox").val();

            ShowHideButton(message);
        }
    );


    $("#SendBtn").click(
        function () {
            let message =
                $("#chatbox").val();

            PlayAssistant(message);
        }
    );


    $("#chatbox").keypress(
        function (e) {

            let key = e.which;

            if (key == 13) {

                let message =
                    $("#chatbox").val();

                PlayAssistant(message);
            }
        }
    );

});

$("#ConversationMicBtn").on(
    "click",
    function () {
        eel.playAssistantSound();

        prepareSiriWave();

        eel.allCommands()();
    }
);


$("#ConversationSendBtn").on(
    "click",
    function () {
        const message =
            $("#ConversationChatbox")
                .val()
                .trim();

        if (!message) {
            return;
        }

        eel.allCommands(message);

        $("#ConversationChatbox")
            .val("");
    }
);


$("#ConversationChatbox").on(
    "keypress",
    function (event) {

        if (event.which !== 13) {
            return;
        }

        const message =
            $(this)
                .val()
                .trim();

        if (!message) {
            return;
        }

        eel.allCommands(message);

        $(this).val("");
    }
);