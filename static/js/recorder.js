// Handles: mic permission, prep countdown, recording countdown,
// mid-session prompt changes (debate rebuttal / Q&A stress test),
// and submitting the recorded audio to the Flask backend.

(function () {
  const timerEl = document.getElementById("timer");
  const phaseEl = document.getElementById("phase-label");
  const startBtn = document.getElementById("start-btn");
  const stopBtn = document.getElementById("stop-btn");
  const micStatus = document.getElementById("mic-status");
  const promptLabel = document.getElementById("prompt-label");
  const promptText = document.getElementById("prompt-text");
  const audioInput = document.getElementById("audio-input");
  const submitForm = document.getElementById("submit-form");

  let mediaRecorder = null;
  let chunks = [];
  let stream = null;
  let mainTimerInterval = null;
  let submitted = false;

  function setTimer(seconds) {
    timerEl.textContent = seconds + "s";
  }

  function submitRecording() {
    if (submitted) return;
    submitted = true;
    stopBtn.disabled = true;
    phaseEl.textContent = "Processing (transcribing + scoring)...";
    timerEl.textContent = "⏳";

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    } else {
      finishSubmit();
    }
  }

  function finishSubmit() {
    const mimeType = ENTRY.video ? "video/webm" : "audio/webm";
    const filename = ENTRY.video ? "recording.webm" : "recording.webm";
    const blob = new Blob(chunks, { type: mimeType });
    const file = new File([blob], filename, { type: mimeType });
    const dt = new DataTransfer();
    dt.items.add(file);
    audioInput.files = dt.files;
    submitForm.submit();
  }

  function startRecording() {
    const constraints = ENTRY.video
      ? { audio: true, video: { width: 480, height: 360 } }
      : { audio: true };

    navigator.mediaDevices.getUserMedia(constraints)
      .then((s) => {
        stream = s;
        chunks = [];

        if (ENTRY.video) {
          const preview = document.getElementById("preview");
          if (preview) preview.srcObject = stream;
        }

        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        mediaRecorder.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          finishSubmit();
        };
        mediaRecorder.start();
        micStatus.textContent = ENTRY.video ? "Recording (audio + video)..." : "Recording...";
        stopBtn.disabled = false;
        runMainTimer();
      })
      .catch((err) => {
        micStatus.textContent = (ENTRY.video ? "Camera/mic" : "Mic") + " access denied or unavailable: " + err.message;
      });
  }

  function runMainTimer() {
    let remaining = ENTRY.seconds;
    phaseEl.textContent = "Speak now";
    setTimer(remaining);
    updateMidPrompt(ENTRY.seconds - remaining);

    mainTimerInterval = setInterval(() => {
      remaining -= 1;
      setTimer(Math.max(remaining, 0));
      updateMidPrompt(ENTRY.seconds - remaining);
      if (remaining <= 0) {
        clearInterval(mainTimerInterval);
        submitRecording();
      }
    }, 1000);
  }

  function updateMidPrompt(elapsed) {
    if (ENTRY.mode === "debate_rebuttal" && ENTRY.rebuttal) {
      if (elapsed >= ENTRY.argument_seconds) {
        promptLabel.textContent = "Now rebut this:";
        promptText.textContent = ENTRY.rebuttal;
      }
    } else if (ENTRY.mode === "qa_stress_test" && ENTRY.questions) {
      const qSeconds = ENTRY.question_seconds || 30;
      const qIndex = Math.min(Math.floor(elapsed / qSeconds), ENTRY.questions.length - 1);
      promptLabel.textContent = "Question " + (qIndex + 1) + " of " + ENTRY.questions.length;
      promptText.textContent = ENTRY.questions[qIndex];
    }
  }

  function runPrep() {
    let remaining = ENTRY.prep_seconds;
    if (remaining <= 0) {
      startRecording();
      return;
    }
    phaseEl.textContent = "Get ready";
    setTimer(remaining);
    const prepInterval = setInterval(() => {
      remaining -= 1;
      setTimer(Math.max(remaining, 0));
      if (remaining <= 0) {
        clearInterval(prepInterval);
        startRecording();
      }
    }, 1000);
  }

  startBtn.addEventListener("click", () => {
    startBtn.disabled = true;
    runPrep();
  });

  stopBtn.addEventListener("click", () => {
    if (mainTimerInterval) clearInterval(mainTimerInterval);
    submitRecording();
  });

  setTimer(ENTRY.prep_seconds > 0 ? ENTRY.prep_seconds : ENTRY.seconds);
})();
