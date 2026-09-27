// ponytail: answers are hardcoded for the Northern Illinois mock.
// A CMS quiz would ship this map from front matter without printing it in HTML.

export var QUIZ_ANSWERS = {
  "northern-illinois": {
    band: "true",
    opponent: "ball-state",
    seltzer: "red-wine",
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
  if (correct === total) return "You caught it. DeKalb has nothing left to hide.";
  if (correct === 0) return "Rough night. The pork tenderloin group knew more than that.";
  if (correct + 1 === total) return "Close. One fact got past you.";
  return "A few plays got away.";
}

export function prizeLine(correct, total) {
  var score = correct + "/" + total;
  if (correct === total) return score + " — claim a shot at courtside with Eric.";
  return score + " — only a perfect card gets a shot at courtside.";
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
  var result = root.querySelector(".post-quiz-result");
  var scoreEl = root.querySelector(".post-quiz-score");
  var prizeCopy = root.querySelector(".post-quiz-prize-copy");
  var prize = root.querySelector(".post-quiz-prize");
  var retry = root.querySelector(".post-quiz-retry");

  function showResult(scoreText, line) {
    scoreEl.textContent = scoreText;
    prizeCopy.textContent = line;
    result.hidden = false;
    prize.hidden = line === "";
    result.focus();
  }

  open.addEventListener("click", function () {
    var willOpen = panel.hidden;
    panel.hidden = !willOpen;
    open.setAttribute("aria-expanded", willOpen ? "true" : "false");
    if (willOpen) {
      var first = form.querySelector("input");
      if (first) first.focus();
    }
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var picks = readPicks(form, answers);
    if (missingKeys(answers, picks).length) {
      showResult("Answer all three first.", "");
      return;
    }
    var scored = scoreQuiz(answers, picks);
    showResult(
      scored.correct + "/" + scored.total + ". " + feedbackLine(scored.correct, scored.total),
      prizeLine(scored.correct, scored.total)
    );
  });

  retry.addEventListener("click", function () {
    form.reset();
    scoreEl.textContent = "";
    prizeCopy.textContent = "";
    result.hidden = true;
    prize.hidden = true;
    var first = form.querySelector("input");
    if (first) first.focus();
  });
}

export function mountQuiz(doc) {
  var root = doc.querySelector(".post-quiz");
  if (!root) return;
  var answers = QUIZ_ANSWERS[root.getAttribute("data-quiz-id")];
  if (!answers) return;
  bindQuiz(root, answers);
}

if (typeof document !== "undefined") mountQuiz(document);
