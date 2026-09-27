// ponytail: answers are hardcoded for the Sardinia mock (sardinia-napoli.md).
// A CMS quiz would ship this map from front matter without printing it in HTML.

export var QUIZ_ANSWERS = {
  "sardinia-napoli": {
    flag: "true",
    deal: "ninety",
    bar: "redskin",
  },
};

export function scoreQuiz(answers, picks) {
  var keys = Object.keys(answers || {});
  var correct = 0;
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    if (picks && picks[key] === answers[key]) correct += 1;
  }
  return { correct: correct, total: keys.length };
}

export function missingKeys(answers, picks) {
  return Object.keys(answers || {}).filter(function (key) {
    return !picks || picks[key] === undefined || picks[key] === "";
  });
}

export function feedbackLine(correct, total) {
  if (total > 0 && correct === total) return "Perfect — you've earned a sticker.";
  if (total > 1 && correct + 1 === total) return "Close. One fact got past you.";
  if (correct === 0) return "Not this time.";
  return "Not quite. A few stops got away.";
}

export function showStickerClaim(correct, total) {
  return total > 0 && correct === total;
}

export function nextQuizStep(index, total, answered) {
  var n = Number(total) || 0;
  var i = Number(index) || 0;
  if (n < 1) return { index: 0, done: false, needsAnswer: false };
  if (i < 0) i = 0;
  if (i >= n) i = n - 1;
  if (!answered) return { index: i, done: false, needsAnswer: true };
  if (i + 1 >= n) return { index: i, done: true, needsAnswer: false };
  return { index: i + 1, done: false, needsAnswer: false };
}

export function stepLabel(index, total) {
  return index + 1 + "/" + total;
}

// First tap reveals Q1. A later tap does not close or reset; Try again does that.
export function onStartTap(started) {
  if (started) return { started: true, reveal: false };
  return { started: true, reveal: true };
}

export function readPicks(form, answers) {
  var picks = {};
  Object.keys(answers).forEach(function (key) {
    var chosen = form.querySelector('input[name="' + key + '"]:checked');
    picks[key] = chosen ? chosen.value : "";
  });
  return picks;
}

export function bindQuiz(root, answers) {
  var open = root.querySelector(".post-quiz-open");
  var panel = root.querySelector(".post-quiz-panel");
  var form = root.querySelector(".post-quiz-form");
  var steps = form.querySelectorAll(".post-quiz-q");
  var next = root.querySelector(".post-quiz-next");
  var need = root.querySelector(".post-quiz-need");
  var progress = root.querySelector(".post-quiz-progress");
  var result = root.querySelector(".post-quiz-result");
  var scoreEl = root.querySelector(".post-quiz-score");
  var prize = root.querySelector(".post-quiz-prize");
  var retry = root.querySelector(".post-quiz-retry");
  var index = 0;
  var started = false;

  function paint(i) {
    index = i;
    for (var n = 0; n < steps.length; n++) {
      var on = n === i;
      steps[n].hidden = !on;
      steps[n].disabled = !on;
    }
    if (progress) progress.textContent = stepLabel(i, steps.length);
    next.hidden = false;
    next.textContent = i === steps.length - 1 ? "Lock it in" : "Next";
    if (need) need.hidden = true;
  }

  function reset() {
    form.reset();
    result.hidden = true;
    scoreEl.textContent = "";
    if (prize) prize.hidden = true;
    if (retry) retry.hidden = true;
    paint(0);
  }

  open.addEventListener("click", function () {
    var tap = onStartTap(started);
    started = tap.started;
    if (!tap.reveal) return;
    panel.hidden = false;
    open.hidden = true;
    open.disabled = true;
    open.setAttribute("aria-expanded", "true");
    var first = steps[0] && steps[0].querySelector("input");
    if (first) first.focus();
  });

  next.addEventListener("click", function () {
    var step = steps[index];
    var answered = !!(step && step.querySelector("input:checked"));
    var move = nextQuizStep(index, steps.length, answered);
    if (move.needsAnswer) {
      if (need) need.hidden = false;
      return;
    }
    if (!move.done) {
      paint(move.index);
      var first = steps[move.index].querySelector("input");
      if (first) first.focus();
      return;
    }
    for (var n = 0; n < steps.length; n++) steps[n].disabled = false;
    var scored = scoreQuiz(answers, readPicks(form, answers));
    for (var n = 0; n < steps.length; n++) {
      steps[n].hidden = true;
      steps[n].disabled = true;
    }
    scoreEl.textContent =
      scored.correct + "/" + scored.total + ". " + feedbackLine(scored.correct, scored.total);
    result.hidden = false;
    if (prize) prize.hidden = !showStickerClaim(scored.correct, scored.total);
    if (retry) retry.hidden = false;
    next.hidden = true;
    result.focus();
  });

  if (retry) {
    retry.addEventListener("click", function () {
      reset();
      var first = steps[0] && steps[0].querySelector("input");
      if (first) first.focus();
    });
  }
}

export function mountQuiz(doc) {
  var root = doc.querySelector(".post-quiz");
  if (!root) return;
  var answers = QUIZ_ANSWERS[root.getAttribute("data-quiz-id")];
  if (!answers) return;
  bindQuiz(root, answers);
}

if (typeof document !== "undefined") mountQuiz(document);
