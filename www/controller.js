$(document).ready(function () {
  let activeConversationId = null;

  function escapeHtml(value) {
    return $("<div>")
      .text(String(value ?? ""))
      .html();
  }


  function formatHistoryDate(timestamp) {
    if (!timestamp) {
      return "";
    }

    try {
      const date = new Date(timestamp);

      if (Number.isNaN(date.getTime())) {
        return "";
      }

      return date.toLocaleDateString(
        undefined,
        {
          day: "numeric",
          month: "short",
          year: "numeric",
        }
      );
    } catch (e) {
      return "";
    }
  }


  function renderConversationHistory(conversations) {
    const history =
      document.getElementById(
        "conversation-history"
      );

    if (!history) {
      return;
    }

    history.innerHTML = "";

    if (
      !conversations ||
      conversations.length === 0
    ) {
      history.innerHTML = `
        <div class="history-empty">
          <i class="bi bi-chat-square-text"></i>

          <strong>No saved conversations</strong>

          <span>
            Your conversations will appear here.
          </span>
        </div>
      `;

      return;
    }

    conversations.forEach(
      (conversation) => {
        const item =
          document.createElement("button");

        item.type = "button";

        item.className =
          "conversation-history-item";

        item.dataset.conversationId =
          conversation.conversation_id;

        const title =
          conversation.title ||
          "Untitled conversation";

        const date =
          formatHistoryDate(
            conversation.updated_at ||
            conversation.created_at
          );

        const count =
          Number(
            conversation.message_count || 0
          );

        item.innerHTML = `
          <span class="conversation-history-icon">
            <i class="bi bi-chat-left-text"></i>
          </span>

          <span class="conversation-history-content">
            <strong>
              ${escapeHtml(title)}
            </strong>

            <span>
              ${count} message${count === 1 ? "" : "s"}
              ${date ? ` · ${escapeHtml(date)}` : ""}
            </span>
          </span>

          <i
            class="bi bi-chevron-right conversation-history-arrow"
          ></i>
        `;

        if (
          conversation.conversation_id ===
          activeConversationId
        ) {
          item.classList.add(
            "active"
          );
        }

        item.addEventListener(
          "click",
          () => {
            loadConversationFromHistory(
              conversation.conversation_id,
              title
            );
          }
        );

        history.appendChild(item);
      }
    );
  }


  async function refreshConversationHistory() {
    try {
      const result =
        await eel.getConversationHistory(20)();

      renderConversationHistory(
        result || []
      );
    } catch (e) {
      console.error(
        "Conversation history loading failed:",
        e
      );

      const history =
        document.getElementById(
          "conversation-history"
        );

      if (history) {
        history.innerHTML = `
          <div class="history-empty history-error">
            <i class="bi bi-exclamation-triangle"></i>

            <strong>
              Unable to load history
            </strong>

            <span>
              Check MongoDB connection.
            </span>
          </div>
        `;
      }
    }
  }


  async function loadConversationFromHistory(
    conversationId,
    title
  ) {
    if (!conversationId) {
      return;
    }

    try {
      const result =
        await eel.loadConversation(
          conversationId
        )();

      if (
        !result ||
        !result.success
      ) {
        console.error(
          "Failed to load conversation."
        );

        return;
      }

      activeConversationId =
        conversationId;

      renderLoadedConversation(
        result.messages || []
      );

      if (
        typeof window.openConversationViewer ===
        "function"
      ) {
        window.openConversationViewer(
          title || "Conversation"
        );
      }

      if (
        typeof window.closeHistorySidebar ===
        "function"
      ) {
        window.closeHistorySidebar();
      }

    } catch (e) {
      console.error(
        "Conversation loading failed:",
        e
      );
    }
  }


  function renderLoadedConversation(
    messages
  ) {
    const targets = [
      document.getElementById(
        "chat-canvas-body"
      ),

      document.getElementById(
        "ConversationViewerBody"
      ),
    ].filter(Boolean);

    targets.forEach(
      (target) => {
        target.innerHTML = "";
      }
    );

    messages.forEach(
      (message) => {

        targets.forEach(
          (target) => {

            if (
              message.role === "user"
            ) {
              appendHistoricalUserMessage(
                message.content,
                target
              );

            } else if (
              message.role === "assistant"
            ) {
              appendHistoricalAssistantMessage(
                message.content,
                target
              );
            }

          }
        );
      }
    );

    targets.forEach(
      (target) => {
        target.scrollTop =
          target.scrollHeight;
      }
    );
  }


  function appendHistoricalUserMessage(
    message,
    target
  ) {
    if (!target) {
      return;
    }

    const row =
      document.createElement("div");

    row.className =
      "row justify-content-end mb-4";

    const width =
      document.createElement("div");

    width.className =
      "width-size";

    const bubble =
      document.createElement("div");

    bubble.className =
      "sender_message";

    bubble.textContent =
      String(message || "");

    width.appendChild(
      bubble
    );

    row.appendChild(
      width
    );

    target.appendChild(
      row
    );
  }


  function appendHistoricalAssistantMessage(
    message,
    target
  ) {
    if (!target) {
      return;
    }

    const row =
      document.createElement("div");

    row.className =
      "row justify-content-start mb-4";

    const width =
      document.createElement("div");

    width.className =
      "width-size";

    width.style.maxWidth =
      "100%";

    const card =
      document.createElement("article");

    card.className =
      "jarvis-response-card";

    const header =
      document.createElement("div");

    header.className =
      "jarvis-response-header";

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
    `;

    const body =
      document.createElement("div");

    body.className =
      "jarvis-response-body";

    if (
      window.marked &&
      window.DOMPurify
    ) {

      const html =
        window.marked.parse(
          String(message || ""),
          {
            gfm: true,
            breaks: true,
          }
        );

      body.innerHTML =
        window.DOMPurify.sanitize(
          html
        );

    } else {
      body.textContent =
        String(message || "");
    }

    card.appendChild(
      header
    );

    card.appendChild(
      body
    );

    width.appendChild(
      card
    );

    row.appendChild(
      width
    );

    target.appendChild(
      row
    );

    enhanceCodeBlocks(
      body
    );
  }

  $("#NewConversationBtn").on(
    "click",
    async function () {
      try {
        const result =
          await eel.startNewConversation()();

        if (
          !result ||
          !result.success
        ) {
          console.error(
            "Unable to create new conversation."
          );

          return;
        }

        const chatBox =
          document.getElementById(
            "chat-canvas-body"
          );

        if (chatBox) {
          chatBox.innerHTML = "";
        }

        const viewerBody =
          document.getElementById(
            "ConversationViewerBody"
          );

        if (viewerBody) {
          viewerBody.innerHTML = "";
        }

        activeConversationId =
          result.conversation_id;

        if (
          typeof window.closeConversationViewer ===
          "function"
        ) {
          window.closeConversationViewer();
        }

        await refreshConversationHistory();

        console.log(
          "New conversation:",
          result.conversation_id
        );

      } catch (e) {
        console.error(
          "New conversation error:",
          e
        );
      }
    }
  );


  // Define handlers first, then expose them to Python via eel.expose.
  // This ensures the visual hood updates (big-screen) as well as chat (offcanvas).

  function DisplayMessage(message) {
    try {
      // Update big hood message area (visible on main screen)
      if (message && message.trim() !== "") {
        $("#WishMessage").text(message);

        // Also update siri-message container so textillate/animation picks it up
        $(".siri-message").text(message);

        // Restart textillate if initialized
        try {
          $(".siri-message").textillate("start");
        } catch (e) { }
      }
    } catch (e) {
      console.error("DisplayMessage error:", e);
    }
  }

  // Expose after definition
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
        chatBox.innerHTML += `
          <div class="row justify-content-end mb-4">
            <div class="width-size">
              <div class="sender_message">
                ${$("<div>").text(message).html()}
              </div>
            </div>
          </div>`;

        chatBox.scrollTop = chatBox.scrollHeight;
      }

      // Also show a short transient message on the hood
      try {
        const hood = $("#JarvisHood");

        if (hood.length) {
          const t = $(
            `<div class="hood-transient sender-transient">
              ${$("<div>").text(message).html()}
            </div>`
          );

          hood.prepend(t);

          setTimeout(
            () => t.fadeOut(400, () => t.remove()),
            3000
          );
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
      if (
        navigator.clipboard &&
        navigator.clipboard.writeText
      ) {
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

      button.addEventListener(
        "click",
        async () => {
          const success =
            await copyTextToClipboard(
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
        }
      );

      pre.appendChild(button);
    });
  }


  function assistantResponse(message) {
    try {
      const chatBox =
        document.getElementById(
          "chat-canvas-body"
        );

      if (!chatBox || !message) {
        return;
      }


      // =========================================================
      // CHAT PANEL RESPONSE
      // =========================================================

      const row =
        document.createElement("div");

      row.className =
        "row justify-content-start mb-4";


      const width =
        document.createElement("div");

      width.className =
        "width-size";


      const card =
        document.createElement("article");

      card.className =
        "jarvis-response-card";


      const header =
        document.createElement("div");

      header.className =
        "jarvis-response-header";


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


      const body =
        document.createElement("div");

      body.className =
        "jarvis-response-body";


      // Render Markdown safely
      if (
        window.marked &&
        window.DOMPurify
      ) {
        const html =
          window.marked.parse(
            String(message),
            {
              gfm: true,
              breaks: true
            }
          );

        body.innerHTML =
          window.DOMPurify.sanitize(
            html
          );

      } else {
        // Safe fallback if Markdown libraries
        // are unavailable
        body.textContent =
          String(message);
      }


      const footer =
        document.createElement("div");

      footer.className =
        "jarvis-response-footer";


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


      // Chat response copy button
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


      // =========================================================
      // MAIN JARVIS HUD RESPONSE
      // =========================================================

      try {
        const hoodResponse =
          document.getElementById(
            "HoodResponse"
          );

        const hoodResponseBody =
          document.getElementById(
            "HoodResponseBody"
          );

        const hoodCopyButton =
          document.getElementById(
            "HoodResponseCopy"
          );

        const hoodCard =
          document.getElementById(
            "HoodResponseCard"
          );


        if (
          hoodResponse &&
          hoodResponseBody
        ) {

          // Render Markdown safely
          if (
            window.marked &&
            window.DOMPurify
          ) {
            const hoodHtml =
              window.marked.parse(
                String(message),
                {
                  gfm: true,
                  breaks: true
                }
              );

            hoodResponseBody.innerHTML =
              window.DOMPurify.sanitize(
                hoodHtml
              );

          } else {
            // Safe fallback
            hoodResponseBody.textContent =
              String(message);
          }


          // Reveal the HUD response panel
          hoodResponse.hidden = false;


          // Replace the SiriWave processing view with the response view.
          $("#SiriWave .siri-message").hide();
          $("#SiriWave #siri-container").hide();


          // Restart response animation
          if (hoodCard) {

            hoodCard.classList.remove(
              "hood-response-refresh"
            );

            // Force browser reflow so the
            // animation can replay
            void hoodCard.offsetWidth;

            hoodCard.classList.add(
              "hood-response-refresh"
            );
          }


          // Add Copy buttons to code blocks
          enhanceCodeBlocks(
            hoodResponseBody
          );


          // Main HUD Copy button
          if (hoodCopyButton) {

            // Replace the previous handler
            // instead of stacking handlers
            hoodCopyButton.onclick =
              async function () {

                const success =
                  await copyTextToClipboard(
                    String(message)
                  );

                if (success) {

                  hoodCopyButton.innerHTML =
                    '<i class="bi bi-check2"></i> Copied';

                  setTimeout(() => {
                    hoodCopyButton.innerHTML =
                      '<i class="bi bi-copy"></i> Copy';
                  }, 1600);
                }
              };
          }

        } else {
          console.warn(
            "HUD response elements not found. " +
            "Check HoodResponse, HoodResponseBody, " +
            "HoodResponseCard, and HoodResponseCopy " +
            "in index.html."
          );
        }

      } catch (e) {
        console.error(
          "HUD response rendering error:",
          e
        );
      }


    } catch (e) {

      console.error(
        "assistantResponse error:",
        e
      );

      // Guaranteed fallback
      receiverText(message);
    }
  }

  eel.expose(assistantResponse);


  function receiverText(message) {
    try {
      var chatBox =
        document.getElementById(
          "chat-canvas-body"
        );

      if (
        message &&
        message.trim() !== ""
      ) {

        chatBox.innerHTML += `
          <div class="row justify-content-start mb-4">
            <div class="width-size">
              <div class="receiver_message">
                ${$("<div>")
            .text(message)
            .html()}
              </div>
            </div>
          </div>`;

        chatBox.scrollTop =
          chatBox.scrollHeight;
      }


      // Mirror assistant response to the big
      // hood area
      try {

        if (
          message &&
          message.trim() !== ""
        ) {

          // Update both main wish message
          // and siri-message animation
          $("#WishMessage").text(
            message
          );

          $(".siri-message").text(
            message
          );

          try {
            $(".siri-message").textillate(
              "start"
            );
          } catch (e) { }


          const hood =
            $("#JarvisHood");


          if (hood.length) {

            const t = $(
              `<div class="hood-transient receiver-transient">
                ${$("<div>")
                .text(message)
                .html()}
              </div>`
            );

            hood.prepend(t);


            setTimeout(
              () =>
                t.fadeOut(
                  400,
                  () => t.remove()
                ),
              5000
            );
          }
        }

      } catch (e) { }

    } catch (e) {
      console.error(
        "receiverText error:",
        e
      );
    }
  }

  eel.expose(receiverText);


  // =========================================================
  // FACE AUTH / LOADER
  // =========================================================

  // Hide Loader and display Face Auth animation
  function hideLoader() {
    try {
      $("#Loader").attr(
        "hidden",
        true
      );

      $("#FaceAuth").attr(
        "hidden",
        false
      );

    } catch (e) {
      console.error(
        "hideLoader error:",
        e
      );
    }
  }

  eel.expose(hideLoader);


  // =========================================================
  // REAL-TIME WEBCAM
  // =========================================================

  function updateWebcamFrame(
    jpgBase64,
    status,
    score
  ) {

    try {

      const image =
        document.getElementById(
          "WebcamImage"
        );

      const statusElement =
        document.getElementById(
          "WebcamStatus"
        );


      if (!image) {
        return;
      }


      if (jpgBase64) {

        image.src =
          "data:image/jpeg;base64," +
          jpgBase64;
      }


      if (statusElement) {

        if (
          score !== null &&
          score !== undefined
        ) {

          statusElement.textContent =
            status +
            " | Similarity: " +
            Number(score).toFixed(3);

        } else {

          statusElement.textContent =
            status ||
            "Scanning...";
        }
      }

    } catch (error) {

      console.error(
        "updateWebcamFrame error:",
        error
      );
    }
  }

  eel.expose(
    updateWebcamFrame
  );


  // =========================================================
  // FACE AUTH SUCCESS
  // =========================================================

  // Hide Face auth and display Face Auth success animation
  function hideFaceAuth() {

    try {

      $("#FaceAuth").attr(
        "hidden",
        true
      );

      $("#FaceAuthSuccess").attr(
        "hidden",
        false
      );

    } catch (e) {

      console.error(
        "hideFaceAuth error:",
        e
      );
    }
  }

  eel.expose(
    hideFaceAuth
  );


  // Hide success and display
  function hideFaceAuthSuccess() {

    try {

      $("#FaceAuthSuccess").attr(
        "hidden",
        true
      );

      $("#HelloGreet").attr(
        "hidden",
        false
      );

    } catch (e) {

      console.error(
        "hideFaceAuthSuccess error:",
        e
      );
    }
  }

  eel.expose(
    hideFaceAuthSuccess
  );


  // Hide Start Page and display blob
  function hideStart() {

    try {

      $("#Start").attr(
        "hidden",
        true
      );


      setTimeout(
        function () {

          $("#Oval").addClass(
            "animate__animated animate__zoomIn"
          );

        },
        1000
      );


      setTimeout(
        function () {

          $("#Oval").attr(
            "hidden",
            false
          );

        },
        1000
      );

    } catch (e) {

      console.error(
        "hideStart error:",
        e
      );
    }
  }

  eel.expose(
    hideStart
  );


  // =========================================================
  // VOICE AUTH FALLBACK
  // =========================================================

  // Show a "Try Again" button for voice fallback
  function showTryAgain() {

    try {

      // Ensure we don't add multiple buttons
      if (
        $("#tryAgainBtn").length
      ) {
        return;
      }


      // Place the button below the main
      // wish/message container
      const target =
        $("#WishMessage");


      if (!target.length) {
        return;
      }


      const container =
        target.closest(
          ".d-flex"
        ) ||
        target.parent();


      const btn = $(
        `<div
          id="tryAgainContainer"
          class="text-center mt-3 w-100"
        >
          <button
            id="tryAgainBtn"
            class="btn btn-outline-light btn-lg"
          >
            Try Again
          </button>
        </div>`
      );


      // Insert after the entire container
      // so the button appears on its own row
      container.after(
        btn
      );


      $("#tryAgainBtn").on(
        "click",
        function () {

          // Call back into Python to retry
          // voice authentication
          try {

            eel.retryVoiceAuth()();

          } catch (e) {

            console.error(
              "Failed to call retryVoiceAuth",
              e
            );
          }
        }
      );

    } catch (e) {

      console.error(
        "showTryAgain error:",
        e
      );
    }
  }

  eel.expose(
    showTryAgain
  );


  function hideTryAgain() {

    try {

      $("#tryAgainContainer").remove();

    } catch (e) {

      console.error(
        "hideTryAgain error:",
        e
      );
    }
  }

  eel.expose(
    hideTryAgain
  );

  refreshConversationHistory();
});