const svg = document.querySelector("#floorPlan");
const status = document.querySelector("#viewStatus");
const buttons = [...document.querySelectorAll("[data-view]")];
const isEmbed = new URLSearchParams(window.location.search).get("embed") === "1";

const views = {
  all: {
    box: isEmbed ? "0 45 1380 1030" : "0 0 1380 1160",
    status: "1층 본동 강의실 전체와 야외 복도, 별도 행정실 건물을 함께 표시합니다."
  },
  admin: {
    box: "720 35 650 560",
    status: "본동 오른쪽 위 강의실 행 위에 야외 복도를 두고, 그 위쪽만 행정실로 통합했습니다."
  },
  core: {
    box: "540 650 360 430",
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
