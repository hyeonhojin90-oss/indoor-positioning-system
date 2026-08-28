const svg = document.querySelector("#floorPlan");
const status = document.querySelector("#viewStatus");
const buttons = [...document.querySelectorAll("[data-view]")];
const isEmbed = new URLSearchParams(window.location.search).get("embed") === "1";

const views = {
  all: {
    box: isEmbed ? "0 40 1380 1050" : "0 0 1380 1180",
    status: "코어와 계단의 고정 좌표 위에 2층 강의실, 2107, S-space, TDM과 증축부 동선을 함께 표시합니다."
  },
  extension: {
    box: "820 35 540 720",
    status: "오른쪽 메인복도에서 진입해 기둥과 TDM 사이를 지나 증축부 복도로 연결되는 구조입니다."
  },
  core: {
    box: "540 600 360 430",
    status: "코어, 화장실, 엘리베이터, 코어복도와 메인계단은 다른 층과 같은 좌표로 고정되어 있습니다."
  }
};

function setView(name) {
  const view = views[name];
  svg.setAttribute("viewBox", view.box);
  if (status) status.textContent = view.status;
  buttons.forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

buttons.forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
setView("all");
