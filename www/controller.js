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
        } catch (e) { }
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
      } catch (e) { }
    } catch (e) {
      console.error("senderText error:", e);
    }
  }
  eel.expose(senderText);

  function isRichAssistantResponse(message) {
    if (!message) {
      return false;
    }

    const text = String(message).trim();

    return (
      text.length >= 180 ||
      /```/.test(text) ||
      /^#{1,6}\s/m.test(text) ||
      /^\s*[-*+]\s/m.test(text) ||
      /^\s*\d+\.\s/m.test(text) ||
      /\|.+\|/.test(text)
    );
  }

  async function copyTextToClipboard(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (e) {
      console.warn("Clipboard API unavailable:", e);
    }

    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
      return true;
    } catch (e) {
      console.error("Clipboard fallback failed:", e);
      return false;
    }
  }

  function enhanceCodeBlocks(container) {
    const codeBlocks = container.querySelectorAll("pre");

    codeBlocks.forEach((pre) => {
      if (pre.querySelector(".jarvis-code-copy")) {
        return;
      }

      const code = pre.querySelector("code");

      if (!code) {
        return;
      }

      const button = document.createElement("button");

      button.className = "jarvis-code-copy";
      button.type = "button";
      button.innerHTML =
        '<i class="bi bi-clipboard"></i> Copy';

      button.addEventListener("click", async () => {
        const success = await copyTextToClipboard(
          code.innerText
        );

        if (success) {
          button.innerHTML =
            '<i class="bi bi-check2"></i> Copied';

          setTimeout(() => {
            button.innerHTML =
              '<i class="bi bi-clipboard"></i> Copy';
          }, 1600);
        }
      });

      pre.appendChild(button);
    });
  }

  function assistantResponse(message) {
    try {
      const chatBox = document.getElementById(
        "chat-canvas-body"
      );

      if (!chatBox || !message) {
        return;
      }

      const row = document.createElement("div");
      row.className =
        "row justify-content-start mb-4";

      const width = document.createElement("div");
      width.className = "width-size";

      const card = document.createElement("article");
      card.className = "jarvis-response-card";

      const header = document.createElement("div");
      header.className = "jarvis-response-header";

      header.innerHTML = `
            <div class="jarvis-response-brand">
                <div class="jarvis-response-icon">
                    <i class="bi bi-stars"></i>
                </div>

                <div class="jarvis-response-title">
                    <strong>JARVIS</strong>
                    <span>AI RESPONSE</span>
                </div>
            </div>

            <button
                type="button"
                class="jarvis-copy-response"
                aria-label="Copy response"
            >
                <i class="bi bi-copy"></i>
                Copy
            </button>
        `;

      const body = document.createElement("div");
      body.className = "jarvis-response-body";

      if (
        window.marked &&
        window.DOMPurify
      ) {
        const html = window.marked.parse(
          String(message),
          {
            gfm: true,
            breaks: true
          }
        );

        body.innerHTML =
          window.DOMPurify.sanitize(html);
      } else {
        body.textContent = String(message);
      }

      const footer = document.createElement("div");
      footer.className = "jarvis-response-footer";

      footer.innerHTML = `
            <span>
                <i class="bi bi-stars"></i>
                JARVIS
            </span>

            <span class="jarvis-response-status">
                Response ready
            </span>
        `;

      card.appendChild(header);
      card.appendChild(body);
      card.appendChild(footer);

      width.appendChild(card);
      row.appendChild(width);

      chatBox.appendChild(row);

      const copyButton =
        header.querySelector(
          ".jarvis-copy-response"
        );

      copyButton.addEventListener(
        "click",
        async () => {
          const success =
            await copyTextToClipboard(
              String(message)
            );

          if (success) {
            copyButton.innerHTML =
              '<i class="bi bi-check2"></i> Copied';

            setTimeout(() => {
              copyButton.innerHTML =
                '<i class="bi bi-copy"></i> Copy';
            }, 1600);
          }
        }
      );

      enhanceCodeBlocks(body);

      chatBox.scrollTop =
        chatBox.scrollHeight;

      // Keep the main HUD clean instead of placing
      // the entire long answer into WishMessage.
      const plainText =
        String(message)
          .replace(/\s+/g, " ")
          .trim();

      const preview =
        plainText.length > 120
          ? plainText.slice(0, 117) + "..."
          : plainText;

      $("#WishMessage").text(preview);
      $(".siri-message").text(
        "Response ready."
      );

      try {
        $(".siri-message").textillate(
          "start"
        );
      } catch (e) { }

      // Small HUD transient notification.
      try {
        const hood =
          $("#JarvisHood");

        if (hood.length) {
          const transient = $(
            `<div class="hood-transient receiver-transient">
                        <div class="hood-response-label">
                            <i class="bi bi-stars"></i>
                            JARVIS RESPONSE READY
                        </div>
                    </div>`
          );

          hood.prepend(transient);

          setTimeout(() => {
            transient.fadeOut(
              400,
              () => transient.remove()
            );
          }, 3500);
        }
      } catch (e) { }

    } catch (e) {
      console.error(
        "assistantResponse error:",
        e
      );

      // Guaranteed fallback.
      receiverText(message);
    }
  }

  eel.expose(assistantResponse);

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
          } catch (e) { }
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
      } catch (e) { }
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

  function updateWebcamFrame(jpgBase64, status, score) {
    try {
      const image = document.getElementById("WebcamImage");
      const statusElement = document.getElementById("WebcamStatus");

      if (!image) {
        return;
      }

      if (jpgBase64) {
        image.src = "data:image/jpeg;base64," + jpgBase64;
      }

      if (statusElement) {
        if (score !== null && score !== undefined) {
          statusElement.textContent =
            status + " | Similarity: " + Number(score).toFixed(3);
        } else {
          statusElement.textContent = status || "Scanning...";
        }
      }

    } catch (error) {
      console.error("updateWebcamFrame error:", error);
    }
  }

  eel.expose(updateWebcamFrame);

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

  // Show a "Try Again" button for voice fallback
  function showTryAgain() {
    try {
      // ensure we don't add multiple buttons
      if ($('#tryAgainBtn').length) return;
      // place the button below the main wish/message container for visibility
      const target = $('#WishMessage');
      if (!target.length) return;
      const container = target.closest('.d-flex') || target.parent();
      const btn = $(
        `<div id="tryAgainContainer" class="text-center mt-3 w-100"><button id="tryAgainBtn" class="btn btn-outline-light btn-lg">Try Again</button></div>`
      );
      // insert after the entire container so the button appears on its own row
      container.after(btn);
      $('#tryAgainBtn').on('click', function () {
        // call back into Python to retry voice auth
        try {
          eel.retryVoiceAuth()();
        } catch (e) {
          console.error('Failed to call retryVoiceAuth', e);
        }
      });
    } catch (e) {
      console.error('showTryAgain error:', e);
    }
  }
  eel.expose(showTryAgain);

  function hideTryAgain() {
    try {
      $('#tryAgainContainer').remove();
    } catch (e) {
      console.error('hideTryAgain error:', e);
    }
  }
  eel.expose(hideTryAgain);

});
