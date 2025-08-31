$(document).ready(function () {
  // Define handlers first, then expose them to Python via eel.expose.
  // This ensures the visual hood updates (big-screen) as well as chat (offcanvas).

  function DisplayMessage(message) {
    try {
      // Update big hood message area (visible on main screen)
      if (message && message.trim() !== "") {
        $("#WishMessage").text(message);
        // also update siri-message container so textillate/animation picks it up
        $(".siri-message").text(message);
        // restart textillate if initialized
        try {
          $(".siri-message").textillate("start");
        } catch (e) {}
      }
    } catch (e) {
      console.error("DisplayMessage error:", e);
    }
  }
  // expose after definition
  eel.expose(DisplayMessage);

  function ShowHood() {
    try {
      $("#Oval").attr("hidden", false);
      $("#SiriWave").attr("hidden", true);
    } catch (e) {
      console.error("ShowHood error:", e);
    }
  }
  eel.expose(ShowHood);

  function senderText(message) {
    try {
      var chatBox = document.getElementById("chat-canvas-body");
      if (message && message.trim() !== "") {
        chatBox.innerHTML += `<div class="row justify-content-end mb-4">
                    <div class = "width-size">
                        <div class = "sender_message">${$("<div>")
                          .text(message)
                          .html()}</div>
                    </div>
                </div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
      }
      // Also show a short transient message on the hood
      try {
        const hood = $("#JarvisHood");
        if (hood.length) {
          const t = $(
            `<div class="hood-transient sender-transient">${$("<div>")
              .text(message)
              .html()}</div>`
          );
          hood.prepend(t);
          setTimeout(() => t.fadeOut(400, () => t.remove()), 3000);
        }
      } catch (e) {}
    } catch (e) {
      console.error("senderText error:", e);
    }
  }
  eel.expose(senderText);

  function receiverText(message) {
    try {
      var chatBox = document.getElementById("chat-canvas-body");
      if (message && message.trim() !== "") {
        chatBox.innerHTML += `<div class="row justify-content-start mb-4">
                    <div class = "width-size ">
                        <div class = "receiver_message"> ${$("<div>")
                          .text(message)
                          .html()} </div>
                    </div>
                </div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
      }
      // Mirror assistant response to the big hood area (so spoken + written appear together)
      try {
        if (message && message.trim() !== "") {
          // Update both the main wish message and siri-message animation
          $("#WishMessage").text(message);
          $(".siri-message").text(message);
          try {
            $(".siri-message").textillate("start");
          } catch (e) {}
          const hood = $("#JarvisHood");
          if (hood.length) {
            const t = $(
              `<div class="hood-transient receiver-transient">${$("<div>")
                .text(message)
                .html()}</div>`
            );
            hood.prepend(t);
            setTimeout(() => t.fadeOut(400, () => t.remove()), 5000);
          }
        }
      } catch (e) {}
    } catch (e) {
      console.error("receiverText error:", e);
    }
  }
  eel.expose(receiverText);

  // Hide Loader and display Face Auth animation
  function hideLoader() {
    try {
      $("#Loader").attr("hidden", true);
      $("#FaceAuth").attr("hidden", false);
    } catch (e) {
      console.error("hideLoader error:", e);
    }
  }
  eel.expose(hideLoader);

  // Hide Face auth and display Face Auth success animation
  function hideFaceAuth() {
    try {
      $("#FaceAuth").attr("hidden", true);
      $("#FaceAuthSuccess").attr("hidden", false);
    } catch (e) {
      console.error("hideFaceAuth error:", e);
    }
  }
  eel.expose(hideFaceAuth);

  // Hide success and display
  function hideFaceAuthSuccess() {
    try {
      $("#FaceAuthSuccess").attr("hidden", true);
      $("#HelloGreet").attr("hidden", false);
    } catch (e) {
      console.error("hideFaceAuthSuccess error:", e);
    }
  }
  eel.expose(hideFaceAuthSuccess);

  // Hide Start Page and display blob
  function hideStart() {
    try {
      $("#Start").attr("hidden", true);
      setTimeout(function () {
        $("#Oval").addClass("animate__animated animate__zoomIn");
      }, 1000);
      setTimeout(function () {
        $("#Oval").attr("hidden", false);
      }, 1000);
    } catch (e) {
      console.error("hideStart error:", e);
    }
  }
  eel.expose(hideStart);

});
