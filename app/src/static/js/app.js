$(document).ready(function () {
  // Toast notification helper
  function showToast(message, type = "success") {
    const $toast = $("#toast");
    $toast.text(message);
    $toast.removeClass("hidden toast-success toast-error").addClass(`toast-${type}`);
    setTimeout(() => {
      $toast.addClass("hidden");
    }, 3500);
  }

  // Copy to clipboard helper
  function copyToClipboard(text, successMsg = "Copiado al portapapeles") {
    if (!text) return;
    navigator.clipboard.writeText(text).then(
      () => showToast(successMsg, "success"),
      () => showToast("Error al copiar", "error")
    );
  }

  // Format short npub
  function formatShortKey(key) {
    if (!key || key.length < 16) return key || "-";
    return key.substring(0, 10) + "..." + key.substring(key.length - 6);
  }

  // Format timestamp
  function formatTimestamp(ts) {
    if (!ts) return "Nunca";
    const date = new Date(ts * 1000);
    return date.toLocaleString();
  }

  // 1. Fetch Bunker Live Status
  function loadBunkerStatus() {
    $.getJSON("/api/bunker/status")
      .done(function (data) {
        // Relay Status Badge & Selection
        const currentRelay = data.current_relay_url || data.relay_external_url;
        const $relayBadge = $("#relay-status-badge");
        const $relayText = $("#relay-status-text");
        if (data.relay_connected) {
          $relayBadge.removeClass("badge-offline").addClass("badge-online");
          $relayText.text(`Relay: Conectado (${currentRelay})`);
        } else {
          $relayBadge.removeClass("badge-online").addClass("badge-offline");
          $relayText.text(`Relay: Desconectado (${currentRelay})`);
        }

        // Sync Relay Dropdown if not currently editing custom
        if (!$("#custom-relay-input").is(":focus")) {
          const $select = $("#relay-select");
          if ($select.find(`option[value="${currentRelay}"]`).length > 0) {
            $select.val(currentRelay);
            $("#custom-relay-input").addClass("hidden");
          } else {
            $select.val("custom");
            $("#custom-relay-input").removeClass("hidden").val(currentRelay);
          }
        }

        // Active Sessions Count
        $("#active-session-count").text(`${data.active_sessions_count} sesiones activas`);

        // Active Identity details
        if (data.active_identity) {
          const id = data.active_identity;
          $("#active-alias").text(id.alias);
          $("#active-npub").text(formatShortKey(id.keys.bech32_npub)).attr("title", id.keys.bech32_npub);
          $("#active-sig-count").text(id.metadata.total_signatures_performed || 0);
          $("#active-last-used").text(formatTimestamp(id.metadata.last_used_timestamp));
        } else {
          $("#active-alias").text("Ninguna");
          $("#active-npub").text("-").removeAttr("title");
          $("#active-sig-count").text("0");
          $("#active-last-used").text("-");
        }

        // Connection String
        $("#bunker-uri-input").val(data.bunker_connection_string || "");
      })
      .fail(function (err) {
        console.error("Error al obtener estado del Bunker:", err);
      });
  }

  // 2. Fetch and render Identities Registry
  function loadIdentities() {
    $.getJSON("/api/identities")
      .done(function (registry) {
        const activeId = registry.active_identity_id;
        const identities = registry.identities || [];
        const $tbody = $("#identities-table-body");
        $tbody.empty();

        if (identities.length === 0) {
          $tbody.append(`
            <tr>
              <td colspan="7" class="text-center" style="padding: 2rem; color: #94a3b8;">
                No hay identidades generadas. Haz clic en <strong>+ Generar Nueva Identidad</strong> para comenzar.
              </td>
            </tr>
          `);
          return;
        }

        identities.forEach(function (item) {
          const isActive = item.id === activeId;
          const statusBadge = isActive
            ? `<span class="badge badge-active">Activa</span>`
            : `<span class="badge" style="color: #64748b;">Inactiva</span>`;

          const actionBtn = isActive
            ? `<button class="btn btn-sm btn-secondary" disabled>En uso</button>`
            : `<button class="btn btn-sm btn-primary btn-switch-identity" data-id="${item.id}" data-alias="${item.alias}">Activar</button>`;

          const npubShort = formatShortKey(item.keys.bech32_npub);
          const npubFull = item.keys.bech32_npub;

          const rowHtml = `
            <tr class="${isActive ? 'row-active' : ''}">
              <td>${statusBadge}</td>
              <td><strong>${item.alias}</strong></td>
              <td>
                <span class="code-font" title="${npubFull}">${npubShort}</span>
                <button class="btn btn-sm btn-secondary btn-copy-npub" data-npub="${npubFull}" style="margin-left: 0.5rem; padding: 0.15rem 0.4rem;">📋</button>
              </td>
              <td>${item.metadata.total_signatures_performed || 0}</td>
              <td>${formatTimestamp(item.metadata.last_used_timestamp)}</td>
              <td>${formatTimestamp(item.metadata.created_timestamp)}</td>
              <td>${actionBtn}</td>
            </tr>
          `;
          $tbody.append(rowHtml);
        });
      })
      .fail(function (err) {
        console.error("Error al cargar identidades:", err);
        showToast("Error al cargar identidades desde disco", "error");
      });
  }

  // 3. Refresh All Data
  function refreshAll() {
    loadBunkerStatus();
    loadIdentities();
  }

  // Event Listeners
  $("#btn-refresh").on("click", function () {
    refreshAll();
    showToast("Datos actualizados");
  });

  $("#btn-copy-bunker").on("click", function () {
    const uri = $("#bunker-uri-input").val();
    if (!uri) {
      showToast("No hay connection string disponible", "error");
      return;
    }
    copyToClipboard(uri, "Connection string copiado al portapapeles");
  });

  $(document).on("click", ".btn-copy-npub", function () {
    const npub = $(this).data("npub");
    copyToClipboard(npub, "npub copiado");
  });

  // Relay selection handlers
  $("#relay-select").on("change", function () {
    const val = $(this).val();
    if (val === "custom") {
      $("#custom-relay-input").removeClass("hidden").focus();
    } else {
      $("#custom-relay-input").addClass("hidden");
    }
  });

  $("#btn-apply-relay").on("click", function () {
    let targetRelay = $("#relay-select").val();
    if (targetRelay === "custom") {
      targetRelay = $("#custom-relay-input").val().trim();
      if (!targetRelay || (!targetRelay.startsWith("wss://") && !targetRelay.startsWith("ws://"))) {
        showToast("Ingresa una URL válida de relay (ws:// o wss://)", "error");
        return;
      }
    }

    const $btn = $(this);
    $btn.prop("disabled", true).text("Cambiando...");

    $.ajax({
      url: "/api/bunker/relay",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ relay_url: targetRelay }),
      success: function (res) {
        showToast(`Relay cambiado a ${targetRelay}. Reanudando oyente.`);
        refreshAll();
      },
      error: function (xhr) {
        const msg = xhr.responseJSON ? xhr.responseJSON.detail : "Error al cambiar relay";
        showToast(msg, "error");
      },
      complete: function () {
        $btn.prop("disabled", false).text("Cambiar Relay");
      }
    });
  });

  // Switch Identity
  $(document).on("click", ".btn-switch-identity", function () {
    const targetId = $(this).data("id");
    const alias = $(this).data("alias");
    const $btn = $(this);
    $btn.prop("disabled", true).text("Activando...");

    $.ajax({
      url: "/api/identities/switch",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ target_identity_id: targetId }),
      success: function (res) {
        showToast(`Identidad conmutada a "${alias}". Sesiones previas invalidadas.`);
        refreshAll();
      },
      error: function (err) {
        showToast("Error al cambiar de identidad", "error");
        $btn.prop("disabled", false).text("Activar");
      }
    });
  });

  // Connect via string
  $("#btn-submit-connect-string").on("click", function () {
    const connStr = $("#connect-string-input").val().trim();
    if (!connStr) {
      showToast("Ingresa un string nostrconnect:// válido", "error");
      return;
    }

    const $btn = $(this);
    $btn.prop("disabled", true).text("Conectando...");

    $.ajax({
      url: "/api/bunker/connect-string",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ connection_string: connStr }),
      success: function (res) {
        showToast(`Conectado exitosamente con cliente: ${formatShortKey(res.client_pubkey)}`);
        $("#connect-string-input").val("");
        refreshAll();
      },
      error: function (xhr) {
        const msg = xhr.responseJSON ? xhr.responseJSON.detail : "Error al conectar";
        showToast(msg, "error");
      },
      complete: function () {
        $btn.prop("disabled", false).text("Conectar");
      }
    });
  });

  // Modal handlers
  $("#btn-open-create-modal").on("click", function () {
    $("#form-create-identity")[0].reset();
    $("#modal-create-identity").removeClass("hidden");
    $("#new-alias").focus();
  });

  $("#btn-close-modal, #btn-cancel-modal").on("click", function () {
    $("#modal-create-identity").addClass("hidden");
  });

  // Form submit: Generate new identity
  $("#form-create-identity").on("submit", function (e) {
    e.preventDefault();
    const alias = $("#new-alias").val().trim();
    const description = $("#new-description").val().trim();

    if (!alias) return;

    const $submitBtn = $(this).find('button[type="submit"]');
    $submitBtn.prop("disabled", true).text("Generando llaves...");

    $.ajax({
      url: "/api/identities/generate",
      type: "POST",
      contentType: "application/json",
      data: JSON.stringify({ alias: alias, description: description }),
      success: function (created) {
        showToast(`Identidad "${created.alias}" generada exitosamente`);
        $("#modal-create-identity").addClass("hidden");
        refreshAll();
      },
      error: function (xhr) {
        const msg = xhr.responseJSON ? xhr.responseJSON.detail : "Error al generar identidad";
        showToast(msg, "error");
      },
      complete: function () {
        $submitBtn.prop("disabled", false).text("Generar Clave");
      }
    });
  });

  // Initial load
  refreshAll();
});

