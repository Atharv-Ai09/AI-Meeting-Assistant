/* AI Meeting Assistant - front-end logic (home page and results page). */
(function () {
  "use strict";

  // ---------------------------------------------------------------- shared helpers
  function $(id) { return document.getElementById(id); }

  function showAlert(type, message, area) {
    var container = area || $("alertArea");
    if (!container) { return; }
    var div = document.createElement("div");
    div.className = "alert alert-" + type + " alert-dismissible fade show";
    div.setAttribute("role", "alert");
    div.appendChild(document.createTextNode(message));
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("data-bs-dismiss", "alert");
    close.setAttribute("aria-label", "Close");
    div.appendChild(close);
    container.innerHTML = "";
    container.appendChild(div);
    div.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function formatBytes(bytes) {
    if (bytes < 1024 * 1024) { return (bytes / 1024).toFixed(1) + " KB"; }
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatClock(seconds) {
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function extensionOf(name) {
    var i = name.lastIndexOf(".");
    return i === -1 ? "" : name.slice(i + 1).toLowerCase();
  }

  function countWords(text) {
    var t = text.trim();
    return t ? t.split(/\s+/).length : 0;
  }

  // ---------------------------------------------------------------- home page
  function initHome() {
    var cfg = window.APP_CONFIG;
    var dropZone = $("dropZone"), fileInput = $("fileInput"), uploadBtn = $("uploadBtn");
    var recordBtn = $("recordBtn"), stopBtn = $("stopBtn"), clearBtn = $("clearBtn"), processBtn = $("processBtn");
    var previewBox = $("previewBox"), player = $("audioPlayer"), fileInfo = $("fileInfo");
    var recordTimer = $("recordTimer"), recordTime = $("recordTime");

    var currentFile = null, previewUrl = null;
    var recorder = null, stream = null, recordedChunks = [], timerId = null, startedAt = 0;
    var processing = false, elapsedId = null;

    function setFile(file) {
      var ext = extensionOf(file.name);
      if (cfg.extensions.indexOf(ext) === -1) {
        showAlert("danger", "Unsupported file format" + (ext ? " (." + ext + ")" : "") + ". Allowed formats: " + cfg.extensions.join(", ").toUpperCase() + ".");
        return false;
      }
      if (file.size === 0) { showAlert("danger", "The selected audio file is empty."); return false; }
      if (file.size > cfg.maxBytes) { showAlert("danger", "The file is too large. Maximum size is " + cfg.maxMb + " MB."); return false; }
      clearAudio(true);
      currentFile = file;
      previewUrl = URL.createObjectURL(file);
      player.src = previewUrl;
      fileInfo.textContent = file.name + " (" + formatBytes(file.size) + ")";
      previewBox.classList.remove("d-none");
      clearBtn.disabled = false;
      processBtn.disabled = false;
      $("alertArea").innerHTML = "";
      return true;
    }

    function clearAudio(keepAlerts) {
      if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
      currentFile = null;
      player.removeAttribute("src");
      player.load();
      previewBox.classList.add("d-none");
      fileInput.value = "";
      clearBtn.disabled = true;
      processBtn.disabled = true;
      if (!keepAlerts) { $("alertArea").innerHTML = ""; }
    }

    // ---- upload and drag & drop
    uploadBtn.addEventListener("click", function (e) { e.stopPropagation(); fileInput.click(); });
    dropZone.addEventListener("click", function () { fileInput.click(); });
    dropZone.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
    fileInput.addEventListener("change", function () { if (fileInput.files.length) { setFile(fileInput.files[0]); } });
    ["dragenter", "dragover"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) { e.preventDefault(); dropZone.classList.add("dragover"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      dropZone.addEventListener(ev, function (e) { e.preventDefault(); dropZone.classList.remove("dragover"); });
    });
    dropZone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) { setFile(e.dataTransfer.files[0]); }
    });
    clearBtn.addEventListener("click", function () { clearAudio(false); });

    // ---- recording
    function pickMime() {
      var options = [
        ["audio/webm;codecs=opus", "webm"], ["audio/webm", "webm"],
        ["audio/ogg;codecs=opus", "ogg"], ["audio/mp4", "m4a"]
      ];
      if (window.MediaRecorder && MediaRecorder.isTypeSupported) {
        for (var i = 0; i < options.length; i++) {
          if (MediaRecorder.isTypeSupported(options[i][0])) { return options[i]; }
        }
      }
      return ["", "webm"];
    }

    function stopTimer() {
      if (timerId) { clearInterval(timerId); timerId = null; }
      recordTimer.classList.add("d-none");
    }

    recordBtn.addEventListener("click", function () {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
        showAlert("danger", "Recording is not supported in this browser. Please upload an audio file instead.");
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (s) {
        stream = s;
        var chosen = pickMime();
        recordedChunks = [];
        recorder = chosen[0] ? new MediaRecorder(stream, { mimeType: chosen[0] }) : new MediaRecorder(stream);
        recorder.ondataavailable = function (e) { if (e.data && e.data.size) { recordedChunks.push(e.data); } };
        recorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          stopTimer();
          recordBtn.disabled = false;
          stopBtn.disabled = true;
          if (!recordedChunks.length) { showAlert("danger", "Nothing was recorded. Please try again."); return; }
          var type = recorder.mimeType || chosen[0] || "audio/webm";
          var blob = new Blob(recordedChunks, { type: type });
          var stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
          var file = new File([blob], "recording_" + stamp + "." + chosen[1], { type: type });
          if (setFile(file)) { showAlert("success", "Recording saved. Press \"Transcribe & Summarize\" to process it."); }
        };
        recorder.start(1000);
        startedAt = Date.now();
        recordTime.textContent = "0:00";
        recordTimer.classList.remove("d-none");
        timerId = setInterval(function () { recordTime.textContent = formatClock((Date.now() - startedAt) / 1000); }, 500);
        recordBtn.disabled = true;
        stopBtn.disabled = false;
        processBtn.disabled = true;
      }).catch(function (err) {
        var msg = "Could not start recording.";
        if (err && err.name === "NotAllowedError") { msg = "Microphone permission was denied. Allow microphone access and try again."; }
        else if (err && err.name === "NotFoundError") { msg = "No microphone was found on this device."; }
        showAlert("danger", msg);
      });
    });

    stopBtn.addEventListener("click", function () {
      if (recorder && recorder.state !== "inactive") { recorder.stop(); }
    });

    // ---- processing
    function setStatus(title, detail, percent, indeterminate) {
      $("statusBox").classList.remove("d-none");
      $("statusTitle").textContent = title;
      $("statusDetail").textContent = detail || "";
      var bar = $("progressBar");
      bar.style.width = percent + "%";
      bar.classList.toggle("progress-bar-animated", !!indeterminate);
    }

    function setBusy(busy) {
      processing = busy;
      processBtn.disabled = busy || !currentFile;
      recordBtn.disabled = busy;
      uploadBtn.disabled = busy;
      clearBtn.disabled = busy || !currentFile;
    }

    function renderResults(data) {
      var r = data.report;
      $("resFile").textContent = r.filename;
      $("resDuration").textContent = r.duration_text;
      $("resLanguage").textContent = r.language;
      $("resSummary").textContent = r.summary || "A summary is not available.";
      var kp = $("resKeyPoints");
      kp.innerHTML = "";
      if (r.key_points.length) {
        r.key_points.forEach(function (p) { var li = document.createElement("li"); li.textContent = p; kp.appendChild(li); });
      } else {
        var none = document.createElement("li"); none.textContent = "No key discussion points could be extracted."; kp.appendChild(none);
      }
      var actions = $("resActions");
      actions.innerHTML = "";
      if (r.action_items.length) {
        var ul = document.createElement("ul");
        r.action_items.forEach(function (a) {
          var li = document.createElement("li");
          li.textContent = a.task + " (Responsible: " + a.responsible + " | Deadline: " + a.deadline + ")";
          ul.appendChild(li);
        });
        actions.appendChild(ul);
      } else {
        actions.textContent = "No specific action items identified.";
      }
      $("resTranscript").textContent = r.transcript;
      var warn = $("resWarnings");
      warn.innerHTML = "";
      (r.warnings || []).forEach(function (w) {
        var d = document.createElement("div"); d.className = "alert alert-warning mb-2"; d.textContent = w; warn.appendChild(d);
      });
      $("resOpen").href = data.result_url;
      $("dlTranscript").href = data.downloads.transcript;
      $("dlSummary").href = data.downloads.summary;
      $("dlReport").href = data.downloads.report;
      var section = $("resultsSection");
      section.classList.remove("d-none");
      section.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    processBtn.addEventListener("click", function () {
      if (!currentFile || processing) { return; }
      var form = new FormData();
      form.append("audio", currentFile, currentFile.name);
      form.append("whisper_model", $("whisperModel").value);
      form.append("summary_length", $("summaryLength").value);
      form.append("language", $("language").value);

      $("resultsSection").classList.add("d-none");
      $("alertArea").innerHTML = "";
      setBusy(true);
      setStatus("Uploading audio...", "Sending the file to the local server.", 0, false);

      var started = Date.now();
      elapsedId = setInterval(function () { $("statusElapsed").textContent = "Elapsed " + formatClock((Date.now() - started) / 1000); }, 1000);

      function finish() {
        clearInterval(elapsedId);
        setBusy(false);
        $("statusBox").classList.add("d-none");
      }

      var xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/process");
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) { setStatus("Uploading audio...", Math.round((e.loaded / e.total) * 100) + "% uploaded", Math.round((e.loaded / e.total) * 100), false); }
      };
      xhr.upload.onload = function () {
        setStatus("Transcribing and summarizing...",
          "This can take several minutes on a CPU. On the first run the AI models are also downloaded.", 100, true);
      };
      xhr.onload = function () {
        finish();
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (e) { data = null; }
        if (xhr.status >= 200 && xhr.status < 300 && data && data.success) {
          showAlert("success", "Processing finished successfully.");
          renderResults(data);
        } else {
          showAlert("danger", (data && data.error) || "Processing failed (HTTP " + xhr.status + ").");
        }
      };
      xhr.onerror = function () { finish(); showAlert("danger", "Could not reach the server. Make sure the application is still running."); };
      xhr.send(form);
    });
  }

  // ---------------------------------------------------------------- results page
  function initResult() {
    var page = $("resultPage");
    var area = $("transcriptArea");
    var wordCount = $("wordCount");
    var status = $("regenStatus");

    function updateCount() { wordCount.textContent = countWords(area.value) + " words"; }
    area.addEventListener("input", updateCount);
    updateCount();

    $("copyBtn").addEventListener("click", function () {
      var text = area.value;
      function fallback() {
        area.select();
        try { document.execCommand("copy"); showAlert("success", "Transcript copied to the clipboard."); }
        catch (e) { showAlert("danger", "Copy failed. Select the text and copy it manually."); }
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function () { showAlert("success", "Transcript copied to the clipboard."); }, fallback);
      } else { fallback(); }
    });

    $("downloadEditedBtn").addEventListener("click", function () {
      var blob = new Blob([area.value], { type: "text/plain;charset=utf-8" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "meeting_transcript.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });

    $("regenBtn").addEventListener("click", function () {
      var btn = $("regenBtn");
      btn.disabled = true;
      status.classList.remove("d-none");
      status.textContent = "Regenerating the summary from the edited transcript. This may take a minute...";
      fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: area.value,
          summary_length: $("regenLength").value,
          report_id: page.getAttribute("data-report-id")
        })
      }).then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      }).then(function (out) {
        if (out.ok && out.data.success) { window.location.reload(); return; }
        btn.disabled = false;
        status.classList.add("d-none");
        showAlert("danger", out.data.error || "Could not regenerate the summary.");
      }).catch(function () {
        btn.disabled = false;
        status.classList.add("d-none");
        showAlert("danger", "Could not reach the server.");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if ($("dropZone")) { initHome(); }
    if ($("resultPage")) { initResult(); }
  });
})();
